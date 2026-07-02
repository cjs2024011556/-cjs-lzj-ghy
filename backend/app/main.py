"""
A1 设备检修智能系统 - FastAPI 入口
基于多模态大模型技术的设备检修知识检索与作业系统

运行: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
import time

from app.core.config import settings
from app.core.logger import setup_logger
from app.api.v1 import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动
    setup_logger()
    logger.info(f"🚀 {settings.APP_NAME} 启动中...")
    logger.info(f"📦 环境: {settings.APP_ENV}")
    logger.info(f"🤖 LLM 模式: {settings.LLM_MODE}")
    if settings.LLM_MODE == "cloud":
        logger.info(f"☁️  云端模型: {settings.CLOUD_LLM.model}")
    else:
        logger.info(f"💻 本地模型: {settings.LOCAL_LLM.model_path}")

    yield

    # 关闭
    try:
        from app.llm.factory import get_model_adapter
        adapter = get_model_adapter()
        if hasattr(adapter, "aclose"):
            await adapter.aclose()
    except Exception as e:
        logger.warning(f"关闭适配器时出错（可忽略）: {e}")
    logger.info(f"🛑 {settings.APP_NAME} 关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    description="基于多模态大模型技术的设备检修知识检索与作业系统",
    version="0.1.0",
    docs_url="/docs" if settings.APP_DEBUG else None,
    redoc_url="/redoc" if settings.APP_DEBUG else None,
    openapi_url="/openapi.json" if settings.APP_DEBUG else None,
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = (time.time() - start) * 1000
    logger.info(
        f"{request.method} {request.url.path} → {response.status_code} ({duration:.1f}ms)"
    )
    response.headers["X-Process-Time"] = f"{duration:.1f}ms"
    return response


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"未捕获异常: {request.url.path} - {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "detail": str(exc) if settings.APP_DEBUG else None,
        },
    )


# 注册路由
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": settings.APP_NAME,
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "llm_mode": settings.LLM_MODE,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_DEBUG,
    )
