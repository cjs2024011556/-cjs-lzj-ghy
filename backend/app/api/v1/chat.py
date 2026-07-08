"""
聊天 API（首页 - ChatGPT 风格）
- POST /api/v1/chat  智能对话（意图识别 + RAG 路由）
- POST /api/v1/chat/stream  流式（SSE）
- POST /api/v1/chat/agent  工具链（聚群 C ReAct Agent，SSE）
"""
import time
from typing import List, Optional, Dict, Any, Tuple
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.llm.factory import get_model_adapter
from app.llm.base import ChatRequest, ChatMessage, MessageRole
from app.core.config import settings
from app.core.logger import logger
from app.services.retrieval_service import RetrievalService
from app.services.keyword_cache import read_cached_json, read_cached_manuals
from fastapi.responses import StreamingResponse

router = APIRouter()
_retrieval_service = RetrievalService()


# ============================================================
# 公共常量
# ============================================================
_RAG_TEMPERATURE = 0.3
_CASUAL_TEMPERATURE = 0.7
_RAG_MAX_TOKENS = 2000
_CASUAL_MAX_TOKENS = 1500
_CASUAL_PROMPT = (
    "你是 A1 设备检修智能系统的对话助手。你可以正常回答用户问题，"
    "如果用户问的是设备检修/工业相关问题，请建议他描述具体设备类型、故障现象，"
    "以便系统用专业知识库回答。你可以闲聊、回答常识问题、帮助分析一般问题。"
)
_RAG_PROMPT = (
    "你是 A1 设备检修智能系统的专家助理。请严格基于下方提供的'参考案例与 SOP'回答用户问题。"
    "要求：1. 优先用参考信息回答，引用具体案例 ID 或 SOP 编号；2. 答案结构清晰；3. 涉及安全时必须加警示。"
)
_RAG_USER_TEMPLATE = (
    "参考案例与 SOP：\n{context}\n\n用户问题：{message}\n\n请基于以上参考给出专业回答。"
)


# ============================================================
# 公共函数（chat() 和 _stream_chat() 共享）
# ============================================================
async def _classify_intent(adapter, message: str) -> Dict[str, Any]:
    """意图识别（带失败降级）"""
    try:
        return await adapter.classify_intent(message)
    except Exception as e:
        logger.warning(f"意图识别异常: {e}")
        return {"intent": "casual", "confidence": 0.0, "reason": "意图识别失败"}


def _history_to_messages(history: List["ChatTurnMessage"], last_n: int = 6) -> List[ChatMessage]:
    """history → ChatMessage 列表（限制 last_n 轮）"""
    messages: List[ChatMessage] = []
    for h in history[-last_n:]:
        messages.append(ChatMessage(
            role=MessageRole.USER if h.role == "user" else MessageRole.ASSISTANT,
            content=h.content,
        ))
    return messages


def _hits_to_sources(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Milvus hits → sources 列表（聚群 A: 透传结构化字段 + 聚群 B: 视觉理解字段）"""
    return [
        {
            "chunk_id": h.get("chunk_id", ""),
            "content": h.get("content", ""),
            "source": h.get("source", ""),
            "score": h.get("score", 0.0),
            "equipment_type": h.get("equipment_type", ""),
            "equipment_model": h.get("equipment_model", ""),
            # PDF-A.5 聚群 A
            "page_number": h.get("page_number", 0),
            "page_end": h.get("page_end", 0),
            "chapter": h.get("chapter", ""),
            "section_title": h.get("section_title", ""),
            "section_type": h.get("section_type", "text"),
            "section_level": h.get("section_level", 0),
            "doc_id": h.get("doc_id", ""),
            # PDF-B.5 聚群 B
            "image_description": h.get("image_description", ""),
            "image_facts": h.get("image_facts", ""),
        }
        for h in hits
    ]


async def _route_and_retrieve(message: str, top_k: int) -> Tuple[List[Dict[str, Any]], str, float, bool]:
    """RAG 路由（统一入口，流式 / 非流式共享）

    Returns: (sources, context, retrieval_latency_ms, used_rag)
    """
    rs = time.time()
    sources: List[Dict[str, Any]] = []
    context = ""
    used_rag = False
    try:
        result = await _retrieval_service.retrieve(query=message, top_k=top_k)
        sources = _hits_to_sources(result.get("hits", []))
        context = result.get("context", "")
        used_rag = True
    except Exception as e:
        logger.warning(f"向量检索失败，降级关键词匹配: {type(e).__name__}: {e}")
        try:
            fallback_hits, fallback_context = await _keyword_fallback(message, top_k)
            logger.info(f"关键词降级匹配: {len(fallback_hits)} 个 case/SOP")
            sources = fallback_hits
            context = fallback_context
            used_rag = True
        except Exception as e2:
            logger.error(f"关键词降级也失败: {e2}")
    return sources, context, (time.time() - rs) * 1000, used_rag


def _build_rag_request(history: List["ChatTurnMessage"], message: str, context: str) -> ChatRequest:
    """构造 RAG ChatRequest（基于检索上下文）"""
    messages = _history_to_messages(history)
    user_msg = _RAG_USER_TEMPLATE.format(
        context=context if context else "（未找到直接匹配的参考）",
        message=message,
    )
    messages.append(ChatMessage(role=MessageRole.USER, content=user_msg))
    return ChatRequest(
        messages=messages,
        system_prompt=_RAG_PROMPT,
        temperature=_RAG_TEMPERATURE,
        max_tokens=_RAG_MAX_TOKENS,
    )


def _build_casual_request(history: List["ChatTurnMessage"], message: str) -> ChatRequest:
    """构造闲聊 ChatRequest"""
    messages = _history_to_messages(history)
    messages.append(ChatMessage(role=MessageRole.USER, content=message))
    return ChatRequest(
        messages=messages,
        system_prompt=_CASUAL_PROMPT,
        temperature=_CASUAL_TEMPERATURE,
        max_tokens=_CASUAL_MAX_TOKENS,
    )


class ChatTurnMessage(BaseModel):
    """单条历史消息"""
    role: str = Field(..., description="user | assistant")
    content: str = Field(..., description="消息内容")


class ChatRequestModel(BaseModel):
    """聊天请求"""
    message: str = Field(..., min_length=1, max_length=2000, description="当前用户消息")
    history: List[ChatTurnMessage] = Field(default_factory=list, description="历史消息")
    top_k: int = Field(default=5, ge=1, le=10, description="检索 Top-K")
    model: Optional[str] = Field(default=None, description="指定 LLM 模型（默认走配置）")


class ChatSource(BaseModel):
    """引用来源"""
    chunk_id: str
    content: str
    source: str
    score: float
    equipment_type: str = ""
    equipment_model: str = ""
    # PDF-A.5 聚群 A: 结构化字段
    page_number: Optional[int] = 0
    page_end: Optional[int] = 0
    chapter: Optional[str] = ""
    section_title: Optional[str] = ""
    section_type: Optional[str] = "text"
    section_level: Optional[int] = 0
    doc_id: Optional[str] = ""
    # PDF-B.5 聚群 B: 视觉理解字段
    image_description: Optional[str] = ""
    image_facts: Optional[str] = ""


class ChatResponseModel(BaseModel):
    """聊天响应"""
    intent: str = Field(..., description="maintenance | casual")
    confidence: float
    reason: str
    answer: str
    sources: List[ChatSource] = Field(default_factory=list, description="RAG 引用来源（仅 maintenance 有）")
    model: str
    latency_ms: float
    used_rag: bool = Field(..., description="是否走了 RAG 增强")
    retrieval_latency_ms: float = 0


@router.post("", response_model=ChatResponseModel)
async def chat(req: ChatRequestModel):
    """智能聊天 - 意图识别 + RAG 路由"""
    start = time.time()

    try:
        adapter = get_model_adapter()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"模型未就绪: {e}")

    # Step 1: 意图识别
    intent_res = await _classify_intent(adapter, req.message)
    intent = intent_res["intent"]
    confidence = intent_res["confidence"]
    reason = intent_res["reason"]

    # Step 2: 路由
    sources: List[Dict[str, Any]] = []
    used_rag = False
    retrieval_latency = 0.0
    answer_text = ""

    if intent == "maintenance" and confidence >= 0.5:
        sources, context, retrieval_latency, used_rag = await _route_and_retrieve(req.message, req.top_k)
        if sources or context:
            chat_req = _build_rag_request(req.history, req.message, context)
            answer_text = (await adapter.chat(chat_req)).content
        else:
            used_rag = False
            answer_text = await _casual_chat(adapter, req.message, req.history)
    else:
        answer_text = await _casual_chat(adapter, req.message, req.history)

    latency = (time.time() - start) * 1000
    return ChatResponseModel(
        intent=intent,
        confidence=confidence,
        reason=reason,
        answer=answer_text,
        sources=[ChatSource(**s) for s in sources],
        model=getattr(adapter, "model_name", "unknown"),
        latency_ms=round(latency, 1),
        used_rag=used_rag,
        retrieval_latency_ms=round(retrieval_latency, 1),
    )


# ============================================================
# 流式聊天（SSE）— ChatGPT 风格打字机效果
# ============================================================
class ChatStreamRequest(BaseModel):
    """流式聊天请求"""
    message: str = Field(..., min_length=1, max_length=2000)
    history: List[ChatTurnMessage] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=10)


def _sse_format(event: str, data: dict) -> str:
    """格式化为 SSE 协议: event: xxx\\ndata: {...}\\n\\n"""
    import json as json_mod
    return f"event: {event}\ndata: {json_mod.dumps(data, ensure_ascii=False)}\n\n"


async def _stream_chat(req: ChatStreamRequest):
    """SSE 流式聊天生成器"""
    import json as json_mod
    start = time.time()

    try:
        adapter = get_model_adapter()
    except Exception as e:
        yield _sse_format("error", {"message": f"模型未就绪: {e}"})
        return

    # ---- 1. 意图识别 ----
    intent_res = await _classify_intent(adapter, req.message)
    intent = intent_res["intent"]
    confidence = intent_res["confidence"]
    reason = intent_res["reason"]

    yield _sse_format("intent", {
        "intent": intent,
        "confidence": confidence,
        "reason": reason,
    })

    # ---- 2. 路由：复用 chat() 的 RAG 逻辑 ----
    sources: List[Dict[str, Any]] = []
    used_rag = False
    retrieval_latency = 0.0

    if intent == "maintenance" and confidence >= 0.5:
        sources, context, retrieval_latency, used_rag = await _route_and_retrieve(req.message, req.top_k)
        yield _sse_format("sources", {"sources": sources, "used_rag": used_rag})
    else:
        context = ""

    # ---- 3. 构造 ChatRequest ----
    if used_rag and (sources or context):
        chat_req = _build_rag_request(req.history, req.message, context)
    else:
        chat_req = _build_casual_request(req.history, req.message)

    # ---- 3. 流式生成 ----
    full_text = ""
    try:
        async for chunk in adapter.chat_text_stream(chat_req):
            full_text += chunk
            yield _sse_format("delta", {"content": chunk})
    except Exception as e:
        logger.error(f"流式生成失败: {e}")
        yield _sse_format("error", {"message": str(e)})
        return

    # ---- 4. 完成事件 ----
    latency = (time.time() - start) * 1000
    yield _sse_format("done", {
        "model": getattr(adapter, "model_name", "unknown"),
        "latency_ms": round(latency, 1),
        "used_rag": used_rag,
        "retrieval_latency_ms": round(retrieval_latency, 1),
        "total_chars": len(full_text),
    })


@router.post("/stream")
async def chat_stream(req: ChatStreamRequest):
    """流式聊天 SSE 端点

    协议：
    - event: intent     → 意图识别结果
    - event: sources    → 引用来源（仅 maintenance）
    - event: delta      → 文本增量（多次）
    - event: done       → 完成（model/latency 等）
    - event: error      → 错误
    """
    return StreamingResponse(
        _stream_chat(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ============================================================
# 聚群 C: 工具链 ReAct Agent 端点（SSE）
# ============================================================
class ChatAgentRequest(BaseModel):
    """工具链 Agent 请求"""
    message: str = Field(..., min_length=1, max_length=2000)
    history: List[ChatTurnMessage] = Field(default_factory=list)
    max_steps: int = Field(default=5, ge=1, le=10)


async def _stream_agent_chat(req: ChatAgentRequest):
    """聚群 C: ReAct Agent SSE 流"""
    from app.services.agent_service import AgentService
    import asyncio as _asyncio

    start = time.time()
    try:
        adapter = get_model_adapter()
    except Exception as e:
        yield _sse_format("error", {"message": f"模型未就绪: {e}"})
        return

    try:
        agent = AgentService(max_steps=req.max_steps)
    except Exception as e:
        yield _sse_format("error", {"message": f"Agent 初始化失败: {e}"})
        return

    # 构造 history 给 agent
    history_dicts = None
    if req.history:
        history_dicts = [
            {"role": h.role, "content": h.content} for h in req.history[-6:]
        ]

    final_answer = ""
    step_count = 0
    try:
        async for event in agent.run(req.message, history=history_dicts, adapter=adapter):
            step_count += 1
            if event.type == "answer":
                final_answer = event.data.get("content", "")
            yield _sse_format(event.type, event.data)
            # 给前端一点喘息时间
            await _asyncio.sleep(0)
    except Exception as e:
        logger.exception("Agent 流式失败")
        yield _sse_format("error", {"message": str(e)})
        return

    latency = (time.time() - start) * 1000
    yield _sse_format("done", {
        "model": getattr(adapter, "model_name", "unknown"),
        "latency_ms": round(latency, 1),
        "events_count": step_count,
        "final_answer": final_answer,
    })


@router.post("/agent")
async def chat_agent(req: ChatAgentRequest):
    """聚群 C: 工具链 ReAct Agent（SSE）

    协议：
    - event: thought      LLM 思考（content）
    - event: tool_call    工具调用 {id, name, arguments}
    - event: tool_result  工具返回 {id, name, ok, result}
    - event: answer       最终答案
    - event: error        错误
    - event: done         完成 {model, latency_ms, events_count, final_answer}
    """
    return StreamingResponse(
        _stream_agent_chat(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ============================================================
# 聚群 C: 评测端点（Eval Report）
# ============================================================
@router.get("/eval/run")
async def run_eval(top_k: int = 5, save_path: Optional[str] = None):
    """聚群 C: 跑评测黄金集，输出 JSON 报告

    Args:
        top_k: 检索 top-k（默认 5）
        save_path: 可选，保存到指定路径（默认 backend/logs/eval_report.json）
    """
    from app.services.eval.runner import run_evaluation, save_report
    try:
        report = await run_evaluation(top_k=top_k)
        if save_path:
            try:
                save_report(report, save_path)
            except Exception as e:
                logger.warning(f"保存评测报告失败: {e}")
        return report
    except Exception as e:
        logger.exception("评测失败")
        raise HTTPException(status_code=500, detail=f"评测失败: {e}")


@router.get("/eval/report")
async def get_eval_report(path: str = "logs/eval_report.json"):
    """聚群 C: 读取已保存的评测报告（默认 backend/logs/eval_report.json）"""
    from pathlib import Path as _P
    backend_root = _P(__file__).resolve().parents[3]
    full = backend_root / path
    if not full.exists():
        raise HTTPException(status_code=404, detail=f"报告不存在: {path}")
    try:
        import json as _json
        return _json.loads(full.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读报告失败: {e}")


async def _casual_chat(adapter, message: str, history: List[ChatTurnMessage]) -> str:
    """普通闲聊（无 RAG）"""
    # 构造多轮消息
    messages: List[ChatMessage] = []
    if history:
        for h in history[-6:]:  # 最多带 6 轮历史
            messages.append(ChatMessage(
                role=MessageRole.USER if h.role == "user" else MessageRole.ASSISTANT,
                content=h.content,
            ))
    messages.append(ChatMessage(role=MessageRole.USER, content=message))

    system_prompt = (
        "你是 A1 设备检修智能系统的对话助手。你可以正常回答用户问题，"
        "如果用户问的是设备检修/工业相关问题，请建议他描述具体设备类型、故障现象，"
        "以便系统用专业知识库回答。你可以闲聊、回答常识问题、帮助分析一般问题。"
    )
    response = await adapter.chat(ChatRequest(
        messages=messages,
        system_prompt=system_prompt,
        temperature=0.7,
        max_tokens=1500,
    ))
    return response.content


async def _keyword_fallback(query: str, top_k: int) -> tuple:
    """关键词降级 RAG（Milvus 不可用时）

    1. 从故障案例库按关键词匹配
    2. 从 SOP 库按设备类型匹配
    3. 关键词命中手册段落

    性能优化（H-Fix-3）：文件读磁盘 cache 到模块级 _CACHE，mtime 检测自动失效。
    之前每个请求都同步 read_text() 多次（2 个 JSON + N 个 MD），热路径下数量级提升。

    Returns: (sources, context_text)
    """
    from app.core.config import CASES_FILE, SOPS_FILE, MANUALS_DIR
    from app.utils.text import extract_keywords

    keywords = extract_keywords(query)

    # 1. 关键词命中案例（cache）
    cases = read_cached_json(CASES_FILE, default=[])

    matched_cases = []
    for c in cases:
        score = 0
        text = " ".join([
            c.get("title", ""),
            c.get("fault_description", ""),
            c.get("solution", ""),
            " ".join(c.get("tags", [])),
        ])
        for kw in keywords:
            if kw in text:
                score += 1
        if score > 0:
            matched_cases.append((score, c))

    matched_cases.sort(key=lambda x: -x[0])
    matched_cases = matched_cases[:top_k]

    sources = []
    context_parts = []

    for score, c in matched_cases:
        sources.append({
            "chunk_id": c["case_id"],
            "content": f"**{c['title']}**\n故障：{c['fault_description']}\n方案：{c['solution']}",
            "source": f"案例库/{c['case_id']}",
            "score": float(score),
            "equipment_type": c.get("equipment_type", ""),
            "equipment_model": c.get("equipment_model", ""),
            # PDF-A.5: 案例/SOP 无结构化字段
            "page_number": 0,
            "page_end": 0,
            "chapter": "",
            "section_title": "",
            "section_type": "text",
            "section_level": 0,
            "doc_id": "",
            # PDF-B.5: 案例无视觉理解字段
            "image_description": "",
            "image_facts": "",
        })
        context_parts.append(
            f"### 案例 {c['case_id']}：{c['title']}\n"
            f"设备：{c.get('equipment_type', '')} / {c.get('equipment_model', '')}\n"
            f"故障描述：{c.get('fault_description', '')}\n"
            f"解决方案：{c.get('solution', '')}\n"
        )

    # 2. 匹配 SOP（cache）
    sops = read_cached_json(SOPS_FILE, default=[])
    for s in sops:
        if any(kw in s.get("equipment_type", "") for kw in keywords) or \
           any(kw in s.get("name", "") for kw in keywords):
            sources.append({
                "chunk_id": s["sop_id"],
                "content": f"**{s['name']}** ({s['sop_id']})\n工具：{', '.join(s.get('tools', [])[:5])}\n步骤数：{len(s.get('steps', []))}",
                "source": f"SOP 库/{s['sop_id']}",
                "score": 0.5,
                "equipment_type": s.get("equipment_type", ""),
                "equipment_model": "",
                # PDF-A.5
                "page_number": 0,
                "page_end": 0,
                "chapter": "",
                "section_title": s.get("name", ""),
                "section_type": "text",
                "section_level": 0,
                "doc_id": "",
                # PDF-B.5
                "image_description": "",
                "image_facts": "",
            })
            context_parts.append(
                f"### SOP {s['sop_id']}：{s['name']}\n"
                f"设备：{s.get('equipment_type', '')}\n"
                f"检修等级：{s.get('maintenance_level', '')}\n"
                f"工具：{', '.join(s.get('tools', []))}\n"
                f"步骤数：{len(s.get('steps', []))}\n"
            )

    # 3. 关键词命中手册段落（manuals/*.md 按 ## 标题切分，cache）
    manuals = read_cached_manuals(MANUALS_DIR)
    import re as re_mod
    for stem, text in manuals.items():
        sections = re_mod.split(r'(?=^## )', text, flags=re_mod.MULTILINE)
        for sec in sections:
            sec = sec.strip()
            if len(sec) < 20:
                continue
            # 段落标题（第一行） + 内容
            first_line = sec.split('\n', 1)[0].strip()
            score = sum(1 for kw in keywords if kw in sec)
            if score > 0:
                sources.append({
                    "chunk_id": f"manual:{stem}#{hash(first_line) & 0xffff:#04x}",
                    "content": sec[:500],  # 限制每段 500 字
                    "source": f"手册/{stem}",
                    "score": float(score * 0.7),  # 手册权重略低
                    "equipment_type": "",
                    "equipment_model": "",
                    # PDF-A.5
                    "page_number": 0,
                    "page_end": 0,
                    "chapter": "",
                    "section_title": first_line,
                    "section_type": "text",
                    "section_level": 2,
                    "doc_id": f"md:{stem}",
                    # PDF-B.5
                    "image_description": "",
                    "image_facts": "",
                })
                context_parts.append(
                    f"### 手册《{stem}》 - {first_line}\n"
                    + sec[:400]
                )

    # 按 score 降序排，截 top_k
    sources.sort(key=lambda x: -x["score"])
    sources = sources[:top_k]
    # context 也按 sources 顺序取前 top_k 段
    context_parts = context_parts[:top_k]

    return sources, "\n".join(context_parts) if context_parts else ""


# ============================================================
# H-Fix-3: keyword_fallback 文件 cache（已抽到 app.services.keyword_cache 复用）
# ============================================================
from app.services.keyword_cache import invalidate as invalidate_keyword_cache


async def _answer_with_context(adapter, message: str, context: str, history: List[ChatTurnMessage]) -> str:
    """用 LLM 基于 context 生成带引用的答案"""
    messages: List[ChatMessage] = []
    if history:
        for h in history[-6:]:
            messages.append(ChatMessage(
                role=MessageRole.USER if h.role == "user" else MessageRole.ASSISTANT,
                content=h.content,
            ))

    system_prompt = """你是 A1 设备检修智能系统的专家助理。请严格基于下方提供的"参考案例与 SOP"回答用户问题。

要求：
1. 优先用参考信息回答，引用具体案例 ID 或 SOP 编号
2. 如果参考信息不充分，可补充你的专业知识，但要明确标注
3. 答案结构清晰：先给结论，再给步骤，最后给预防建议
4. 涉及安全时必须加警示"""

    user_content = f"""参考案例与 SOP：
{context if context else '（未找到直接匹配的参考）'}

用户问题：{message}

请基于以上参考给出专业回答。"""

    messages.append(ChatMessage(role=MessageRole.USER, content=user_content))
    response = await adapter.chat(ChatRequest(
        messages=messages,
        system_prompt=system_prompt,
        temperature=0.3,
        max_tokens=2000,
    ))
    return response.content
