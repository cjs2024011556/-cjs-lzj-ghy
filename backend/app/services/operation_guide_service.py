"""
作业指引服务 - 根据设备类型 + 检修等级生成 SOP
"""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger

from app.llm.factory import get_model_adapter
from app.llm.base import ChatRequest, ChatMessage, MessageRole
from app.core.config import settings, SOPS_FILE


# 内存中缓存 SOP 库
_sop_db: Dict[str, Dict] = {}


def _load_sop_library():
    """启动时加载 SOP 库"""
    global _sop_db
    if not SOPS_FILE.exists():
        logger.warning(f"SOP 库文件不存在: {SOPS_FILE}")
        return
    try:
        data = json.loads(SOPS_FILE.read_text(encoding="utf-8"))
        for sop in data:
            _sop_db[sop["sop_id"]] = sop
        logger.info(f"✅ SOP 库加载: {len(_sop_db)} 个")
    except Exception as e:
        logger.error(f"SOP 库加载失败: {e}")


# 启动时加载
_load_sop_library()


class OperationGuideService:
    """作业指引服务"""

    def _find_sop(
        self,
        equipment_type: str,
        maintenance_level: str,
    ) -> Optional[Dict[str, Any]]:
        """从 SOP 库查找匹配项"""
        for sop in _sop_db.values():
            if sop["equipment_type"] == equipment_type and sop["maintenance_level"] == maintenance_level:
                return sop
        # 模糊匹配
        for sop in _sop_db.values():
            if sop["equipment_type"] == equipment_type:
                return sop
        return None

    async def generate_guide(
        self,
        equipment_type: str,
        equipment_model: Optional[str],
        maintenance_level: str,
        fault_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成作业指引

        策略: 优先从 SOP 库查找 → LLM 个性化重写
        """
        import time
        start = time.time()

        # 1. 查 SOP 库
        sop = self._find_sop(equipment_type, maintenance_level)
        if not sop:
            logger.info(f"SOP 库无匹配 ({equipment_type}/{maintenance_level})，由 LLM 生成")

        # 2. LLM 重写 / 生成
        system_prompt = """你是设备检修作业指导专家。

任务: 基于标准 SOP 和用户实际场景（设备型号、故障描述），输出个性化的作业指引。

要求:
1. 严格遵守安全警告
2. 步骤要具体、可操作
3. 每步标注: 风险等级 (low/medium/high)、所需工具、合规校验点
4. 涉及断电、挂牌、PPE 等安全要求时必须明确

输出 JSON 格式:
{
  "sop_id": "...",
  "name": "...",
  "equipment_type": "...",
  "maintenance_level": "...",
  "estimated_minutes": 0,
  "tools": ["..."],
  "safety_warnings": ["..."],
  "steps": [
    {
      "step_no": 1,
      "title": "...",
      "action": "...",
      "risk_level": "low/medium/high",
      "tools": ["..."],
      "compliance": ["..."],
      "estimated_minutes": 0
    }
  ],
  "personalized_notes": "针对用户具体场景的额外说明"
}"""

        sop_context = ""
        if sop:
            sop_context = f"标准 SOP 库参考（sop_id: {sop['sop_id']}）:\n{json.dumps(sop, ensure_ascii=False, indent=2)}\n\n"

        user_msg = f"""{sop_context}用户实际场景:
- 设备类型: {equipment_type}
- 设备型号: {equipment_model or '未指定'}
- 检修等级: {maintenance_level}
- 故障描述: {fault_description or '无（标准保养）'}

请基于以上信息输出作业指引 JSON。"""

        adapter = get_model_adapter()
        response = await adapter.chat(ChatRequest(
            messages=[ChatMessage(role=MessageRole.USER, content=user_msg)],
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=3000,
        ))

        # 解析 JSON
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        try:
            guide = json.loads(content)
        except json.JSONDecodeError:
            # 兜底: 用 SOP 库
            logger.warning("LLM 返回非 JSON，使用 SOP 库兜底")
            guide = sop or {
                "sop_id": "CUSTOM",
                "name": f"{equipment_type} {maintenance_level}",
                "equipment_type": equipment_type,
                "maintenance_level": maintenance_level,
                "estimated_minutes": 0,
                "tools": [],
                "safety_warnings": ["请参考设备维修手册"],
                "steps": [],
            }

        latency = (time.time() - start) * 1000
        guide["latency_ms"] = round(latency, 1)
        guide["model"] = response.model
        guide["source"] = "sop_library" if sop else "llm_generated"

        return guide

    def list_sops(self) -> List[Dict[str, Any]]:
        """列出所有 SOP"""
        return list(_sop_db.values())
