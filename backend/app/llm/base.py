"""
模型适配层 - 统一接口
所有 LLM 适配器（云端/本地）都必须实现这个接口
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
from enum import Enum


class MessageRole(str, Enum):
    """消息角色"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ChatMessage:
    """单条聊天消息"""
    role: MessageRole
    content: Union[str, List[Dict[str, Any]]]  # 文本或多模态内容（图像/视频）


@dataclass
class ChatRequest:
    """聊天请求"""
    messages: List[ChatMessage]
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 0.9
    system_prompt: Optional[str] = None
    stream: bool = False
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatResponse:
    """聊天响应"""
    content: str
    model: str
    usage: Dict[str, int] = field(default_factory=dict)  # tokens
    finish_reason: str = "stop"
    raw: Optional[Any] = None


class ModelAdapter(ABC):
    """模型适配器抽象基类

    统一接口: chat / embed / parse_document
    实现: BailianAdapter (云端) / LocalQwen2VLAdapter (本地)
    """

    @property
    @abstractmethod
    def mode(self) -> str:
        """返回模式名: 'cloud' | 'local'"""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """返回具体模型名"""
        ...

    @abstractmethod
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """多模态对话

        Args:
            request: 聊天请求，支持文本 + 图像 + 视频

        Returns:
            ChatResponse: 模型回复
        """
        ...

    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """文本向量化

        Args:
            texts: 文本列表

        Returns:
            向量列表（每个元素是 dim 维浮点数列表）
        """
        ...

    @abstractmethod
    async def parse_document(self, file_path: str) -> str:
        """文档解析（OCR + 排版还原）

        Args:
            file_path: 文档路径（PDF/Word/Image）

        Returns:
            解析后的 Markdown/纯文本
        """
        ...

    async def health_check(self) -> bool:
        """健康检查，默认实现：发个 hello"""
        try:
            resp = await self.chat(ChatRequest(
                messages=[ChatMessage(role=MessageRole.USER, content="hello")],
                max_tokens=10,
            ))
            return bool(resp.content)
        except Exception:
            return False
