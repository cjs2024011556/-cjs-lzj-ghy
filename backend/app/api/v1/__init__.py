"""V1 API 路由聚合"""
from fastapi import APIRouter

from app.api.v1 import health, retrieval, operation_guide, knowledge, llm_admin, audio, graph, chat, constants

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["健康检查"])
api_router.include_router(llm_admin.router, prefix="/llm", tags=["LLM 管理"])
api_router.include_router(audio.router, prefix="/audio", tags=["5 模型-语音/全模态"])
api_router.include_router(retrieval.router, prefix="/retrieval", tags=["多模态检索"])
api_router.include_router(operation_guide.router, prefix="/operation-guide", tags=["作业指引"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["知识管理"])
api_router.include_router(graph.router, prefix="/graph", tags=["故障图谱"])
api_router.include_router(chat.router, prefix="/chat", tags=["智能对话"])
api_router.include_router(constants.router, prefix="/constants", tags=["共享常量"])
