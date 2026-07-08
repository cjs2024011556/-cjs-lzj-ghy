"""
多模态 RAG 检索服务 - 核心
文本/图像 → 召回 → 重排 → LLM 生成 → 返回
"""
import time
import re
from typing import List, Dict, Any, Optional
from loguru import logger

from app.services.vector_indexer import MilvusIndexer
from app.llm.factory import get_model_adapter
from app.llm.base import ChatRequest, ChatMessage, MessageRole
from app.utils.images import encode_image_data_uri
from app.core.config import settings, CASES_FILE, SOPS_FILE, MANUALS_DIR
from app.utils.text import extract_keywords


# FIX-Milvus-1: Milvus 不可用时降级到关键词搜索
# cache 抽到独立模块 app.services.keyword_cache（chat.py 和 retrieval_service.py 共享）
from app.services.keyword_cache import read_cached_json, read_cached_manuals


def _keyword_fallback_hits(query: str, top_k: int) -> List[Dict[str, Any]]:
    """Milvus 不可用时的关键词降级检索（返回 hits 列表，格式与 Milvus search 一致）

    - 复用 chat.py 的 _KEYWORD_CACHE（H-Fix-3 已有）
    - 搜：案例库 + SOP 库 + manuals 段落
    - 按相关度降序排
    """
    keywords = extract_keywords(query)
    if not keywords:
        return []

    hits: List[Dict[str, Any]] = []

    # 1. 案例
    cases = read_cached_json(CASES_FILE, default=[])
    for c in cases:
        text = " ".join([
            c.get("title", ""),
            c.get("fault_description", ""),
            c.get("solution", ""),
            " ".join(c.get("tags", [])),
        ])
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            hits.append({
                "chunk_id": c["case_id"],
                "content": f"**{c['title']}**\n故障：{c['fault_description']}\n方案：{c['solution']}",
                "source": f"案例库/{c['case_id']}",
                "score": float(score),
                "doc_type": "case",
                "equipment_type": c.get("equipment_type", ""),
                "equipment_model": c.get("equipment_model", ""),
                "chunk_index": 0,
                # PDF-A.5
                "page_number": 0, "page_end": 0,
                "chapter": "", "section_title": "",
                "section_type": "text", "section_level": 0,
                "doc_id": "",
                # PDF-B.5
                "image_description": "", "image_facts": "",
            })

    # 2. SOP
    sops = read_cached_json(SOPS_FILE, default=[])
    for s in sops:
        if any(kw in s.get("equipment_type", "") for kw in keywords) or \
           any(kw in s.get("name", "") for kw in keywords):
            hits.append({
                "chunk_id": s["sop_id"],
                "content": f"**{s['name']}** ({s['sop_id']})\n工具：{', '.join(s.get('tools', [])[:5])}\n步骤数：{len(s.get('steps', []))}",
                "source": f"SOP 库/{s['sop_id']}",
                "score": 0.5,
                "doc_type": "sop",
                "equipment_type": s.get("equipment_type", ""),
                "equipment_model": "",
                "chunk_index": 0,
                # PDF-A.5
                "page_number": 0, "page_end": 0,
                "chapter": "", "section_title": s.get("name", ""),
                "section_type": "text", "section_level": 0,
                "doc_id": "",
                # PDF-B.5
                "image_description": "", "image_facts": "",
            })

    # 3. manuals 段落
    manuals = read_cached_manuals(MANUALS_DIR)
    for stem, text in manuals.items():
        sections = re.split(r'(?=^## )', text, flags=re.MULTILINE)
        for sec in sections:
            sec = sec.strip()
            if len(sec) < 20:
                continue
            first_line = sec.split('\n', 1)[0].strip()
            score = sum(1 for kw in keywords if kw in sec)
            if score > 0:
                hits.append({
                    "chunk_id": f"manual:{stem}#{hash(first_line) & 0xffff:04x}",
                    "content": sec[:500],
                    "source": f"手册/{stem}",
                    "score": float(score * 0.7),
                    "doc_type": "manual",
                    "equipment_type": "",
                    "equipment_model": "",
                    "chunk_index": 0,
                    # PDF-A.5
                    "page_number": 0, "page_end": 0,
                    "chapter": "", "section_title": first_line,
                    "section_type": "text", "section_level": 2,
                    "doc_id": f"md:{stem}",
                    # PDF-B.5
                    "image_description": "", "image_facts": "",
                })

    hits.sort(key=lambda x: -x["score"])
    return hits[:top_k]


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

        # FIX-Milvus-1: Milvus 不可用时降级到 keyword 搜索
        # - 首次连接失败（_ensure_connected 抛 MilvusException）→ catch 后走 keyword
        # - 后续 query 失败也走 keyword（首次失败后 self._client 仍为 None 会重试 connect）
        try:
            hits = await self.indexer.search(full_query, top_k=candidate_k, filter_expr=filter_expr)
            logger.info(f"✅ Milvus 向量检索: {len(hits)} hits")
        except Exception as milvus_err:
            logger.warning(
                f"⚠️ Milvus 不可用 ({type(milvus_err).__name__}: {milvus_err})，"
                f"降级到 keyword 搜索"
            )
            hits = _keyword_fallback_hits(full_query, top_k)

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
        """构造上下文（聚群 A: 含页码 + 章节 + 类型）"""
        if not hits:
            return "（未检索到相关知识库内容）"
        lines = []
        for i, hit in enumerate(hits, 1):
            # 拼位置标签：有页码就显示「第 X 页 §章节」，否则显示设备型号
            page = hit.get("page_number", 0)
            section = hit.get("section_title", "")
            chapter = hit.get("chapter", "")
            section_type = hit.get("section_type", "text")

            location_parts = []
            if page and page > 0:
                if hit.get("page_end") and hit["page_end"] > page:
                    location_parts.append(f"第 {page}-{hit['page_end']} 页")
                else:
                    location_parts.append(f"第 {page} 页")
            if section and section != "(前言)":
                location_parts.append(f"§{section}")
            if section_type == "table":
                location_parts.append("📊 表格")

            location = " · ".join(location_parts) if location_parts else ""

            head = f"【{i}】来源: {hit['source']}"
            if location:
                head += f" · {location}"
            head += f" (类型: {hit['doc_type']}"
            if hit.get("equipment_type") or hit.get("equipment_model"):
                head += f", 设备: {hit.get('equipment_type', '-')}/{hit.get('equipment_model', '-')}"
            head += ")"

            lines.append(head)
            if chapter and chapter != hit['source']:
                lines.append(f"   章节: {chapter}")
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
4. 涉及安全操作的必须强调安全
5. 【聚群 A 增强】每条数据 / 步骤都要尽量带上**页码 + 章节**溯源（PDF 手册来源尤其重要）
6. 【聚群 A 增强】表格类内容需保留原始结构（行/列对应），不要拍平为纯文字
7. 【聚群 A 增强】如检索结果含页码，回答末尾给"参考来源"块列出页码与章节"""

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
