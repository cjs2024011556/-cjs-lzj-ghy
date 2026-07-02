"""
E2E Test 5: Rerank（U2）— 排序正确性 + 失败降级

业务契约（来自 app/llm/bailian.py:rerank）：
- 输入：query + List[docs] + top_n
- 输出：按相关性降序的 index 列表
- 异常路径：失败时返回原顺序 [0..min(len, top_n)]
"""
import pytest
from unittest.mock import patch, MagicMock

from app.core.config import settings


SKIP_IF_NO_LLM = not settings.CLOUD_LLM.api_key
pytestmark = pytest.mark.skipif(
    SKIP_IF_NO_LLM,
    reason="DASHSCOPE_API_KEY 未配置，跳过 LLM 依赖的 e2e 测试",
)


class TestRerankBehavior:
    """真实云端：rerank 应把相关文档排前"""

    async def test_welding_query_promotes_relevant_doc(self):
        """关于'焊接机器人飞溅'的查询，相关手册应排第 1"""
        from app.llm.bailian import BailianAdapter

        docs = [
            "焊接机器人保护气体流量优化指南",   # idx 0: 强相关
            "数控机床主轴日常维护流程",          # idx 1: 无关
            "液压泵振动分析 SOP",               # idx 2: 无关
            "焊接飞溅过大原因分析与解决方案",    # idx 3: 强相关
        ]
        adapter = BailianAdapter()
        ranked = await adapter.rerank(
            query="焊接机器人飞溅大怎么处理",
            documents=docs,
            top_n=2,
        )

        # 返回应是索引列表
        assert isinstance(ranked, list)
        assert len(ranked) == 2
        # rerank 后排前的应是 idx 0 或 idx 3（焊接相关）
        top_idx = ranked[0]
        assert top_idx in (0, 3), f"rerank 应把焊接相关文档排前，实际 top1={docs[top_idx]}"

    async def test_empty_documents_returns_empty(self):
        from app.llm.bailian import BailianAdapter
        adapter = BailianAdapter()
        ranked = await adapter.rerank(query="测试", documents=[], top_n=5)
        assert ranked == []


class TestRerankFallback:
    """API 异常时的降级逻辑（不依赖真实云端）"""

    async def test_exception_returns_original_order(self):
        """TextReRank.call 抛异常 → rerank 返回原顺序"""
        from app.llm.bailian import BailianAdapter

        # Monkey-patch dashscope.TextReRank.call 抛异常
        # 用 lazy import 找 TextReRank 模块的 call
        import dashscope
        from dashscope import TextReRank

        original_call = TextReRank.call
        try:
            # patch 成抛异常
            with patch.object(TextReRank, "call", side_effect=RuntimeError("模拟 rerank API 失败")):
                adapter = BailianAdapter()
                docs = ["文档 A", "文档 B", "文档 C"]
                ranked = await adapter.rerank(query="测试", documents=docs, top_n=2)

                # 降级：返回 [0, 1]（原顺序的前 2 个）
                assert ranked == [0, 1], f"异常时应返回原顺序，实际: {ranked}"
        finally:
            # 恢复（patch context manager 自动恢复）
            pass  # noqa

    async def test_api_error_response_returns_original_order(self):
        """TextReRank.call 返回 status_code!=200 → 降级"""
        from app.llm.bailian import BailianAdapter
        from dashscope import TextReRank

        # 构造 mock 响应
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.code = "InvalidParameter"
        mock_resp.message = "bad request"

        with patch.object(TextReRank, "call", return_value=mock_resp):
            adapter = BailianAdapter()
            ranked = await adapter.rerank(
                query="测试",
                documents=["a", "b", "c"],
                top_n=3,
            )
            # 降级返回原顺序 [0, 1, 2]
            assert ranked == [0, 1, 2]


class TestRerankSettings:
    """配置驱动的 rerank 行为"""

    def test_rerank_model_configurable(self):
        """RERANK_MODEL 应可配置（默认 gte-rerank）"""
        from app.core.config import settings
        assert hasattr(settings, "RERANK_MODEL")
        assert isinstance(settings.RERANK_MODEL, str)
        assert len(settings.RERANK_MODEL) > 0

    def test_rerank_enabled_toggleable(self):
        """RERANK_ENABLED 应为 bool，可关掉触发降级"""
        from app.core.config import settings
        assert hasattr(settings, "RERANK_ENABLED")
        assert isinstance(settings.RERANK_ENABLED, bool)
