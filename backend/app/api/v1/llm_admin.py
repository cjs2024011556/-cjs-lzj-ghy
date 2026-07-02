"""
LLM 管理接口
- 查询当前模式
- 切换 cloud/local
- 健康检查
- 调用测试
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List

from app.llm.factory import get_model_adapter, switch_mode
from app.llm.base import ChatRequest, ChatMessage, MessageRole
from app.core.config import settings
from app.core.logger import logger

router = APIRouter()


class LLMStatusResponse(BaseModel):
    mode: str
    model: str
    available: bool
    message: str


class SwitchModeRequest(BaseModel):
    mode: str = Field(..., pattern="^(cloud|local)$", description="目标模式")


class ChatTestRequest(BaseModel):
    message: str = Field(..., description="测试消息")
    image_url: Optional[str] = Field(default=None, description="可选图像 URL")


class ChatTestResponse(BaseModel):
    content: str
    model: str
    usage: dict
    latency_ms: float


@router.get("/status", response_model=LLMStatusResponse)
async def get_status():
    """获取当前 LLM 状态"""
    try:
        adapter = get_model_adapter()
        healthy = await adapter.health_check()
        return LLMStatusResponse(
            mode=adapter.mode,
            model=adapter.model_name,
            available=healthy,
            message="就绪" if healthy else "模型无响应",
        )
    except Exception as e:
        return LLMStatusResponse(
            mode=settings.LLM_MODE,
            model="unknown",
            available=False,
            message=str(e),
        )


@router.post("/switch")
async def switch_llm_mode(req: SwitchModeRequest):
    """切换 LLM 模式（cloud ⇄ local）"""
    try:
        adapter = switch_mode(req.mode)
        return {
            "success": True,
            "mode": adapter.mode,
            "model": adapter.model_name,
        }
    except Exception as e:
        logger.error(f"切换模式失败: {e}")
        raise HTTPException(status_code=500, detail=f"切换失败: {e}")


@router.post("/test", response_model=ChatTestResponse)
async def test_chat(req: ChatTestRequest):
    """测试 LLM 调用（debug 用）"""
    import time
    try:
        adapter = get_model_adapter()
        messages = [ChatMessage(role=MessageRole.USER, content=req.message)]
        request = ChatRequest(messages=messages, max_tokens=200)

        start = time.time()
        response = await adapter.chat(request)
        latency = (time.time() - start) * 1000

        return ChatTestResponse(
            content=response.content,
            model=response.model,
            usage=response.usage,
            latency_ms=round(latency, 1),
        )
    except Exception as e:
        logger.error(f"LLM 测试失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embed/test")
async def test_embed(texts: List[str]):
    """测试 Embedding"""
    try:
        from app.llm.factory import get_embedder
        embedder = get_embedder()
        vectors = await embedder.embed(texts)
        return {
            "count": len(vectors),
            "dim": len(vectors[0]) if vectors else 0,
            "first_5_dims": vectors[0][:5] if vectors else [],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
