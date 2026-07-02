"""
LLM 适配器测试（Mock 模式）
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.llm.base import (
    ModelAdapter, ChatRequest, ChatResponse, ChatMessage, MessageRole
)


class MockAdapter(ModelAdapter):
    """用于测试的 Mock 适配器"""
    @property
    def mode(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-model"

    async def chat(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(
            content=f"Mock response: {request.messages[0].content}",
            model=self.model_name,
            usage={"total_tokens": 10},
        )

    async def embed(self, texts):
        return [[0.1] * 1024 for _ in texts]

    async def parse_document(self, file_path: str) -> str:
        return f"Mock parsed: {file_path}"


class TestModelAdapter:
    @pytest.mark.asyncio
    async def test_chat(self):
        adapter = MockAdapter()
        req = ChatRequest(
            messages=[ChatMessage(role=MessageRole.USER, content="hello")],
        )
        resp = await adapter.chat(req)
        assert resp.content == "Mock response: hello"
        assert resp.model == "mock-model"
        assert resp.usage["total_tokens"] == 10

    @pytest.mark.asyncio
    async def test_embed(self):
        adapter = MockAdapter()
        vecs = await adapter.embed(["text1", "text2"])
        assert len(vecs) == 2
        assert len(vecs[0]) == 1024

    @pytest.mark.asyncio
    async def test_health_check(self):
        adapter = MockAdapter()
        assert await adapter.health_check() is True

    def test_mode(self):
        adapter = MockAdapter()
        assert adapter.mode == "mock"
        assert adapter.model_name == "mock-model"


class TestChatRequest:
    def test_default_values(self):
        req = ChatRequest(messages=[])
        assert req.temperature == 0.7
        assert req.max_tokens == 2048
        assert req.top_p == 0.9
        assert req.stream is False
        assert req.system_prompt is None
