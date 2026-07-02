"""
健康检查接口
"""
from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime

from app.core.config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    env: str
    llm_mode: str
    llm_model: str
    timestamp: str


@router.get("", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    from app.llm.factory import get_model_adapter

    try:
        adapter = get_model_adapter()
        model_name = adapter.model_name
    except Exception:
        model_name = "uninitialized"

    return HealthResponse(
        status="ok",
        app=settings.APP_NAME,
        version="0.1.0",
        env=settings.APP_ENV,
        llm_mode=settings.LLM_MODE,
        llm_model=model_name,
        timestamp=datetime.now().isoformat(),
    )


@router.get("/ping")
async def ping():
    return {"pong": True}
