"""
工具框架 + 4 个聚群 C 工具（聚群 C 工具链核心）

目录：
- base.py: BaseTool 抽象 + ToolRegistry 注册表
- kb_tools.py: 4 工具实现（search_kb / lookup_chunk / describe_image / query_graph）

使用：
    from app.services.tools import get_default_registry
    registry = get_default_registry()
    tools_schema = registry.to_openai_tools()
    result = await registry.execute("search_kb", {"query": "油温过高"})
"""
from app.services.tools.base import BaseTool, ToolRegistry
from app.services.tools.kb_tools import (
    SearchKBTool, LookupChunkTool, DescribeImageTool, QueryGraphTool,
    build_default_registry, get_default_registry,
)

__all__ = [
    "BaseTool",
    "ToolRegistry",
    "SearchKBTool",
    "LookupChunkTool",
    "DescribeImageTool",
    "QueryGraphTool",
    "build_default_registry",
    "get_default_registry",
]
