"""
工具抽象 + 注册表（聚群 C）

设计：
- BaseTool: 子类必须实现 name / description / parameters / __call__
- to_openai_schema() 自动生成 OpenAI function calling 格式
- ToolRegistry: 全局工具注册表，支持按名查找 + 执行
- 失败容错：执行失败返回 {"error": ...} 字符串，不抛异常阻塞 ReAct

为什么不直接用 LangChain Tools：
- 项目里 langchain 已装但全代码 0 引用
- 自己实现 ~80 行就够用，避免引入新抽象层
- 调试可控、序列化简单
"""
from __future__ import annotations

import asyncio
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from loguru import logger


# ============================================================
# BaseTool 抽象
# ============================================================
class BaseTool(ABC):
    """工具基类

    子类用法：
        class MyTool(BaseTool):
            name = "my_tool"
            description = "..."
            parameters = {
                "type": "object",
                "properties": {"x": {"type": "string", "description": "..."}},
                "required": ["x"]
            }

            async def __call__(self, x: str) -> str:
                return f"got {x}"
    """

    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {},
        "required": [],
    })

    @abstractmethod
    async def __call__(self, **kwargs) -> Any:
        """工具执行入口（子类实现）"""
        ...

    def to_openai_schema(self) -> Dict[str, Any]:
        """生成 OpenAI function calling 格式的 schema

        Returns:
            {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def safe_call(self, **kwargs) -> Dict[str, Any]:
        """容错调用：失败返回 {"error": str, "tool": name}，不抛异常"""
        try:
            result = await self.__call__(**kwargs)
            return {"ok": True, "tool": self.name, "result": result}
        except Exception as e:
            logger.warning(f"⚠️ 工具 {self.name} 执行失败: {e}")
            return {"ok": False, "tool": self.name, "error": str(e)}


# ============================================================
# ToolRegistry
# ============================================================
class ToolRegistry:
    """工具注册表

    单例模式（全局共享）。
    支持：
    - register(tool) 注册一个工具
    - unregister(name) 注销
    - get(name) 查找
    - to_openai_tools() 导出所有工具的 OpenAI schema
    - execute(name, args) 同步异步执行 + 容错
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if not tool.name:
            raise ValueError(f"工具 {type(tool).__name__} 必须设置 name")
        if tool.name in self._tools:
            logger.warning(f"工具 {tool.name} 已存在，将被覆盖")
        self._tools[tool.name] = tool
        logger.info(f"🔧 工具注册: {tool.name} — {tool.description[:50]}")

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_names(self) -> List[str]:
        return list(self._tools.keys())

    def to_openai_tools(self) -> List[Dict[str, Any]]:
        return [t.to_openai_schema() for t in self._tools.values()]

    async def execute(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """执行一个工具（容错）"""
        tool = self.get(name)
        if tool is None:
            return {"ok": False, "tool": name, "error": f"未注册的工具: {name}"}
        return await tool.safe_call(**args)


# ============================================================
# 同步工具适配（把同步函数包装成异步 BaseTool）
# ============================================================
class FunctionTool(BaseTool):
    """把普通函数包装成工具（同步函数自动放到线程池跑）

    用法：
        def my_search(query: str) -> str:
            return f"result for {query}"

        tool = FunctionTool(
            name="search",
            description="搜索内容",
            parameters={"type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"]},
            func=my_search,
        )
    """

    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        func: Callable[..., Any],
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self._func = func
        self._is_coro = inspect.iscoroutinefunction(func)

    async def __call__(self, **kwargs) -> Any:
        if self._is_coro:
            return await self._func(**kwargs)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._func(**kwargs))
