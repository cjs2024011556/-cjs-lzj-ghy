"""
多模态 RAG 检索服务 - 核心
文本/图像 → 召回 → 重排 → LLM 生成 → 返回
"""
import time
from typing import List, Dict, Any, Optional
from loguru import logger

from app.services.vector_indexer import MilvusIndexer
from app.llm.factory import get_model_adapter
from app.llm.base import ChatRequest, ChatMessage, MessageRole
from app.utils.images import encode_image_data_uri
from app.core.config import settings


class RetrievalService:
    """多模态 RAG 检索服务"""

    def __init__(self):
        self.indexer = MilvusIndexer()

    async def retrieve(
        self,
        query: str,
        image_path: Optional[str] = None,
        equipment_model: Optional[str] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """主入口

        Args:
            query: 文本查询
            image_path: 故障图片（可选）
            equipment_model: 设备型号（精确过滤）
            top_k: 返回条数

        Returns:
            {
                "answer": "...",
                "hits": [...],
                "model": "...",
                "latency_ms": 1234.5,
            }
        """
        start = time.time()

        # 1. 预处理：一次性把图像编码为 data URI（避免后续重复 read_bytes + b64）
        image_data_uri = encode_image_data_uri(image_path) if image_path else None

        # 2. 构造检索 query（含图像描述会注入到 query）
        full_query = query
        if image_data_uri:
            full_query = await self._describe_image(image_data_uri, query)

        # 3. 向量检索（先取 RETRIEVAL_TOP_K 候选，U2 再 rerank）
        from app.core.config import settings
        from app.llm.factory import get_model_adapter

        candidate_k = settings.RETRIEVAL_TOP_K if settings.RERANK_ENABLED else top_k
        filter_expr = (
            f'equipment_model == "{equipment_model}"' if equipment_model else None
        )
        hits = await self.indexer.search(full_query, top_k=candidate_k, filter_expr=filter_expr)

        # 3.5 Rerank（U2：百炼 gte-rerank 精排；失败降级用原顺序）
        if settings.RERANK_ENABLED and len(hits) > top_k:
            try:
                adapter = get_model_adapter()
                docs = [h["content"] for h in hits]
                ranked_idx = await adapter.rerank(full_query, docs, top_n=top_k)
                hits = [hits[i] for i in ranked_idx if i < len(hits)]
            except Exception as e:
                logger.warning(f"rerank 失败，降级到原顺序: {e}")

        # 4. LLM 生成（带引用的答案）
        context = self._build_context(hits)
        system_prompt = self._get_system_prompt()
        user_content = self._build_user_content(query, image_data_uri, context)
        messages = [ChatMessage(role=MessageRole.USER, content=user_content)]

        adapter = get_model_adapter()
        response = await adapter.chat(ChatRequest(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=2000,
        ))

        latency = (time.time() - start) * 1000
        return {
            "answer": response.content,
            "hits": hits,
            "model": response.model,
            "latency_ms": round(latency, 1),
            "usage": response.usage,
        }

    async def _describe_image(self, image_data_uri: str, user_query: str) -> str:
        """用多模态模型生成图像描述，扩展检索 query"""
        adapter = get_model_adapter()
        try:
            messages = [ChatMessage(
                role=MessageRole.USER,
                content=[
                    {"type": "image_url", "image_url": {"url": image_data_uri}},
                    {"type": "text", "text": f"用户问题：{user_query}\n\n请描述这张设备故障图片，看到什么设备、什么故障现象、任何异常细节。用中文简洁回答，控制在 200 字内。"},
                ],
            )]
            resp = await adapter.chat(ChatRequest(messages=messages, max_tokens=300, temperature=0.3))
            return f"{user_query}\n\n[图像描述]: {resp.content}"
        except Exception as e:
            logger.warning(f"图像描述失败，使用纯文本查询: {e}")
            return user_query

    def _build_context(self, hits: List[Dict[str, Any]]) -> str:
        """构造上下文"""
        if not hits:
            return "（未检索到相关知识库内容）"
        lines = []
        for i, hit in enumerate(hits, 1):
            lines.append(
                f"【{i}】来源: {hit['source']} (类型: {hit['doc_type']}, "
                f"设备: {hit.get('equipment_type', '-')}, 型号: {hit.get('equipment_model', '-')})"
            )
            lines.append(f"   相关度: {hit['score']:.3f}")
            lines.append(
                f"   内容: {hit['content'][:500]}{'...' if len(hit['content']) > 500 else ''}"
            )
            lines.append("")
        return "\n".join(lines)

    def _get_system_prompt(self) -> str:
        return """你是设备检修智能助手。基于【知识库检索结果】回答用户问题。

要求:
1. 答案必须基于检索内容，标注引用来源编号（【1】、【2】...）
2. 简洁、结构化、可操作
3. 如果检索内容与问题无关，请直接说明并给出建议
4. 涉及安全操作的必须强调安全"""

    def _build_user_content(self, query: str, image_data_uri: Optional[str], context: str) -> Any:
        """构造用户消息内容"""
        text = f"""用户问题: {query}

知识库检索结果:
{context}

请基于以上检索结果回答用户问题，并标注引用。"""
        if image_data_uri:
            return [
                {"type": "image_url", "image_url": {"url": image_data_uri}},
                {"type": "text", "text": text},
            ]
        return text
