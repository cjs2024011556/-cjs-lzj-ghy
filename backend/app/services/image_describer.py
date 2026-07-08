"""
图片描述器 — 用 VL 模型理解 PDF 页面图像

输入：PNG bytes（来自 page_renderer）
输出：{description: str, facts: List[str]}

聚群 B 用途：
- 扫描页 OCR 兜底（is_likely_scanned 触发）
- 图表页视觉理解（流程图/电路图/数据曲线）
- 把视觉信息转成可被 embedding 检索的文本

设计要点：
- 缓存：按 PNG SHA-256 哈希缓存描述（避免重渲染 + 重 VL）
- 可注入：测试时可注入 mock describer
- 降级：VL 失败时返回空 description（不阻塞 PDF 解析）
"""
from __future__ import annotations

import json as _json
import re
from collections import OrderedDict
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from loguru import logger

from app.services.page_renderer import hash_png, encode_png_to_data_uri


# ============================================================
# 数据类
# ============================================================
@dataclass
class ImageDescription:
    """单张图的 VL 描述结果"""
    description: str = ""                        # 整体描述（200-400 字）
    facts: List[str] = field(default_factory=list)   # 关键事实列表（3-8 条）
    page_number: int = 0                         # 来源页码
    model: str = ""                              # 使用的模型名
    cached: bool = False                         # 是否来自缓存

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    def is_empty(self) -> bool:
        return not self.description.strip() and not self.facts

    def as_chunk_metadata(self) -> Dict[str, Any]:
        """转 chunk metadata 格式（塞进 Milvus 字段）"""
        return {
            "image_description": self.description[:2000],  # VARCHAR 2048 上限
            "image_facts": ",".join(self.facts)[:1000],   # VARCHAR 1024 上限
        }


# ============================================================
# 缓存（PNG hash → ImageDescription）
# ============================================================
_DESC_CACHE: "OrderedDict[str, ImageDescription]" = OrderedDict()
_CACHE_MAX = 256


def _cache_get(key: str) -> Optional[ImageDescription]:
    if key in _DESC_CACHE:
        _DESC_CACHE.move_to_end(key)
        return _DESC_CACHE[key]
    return None


def _cache_put(key: str, value: ImageDescription) -> None:
    value.cached = False  # 缓存里的是新生成的
    _DESC_CACHE[key] = value
    while len(_DESC_CACHE) > _CACHE_MAX:
        _DESC_CACHE.popitem(last=False)


def clear_cache() -> None:
    _DESC_CACHE.clear()


# ============================================================
# Prompt 模板
# ============================================================
_PROMPT = """你是一个工业设备检修手册的图像理解专家。请分析这张图片，提取对设备维护/故障诊断有用的关键信息。

按以下 JSON 格式输出（不要任何其他文字、markdown 包裹或解释）：
{{
  "description": "用 2-3 句话客观描述图片类型和内容（如：系统液压回路图 / 故障树状图 / 扫描件工艺参数表 / 数据趋势曲线等）",
  "facts": [
    "关键事实 1（如：报警代码 E0123 表示电机过载）",
    "关键事实 2（如：油温上限 80°C）",
    "关键事实 3（如：更换周期：每 2000 小时）"
  ]
}}

要求：
1. facts 数量 3-8 条，按重要性排序
2. 数字、参数、报警码、零件编号必须保留
3. 如果是扫描件（无清晰图表），focus 在文字内容识别
4. 如果是图表（流程图/电路图/曲线），focus 在结构和关键节点
5. 如果图片模糊或信息极少，description 写"图片信息不足"，facts 留空数组

严格只输出 JSON。"""


def _parse_response(content: str) -> ImageDescription:
    """解析 VL 返回的 JSON 字符串 → ImageDescription（容错）"""
    if not content:
        return ImageDescription()
    text = content.strip()
    # 去掉 markdown 包裹
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0].strip()
    try:
        data = _json.loads(text)
        return ImageDescription(
            description=str(data.get("description", "")).strip(),
            facts=[str(f).strip() for f in data.get("facts", []) if f],
        )
    except Exception as e:
        # 容错：从文本里提 facts（按行号 "1." 或 "-" 分割）
        logger.debug(f"VL 响应 JSON 解析失败: {e}, content={text[:120]}")
        facts = []
        for m in re.finditer(r'(?:^|\n)\s*[\-\d\.\)]\s*(.+)', text):
            facts.append(m.group(1).strip()[:200])
        return ImageDescription(
            description=text[:400] if not facts else "",
            facts=facts[:8],
        )


# ============================================================
# 主类
# ============================================================
class ImageDescriber:
    """VL 图像描述器（聚群 B）"""

    def __init__(
        self,
        model_name: Optional[str] = None,
        max_tokens: int = 800,
        use_cache: bool = True,
    ):
        self.model_name = model_name  # None 时用 settings.CLOUD_LLM.model
        self.max_tokens = max_tokens
        self.use_cache = use_cache

    async def describe(
        self,
        png_bytes: bytes,
        page_number: int = 0,
        extra_context: str = "",
    ) -> ImageDescription:
        """描述一张 PNG 图像

        Args:
            png_bytes: PNG 图片字节
            page_number: 来源页码（记录用）
            extra_context: 额外上下文（可选，用于 prompt 增强）

        Returns:
            ImageDescription（含 description / facts / model / cached）
        """
        # 1. 缓存查
        key = hash_png(png_bytes)
        if self.use_cache:
            cached = _cache_get(key)
            if cached is not None:
                cached.cached = True
                cached.page_number = page_number
                return cached

        # 2. 调 VL
        try:
            desc = await self._call_vl(png_bytes, extra_context)
        except Exception as e:
            logger.warning(f"⚠️ VL 描述失败 (page={page_number}): {e}")
            return ImageDescription(
                description="",
                facts=[],
                page_number=page_number,
            )

        desc.page_number = page_number
        if self.use_cache:
            _cache_put(key, desc)
        return desc

    async def _call_vl(self, png_bytes: bytes, extra_context: str = "") -> ImageDescription:
        """调用底层 VL 适配器"""
        from app.llm.factory import get_model_adapter
        from app.llm.base import ChatRequest, ChatMessage, MessageRole

        adapter = get_model_adapter()
        # 选模型：优先用 settings 里的 VL 模型，否则用当前模型
        model = self.model_name
        if not model:
            try:
                from app.core.config import settings
                model = settings.CLOUD_LLM.model
            except Exception:
                model = None

        data_uri = encode_png_to_data_uri(png_bytes)
        user_text = _PROMPT
        if extra_context:
            user_text += f"\n\n附加上下文：{extra_context}"

        # 构造 ChatRequest（多模态）
        content = [
            {"type": "image_url", "image_url": {"url": data_uri}},
            {"type": "text", "text": user_text},
        ]
        request = ChatRequest(
            messages=[ChatMessage(role=MessageRole.USER, content=content)],
            temperature=0.1,  # 低温度 = 更稳定
            max_tokens=self.max_tokens,
        )

        # 如果指定了不同的 model，临时覆盖 adapter 路由
        if model and not _is_vl_capable(adapter):
            logger.warning(f"当前 adapter {type(adapter).__name__} 不支持 VL 图像，跳过描述")
            return ImageDescription()

        response = await adapter.chat(request)
        return _parse_response(response.content)


def _is_vl_capable(adapter) -> bool:
    """简单判断 adapter 能不能处理图像"""
    # BailianAdapter._chat_with_model 会按消息内容自动路由
    # LocalQwen2VLAdapter 也支持图像
    return hasattr(adapter, "_chat_multimodal") or hasattr(adapter, "model_name")


# ============================================================
# 注入点（测试用）
# ============================================================
class MockImageDescriber(ImageDescriber):
    """测试用：返回固定 description + facts，不调真实 VL"""

    def __init__(self, mock_description: str = "（mock）图描述", mock_facts: Optional[List[str]] = None, **kwargs):
        super().__init__(**kwargs)
        self._mock_desc = mock_description
        self._mock_facts = mock_facts or ["（mock）事实 1", "（mock）事实 2"]

    async def _call_vl(self, png_bytes: bytes, extra_context: str = "") -> ImageDescription:
        return ImageDescription(
            description=self._mock_desc,
            facts=list(self._mock_facts),
        )


# ============================================================
# 便捷函数
# ============================================================
async def describe_image(
    png_bytes: bytes,
    page_number: int = 0,
) -> ImageDescription:
    """便捷函数"""
    return await ImageDescriber().describe(png_bytes, page_number)
