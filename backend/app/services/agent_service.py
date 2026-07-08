"""
ReAct Agent（聚群 C 工具链核心）

流程（单轮 ReAct 循环）：
  1. 构造 ChatRequest（含 tools schema）
  2. 调 LLM
  3. 解析响应：
     - 若有 tool_calls → 执行工具 → 把结果作为 tool role 消息回填 → 回到步骤 2
     - 若无 tool_calls → 提取 content 作为最终答案 → 退出
  4. 上限：max_steps（默认 5），防止死循环

事件流（用于 SSE 推送）：
  - {"type": "thought", "content": "..."}             # LLM 思考（content）
  - {"type": "tool_call", "name": "...", "args": {...}} # 调工具
  - {"type": "tool_result", "name": "...", "result": ...} # 工具返回
  - {"type": "answer", "content": "..."}              # 最终答案
  - {"type": "done", "steps": N}                      # 结束

为什么不用 LangGraph / autogen：
- 项目里都没装
- 单 ReAct 循环 ~150 行可控
- 后续要做复杂多 agent 再考虑
"""
from __future__ import annotations

import json as _json
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, List, Optional

from loguru import logger

from app.services.tools import ToolRegistry, get_default_registry

# 仅做类型注解；运行时按需 import（避免触发 dashscope 链）
if TYPE_CHECKING:
    from app.llm.base import ChatRequest, ChatResponse, ChatMessage, MessageRole, ToolCall


# ============================================================
# Agent 事件（用于 SSE / 日志 / 测试断言）
# ============================================================
@dataclass
class AgentEvent:
    """Agent 循环产出的一条事件"""
    type: str                                # thought / tool_call / tool_result / answer / done / error
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, **self.data}


# ============================================================
# ReAct 提示词
# ============================================================
REACT_SYSTEM_PROMPT = """你是 A1 设备检修智能助手，具备调用工具获取精确信息的能力。

工作流程：
1. 理解用户问题，判断是否需要调工具
2. 若需要，从可用工具列表中选一个 + 给参数
3. 拿到工具结果后，整合信息给最终答案
4. 答案必须基于工具结果，不要编造

回答要求：
- 中文回答，专业、简洁
- 引用具体页码 / 章节 / 报警码
- 必要时列出关键参数（温度/压力/电压等）
- 不要重复工具已经返回的内容
"""


# ============================================================
# Agent Service
# ============================================================
class AgentService:
    """ReAct Agent 服务

    用法：
        agent = AgentService()
        async for event in agent.run("电机过热怎么排查？"):
            print(event)
    """

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        max_steps: int = 5,
        model_override: Optional[str] = None,
    ):
        self.registry = registry or get_default_registry()
        self.max_steps = max_steps
        self.model_override = model_override
        # 循环检测：最近 N 个 tool_call 签名如果重复出现 → 提前终止
        self._loop_window = 3

    async def run(
        self,
        query: str,
        history: Optional[List[Dict[str, Any]]] = None,
        adapter=None,
    ) -> AsyncIterator[AgentEvent]:
        """ReAct 循环：单 query → 多次 tool_call → 最终 answer

        Args:
            query: 用户问题
            history: 历史消息 [{"role": "user/assistant", "content": "..."}]
            adapter: 模型适配器（None 用默认）

        Yields:
            AgentEvent 序列
        """
        if adapter is None:
            from app.llm.factory import get_model_adapter
            adapter = get_model_adapter()

        # 直接按文件路径 import 避免触发 app.llm 包级 __init__（不需要 dashscope）
        # agent_service.py 在 backend/app/services/ → llm/base.py 在 backend/app/llm/
        import importlib.util as _ilu
        import os as _os
        _base_path = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            "llm", "base.py",
        )
        _spec = _ilu.spec_from_file_location("_agent_llm_base", _base_path)
        _llm_base = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_llm_base)
        ChatRequest = _llm_base.ChatRequest
        ChatMessage = _llm_base.ChatMessage
        MessageRole = _llm_base.MessageRole

        # 1. 构造初始 messages
        messages: List[ChatMessage] = []
        if history:
            for h in history:
                messages.append(ChatMessage(
                    role=MessageRole(h.get("role", "user")),
                    content=h.get("content", ""),
                ))
        messages.append(ChatMessage(role=MessageRole.USER, content=query))

        # 2. 工具签名历史（用于循环检测）
        recent_calls: List[str] = []

        for step in range(self.max_steps):
            # 3. 调 LLM
            try:
                request = ChatRequest(
                    messages=messages,
                    system_prompt=REACT_SYSTEM_PROMPT,
                    temperature=0.3,
                    max_tokens=1500,
                    tools=self.registry.to_openai_tools(),
                    tool_choice="auto",
                )
                response = await adapter.chat(request)
            except Exception as e:
                logger.exception("Agent LLM 调用失败")
                yield AgentEvent("error", {"message": str(e)})
                return

            # 4. 处理响应
            tool_calls = response.tool_calls

            # 4a. 无 tool_call → 提取最终答案
            if not tool_calls:
                if response.content:
                    yield AgentEvent("thought", {"content": response.content, "step": step})
                    yield AgentEvent("answer", {"content": response.content, "step": step})
                else:
                    yield AgentEvent("error", {"message": "LLM 返回空内容"})
                yield AgentEvent("done", {"steps": step + 1, "max_steps": self.max_steps})
                return

            # 4b. 有 tool_call → 思考 + 执行
            if response.content:
                yield AgentEvent("thought", {"content": response.content, "step": step})

            for tc in tool_calls:
                # 循环检测
                sig = f"{tc.name}({_json.dumps(tc.arguments, sort_keys=True, ensure_ascii=False)})"
                if sig in recent_calls[-self._loop_window:]:
                    logger.warning(f"🔁 循环检测: {sig}")
                    yield AgentEvent("error", {
                        "message": f"工具 {tc.name} 重复调用 {self._loop_window} 次，终止循环",
                        "tool": tc.name,
                    })
                    yield AgentEvent("done", {"steps": step + 1, "loop_detected": True})
                    return
                recent_calls.append(sig)

                yield AgentEvent("tool_call", {
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments,
                    "step": step,
                })

                # 5. 执行工具
                result = await self.registry.execute(tc.name, tc.arguments)
                yield AgentEvent("tool_result", {
                    "id": tc.id,
                    "name": tc.name,
                    "ok": result.get("ok", False),
                    "result": result.get("result", result.get("error", "")),
                    "step": step,
                })

                # 6. 工具结果作为 tool role 消息回填
                tool_content = _json.dumps(
                    result.get("result", result.get("error", "")),
                    ensure_ascii=False,
                )
                if len(tool_content) > 6000:
                    tool_content = tool_content[:6000] + "..."

                # assistant 消息（含 tool_calls 信息）
                messages.append(ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content="",
                ))
                # tool 消息（含 tool_call_id）
                messages.append(ChatMessage(
                    role=MessageRole.TOOL,
                    content=tool_content,
                    tool_call_id=tc.id,
                    name=tc.name,
                ))

        # 7. 达到 max_steps → 给一个总结性兜底答案
        yield AgentEvent("error", {
            "message": f"达到最大步数 {self.max_steps}，未得出最终答案",
        })
        yield AgentEvent("done", {"steps": self.max_steps, "max_steps_reached": True})
