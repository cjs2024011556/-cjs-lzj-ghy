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
        logger.error(f"文本检索失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/multimodal", response_model=RetrievalResponse)
async def retrieve_multimodal(
    query: str = Form(...),
    equipment_model: Optional[str] = Form(default=None),
    image: Optional[UploadFile] = File(default=None),
    top_k: int = Form(default=5),
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
        logger.error(f"多模态检索失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def retrieval_stats():
    """检索服务统计"""
    try:
        count = await _service.indexer.count()
        return {"indexed_chunks": count}
    except Exception as e:
        return {"indexed_chunks": -1, "error": str(e)}
