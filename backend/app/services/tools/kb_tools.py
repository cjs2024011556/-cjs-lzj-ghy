"""
聚群 C 4 工具实现

工具集合（满足 LLM 在工业检修场景的需求）：
1. search_kb: 知识库语义检索（向量 + 重排）
2. lookup_chunk: 按 chunk_id 精确定位（用于 RAG 引文深挖）
3. describe_image: VL 解读图片（用户上传故障图）
4. query_graph: 故障图谱查询（实体 + 邻居）

为什么这 4 个：
- search_kb 是基础，所有检修问题都要先检索
- lookup_chunk 让 agent 可以「回到具体 chunk 看完整内容」
- describe_image 处理用户上传的图片
- query_graph 提供图谱推理能力（项目已有 Neo4j 集成）

为什么不直接调 RAG 主链路：
- 主链路带了 system prompt + answer 生成的 LLM 调用（很重）
- 工具版只做检索，不做 LLM 生成，让 agent 自己决定后续
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

from app.services.tools.base import BaseTool, ToolRegistry


# ============================================================
# Tool 1: search_kb
# ============================================================
class SearchKBTool(BaseTool):
    """知识库语义检索（向量 + 关键词）"""
    name = "search_kb"
    description = (
        "在 A1 设备检修知识库中做语义检索。"
        "适用：用户问故障现象/检修方法/技术参数/案例 时调用。"
        "返回 top-k 个相关文档片段（含页码/章节/视觉理解），用于回答用户问题。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "用户问题的核心关键词（去掉'请告诉我'等客套词）",
            },
            "top_k": {
                "type": "integer",
                "description": "返回结果数量，默认 5，范围 1-10",
                "default": 5,
                "minimum": 1,
                "maximum": 10,
            },
            "equipment_model": {
                "type": "string",
                "description": "可选，限定设备型号过滤（如 YUKEN A37）",
            },
        },
        "required": ["query"],
    }

    async def __call__(
        self,
        query: str,
        top_k: int = 5,
        equipment_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        from app.services.retrieval_service import RetrievalService
        service = RetrievalService()
        result = await service.retrieve(
            query=query,
            top_k=top_k,
            equipment_model=equipment_model,
        )
        # 简化输出：去掉 embedding 等大字段
        hits = result.get("hits", [])
        slim = [
            {
                "chunk_id": h.get("chunk_id"),
                "content": h.get("content", "")[:500],
                "source": h.get("source"),
                "score": h.get("score"),
                "page_number": h.get("page_number"),
                "chapter": h.get("chapter"),
                "section_title": h.get("section_title"),
                "section_type": h.get("section_type"),
            }
            for h in hits
        ]
        return {
            "query": query,
            "top_k": top_k,
            "hits": slim,
            "count": len(slim),
        }


# ============================================================
# Tool 2: lookup_chunk
# ============================================================
class LookupChunkTool(BaseTool):
    """按 chunk_id 精确查一个 chunk（用于 RAG 引文深挖）"""
    name = "lookup_chunk"
    description = (
        "按 chunk_id 精确查一个知识库 chunk 的完整内容。"
        "适用：search_kb 召回后想看某条完整内容 / 看页码 / 看视觉理解。"
        "返回该 chunk 的完整字段（content / page / chapter / image_description / image_facts）。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "chunk_id": {
                "type": "string",
                "description": "知识库 chunk 的唯一 ID（通常从 search_kb 召回里拿）",
            },
        },
        "required": ["chunk_id"],
    }

    async def __call__(self, chunk_id: str) -> Dict[str, Any]:
        from app.services.vector_indexer import MilvusIndexer
        indexer = MilvusIndexer()
        indexer._ensure_connected()
        # 直接 query by id（不走 embedding）
        from pymilvus import Collection
        coll = Collection(indexer.COLLECTION_NAME, using="default")
        rows = coll.query(
            expr=f'chunk_id == "{chunk_id}"',
            output_fields=[
                "chunk_id", "content", "source", "page_number", "chapter",
                "section_title", "section_type", "image_description", "image_facts",
            ],
            limit=1,
        )
        if not rows:
            return {"error": f"chunk_id={chunk_id} 不存在"}
        return rows[0]


# ============================================================
# Tool 3: describe_image
# ============================================================
class DescribeImageTool(BaseTool):
    """用 VL 模型描述一张图片（用户上传的故障图）"""
    name = "describe_image"
    description = (
        "用视觉语言模型解读用户上传的设备故障图片。"
        "适用：用户上传了故障照片，想让 AI 描述故障现象 / 读出仪表读数 / 识别报警码。"
        "返回：description（描述）+ facts（关键事实列表）。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "图片文件路径（绝对路径，PNG/JPG/WEBP）",
            },
            "question": {
                "type": "string",
                "description": "可选，用户对图的具体问题（如「读出油温表数值」）",
            },
        },
        "required": ["image_path"],
    }

    async def __call__(
        self,
        image_path: str,
        question: Optional[str] = None,
    ) -> Dict[str, Any]:
        from pathlib import Path
        p = Path(image_path)
        if not p.exists():
            return {"error": f"图片不存在: {image_path}"}
        # 读 → base64
        from app.utils.images import encode_image_data_uri
        from app.llm.factory import get_model_adapter
        from app.llm.base import ChatRequest, ChatMessage, MessageRole

        data_uri = encode_image_data_uri(str(p))
        prompt = "请详细描述这张设备故障图片，提取关键事实（参数、报警码、损坏部位等）。"
        if question:
            prompt += f"\n用户问题：{question}"

        adapter = get_model_adapter()
        resp = await adapter.chat(ChatRequest(
            messages=[ChatMessage(
                role=MessageRole.USER,
                content=[
                    {"type": "image_url", "image_url": {"url": data_uri}},
                    {"type": "text", "text": prompt},
                ],
            )],
            temperature=0.1,
            max_tokens=600,
        ))
        return {
            "image_path": image_path,
            "description": resp.content,
            "model": resp.model,
        }


# ============================================================
# Tool 4: query_graph
# ============================================================
class QueryGraphTool(BaseTool):
    """故障图谱查询（Neo4j）"""
    name = "query_graph"
    description = (
        "在故障知识图谱里查实体（如设备/故障/原因/解决方案）的邻居节点。"
        "适用：用户问'XXX 故障可能由哪些原因引起' / 'XXX 设备的常见故障'。"
        "返回：实体的类型、邻居节点列表、关系类型。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "entity": {
                "type": "string",
                "description": "实体名（如'电机过热'、'液压泵'、'阀门内漏'）",
            },
            "depth": {
                "type": "integer",
                "description": "查询深度（1=直接邻居，2=二层邻居），默认 1",
                "default": 1,
                "minimum": 1,
                "maximum": 2,
            },
        },
        "required": ["entity"],
    }

    async def __call__(self, entity: str, depth: int = 1) -> Dict[str, Any]:
        # 调用项目已有图谱服务
        try:
            from app.services.graph_service import get_graph_service
            svc = get_graph_service()
            result = await svc.get_neighborhood(
                entity_name=entity,
                depth=depth,
                max_nodes=20,
            )
            return {
                "entity": entity,
                "depth": depth,
                "nodes": result.get("nodes", []),
                "edges": result.get("edges", []),
                "count": len(result.get("nodes", [])),
            }
        except Exception as e:
            logger.warning(f"图谱查询失败: {e}")
            return {"error": f"图谱查询失败: {e}", "entity": entity}


# ============================================================
# 默认注册表（单例）
# ============================================================
_DEFAULT_REGISTRY: Optional[ToolRegistry] = None


def build_default_registry() -> ToolRegistry:
    """构造默认工具注册表（4 工具）"""
    reg = ToolRegistry()
    reg.register(SearchKBTool())
    reg.register(LookupChunkTool())
    reg.register(DescribeImageTool())
    reg.register(QueryGraphTool())
    return reg


def get_default_registry() -> ToolRegistry:
    """获取默认工具注册表（懒加载单例）"""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = build_default_registry()
    return _DEFAULT_REGISTRY
