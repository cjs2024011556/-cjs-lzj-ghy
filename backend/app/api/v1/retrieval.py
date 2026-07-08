"""
多模态知识检索 API（F2）
支持文本 / 图像 / 设备型号输入，跨模态语义检索
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
from pathlib import Path
import shutil
import time

from app.services.retrieval_service import RetrievalService
from app.core.config import settings
from app.core.logger import logger

router = APIRouter()

# 全局 service 实例
_service = RetrievalService()


# ============================================================
# H-Fix-4: 错误响应脱敏 — 不把内部 detail 裸传给前端
# ============================================================
def _safe_http_exception(e: Exception, op: str) -> HTTPException:
    """分类异常 → 脱敏 HTTP 响应

    - ValueError / TypeError                  → 400 (用户输入不合法)
    - ConnectionError / TimeoutError          → 503 (后端服务不可用)
    - pymilvus.exceptions.MilvusException     → 503 (向量库不可用)
    - 其他                                     → 500 (内部错误)

    完整堆栈用 logger.exception 记录（保留调试能力），detail 仅给前端友好提示。
    绝不暴露：Milvus 连接串、文件路径、SQL、内部堆栈。
    """
    # Milvus 不可用（最常见的现场：Milvus 服务没启动 / 容器挂了）
    try:
        from pymilvus.exceptions import MilvusException
        if isinstance(e, MilvusException):
            logger.error(f"{op} Milvus 不可用: {type(e).__name__}: {e}")
            return HTTPException(status_code=503, detail=f"{op}依赖的向量数据库暂不可用，请检查 Milvus 服务后重试")
    except ImportError:
        pass  # pymilvus 未装（理论上不会发生，因为能 import 才能触发此错误）

    if isinstance(e, (ValueError, TypeError)):
        logger.warning(f"{op} 参数错误: {type(e).__name__}: {e}")
        return HTTPException(status_code=400, detail=f"{op}参数不合法")
    if isinstance(e, (ConnectionError, TimeoutError)):
        logger.error(f"{op} 后端服务不可用: {type(e).__name__}: {e}")
        return HTTPException(status_code=503, detail=f"{op}依赖的服务暂时不可用，请稍后重试")
    logger.exception(f"{op} 内部错误")
    return HTTPException(status_code=500, detail=f"{op}失败，请稍后重试")


class RetrievalRequest(BaseModel):
    query: str = Field(..., description="检索文本")
    equipment_model: Optional[str] = Field(default=None, description="设备型号")
    top_k: int = Field(default=5, ge=1, le=20)


class RetrievalHit(BaseModel):
    chunk_id: str
    content: str
    source: str
    doc_type: str
    equipment_type: str
    equipment_model: str
    score: float
    chunk_index: int
    # PDF-A.5 聚群 A: 结构化字段（透传自 Milvus）
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


class RetrievalResponse(BaseModel):
    query: str
    answer: str
    hits: List[RetrievalHit]
    model: str
    latency_ms: float
    usage: dict = {}


@router.post("/text", response_model=RetrievalResponse)
async def retrieve_by_text(req: RetrievalRequest):
    """纯文本检索"""
    try:
        result = await _service.retrieve(
            query=req.query,
            equipment_model=req.equipment_model,
            top_k=req.top_k,
        )
        return RetrievalResponse(
            query=req.query,
            answer=result["answer"],
            hits=[RetrievalHit(**h) for h in result["hits"]],
            model=result["model"],
            latency_ms=result["latency_ms"],
            usage=result.get("usage", {}),
        )
    except Exception as e:
        raise _safe_http_exception(e, "文本检索")


@router.post("/multimodal", response_model=RetrievalResponse)
async def retrieve_multimodal(
    query: str = Form(...),
    equipment_model: Optional[str] = Form(default=None),
    image: Optional[UploadFile] = File(default=None),
    top_k: int = Form(default=5, ge=1, le=20),  # UPGRADE-4: 与 /text 端点对齐范围校验
):
    """多模态检索（文本 + 图像）"""
    image_path = None
    try:
        if image:
            # 保存上传图像
            upload_dir = Path(settings.UPLOAD_DIR) / "queries"
            upload_dir.mkdir(parents=True, exist_ok=True)
            image_path = upload_dir / f"{int(time.time())}_{image.filename}"
            with open(image_path, "wb") as f:
                shutil.copyfileobj(image.file, f)

        result = await _service.retrieve(
            query=query,
            image_path=str(image_path) if image_path else None,
            equipment_model=equipment_model,
            top_k=top_k,
        )
        return RetrievalResponse(
            query=query,
            answer=result["answer"],
            hits=[RetrievalHit(**h) for h in result["hits"]],
            model=result["model"],
            latency_ms=result["latency_ms"],
            usage=result.get("usage", {}),
        )
    except Exception as e:
        raise _safe_http_exception(e, "多模态检索")


@router.get("/stats")
async def retrieval_stats():
    """检索服务统计"""
    try:
        count = await _service.indexer.count()
        return {"indexed_chunks": count}
    except Exception as e:
        # H-Fix-4: stats 错误也脱敏 — 内部错误不暴露给前端
        logger.exception("检索服务统计失败")
        return {"indexed_chunks": -1, "error": "统计服务暂时不可用"}
