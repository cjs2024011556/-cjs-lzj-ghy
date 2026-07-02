"""LLM 模型适配层"""
from app.llm.base import ModelAdapter, ChatRequest, ChatResponse, ChatMessage, MessageRole
from app.llm.factory import get_model_adapter, switch_mode

__all__ = [
    "ModelAdapter",
    "ChatRequest",
    "ChatResponse",
    "ChatMessage",
    "MessageRole",
    "get_model_adapter",
    "switch_mode",
]
