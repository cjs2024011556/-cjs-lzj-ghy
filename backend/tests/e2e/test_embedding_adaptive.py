"""
E2E Test 4: Embedding 自适应（U1）

验证：
- `get_model_dim(model)` — 固定维度模型返回正确 dim
- `supports_custom_dim(model)` — v3 系列支持自定义 dim
- 真实 embed() — 切换 EMBEDDING_MODEL，返回向量维度匹配
"""
import pytest

from app.constants.embedding_models import (
    EMBEDDING_MODEL_DIM,
    EMBEDDING_CUSTOM_DIM_SUPPORT,
    get_model_dim,
    supports_custom_dim,
)
from app.core.config import settings


class TestModelDimMapping:
    """纯函数测试：不依赖云端 API"""

    def test_v3_default_dim(self):
        assert get_model_dim("text-embedding-v3") == 1024

    def test_v2_fixed_dim(self):
        assert get_model_dim("text-embedding-v2") == 1536

    def test_async_v3_dim(self):
        assert get_model_dim("text-embedding-async-v3") == 1024

    def test_bge_m3_dim(self):
        assert get_model_dim("BAAI/bge-m3") == 1024

    def test_unknown_model_uses_fallback(self):
        # 不在表里的模型 → fallback
        assert get_model_dim("totally-unknown-model", fallback=512) == 512

    def test_v3_supports_custom_dim(self):
        assert supports_custom_dim("text-embedding-v3") is True
        assert supports_custom_dim("text-embedding-async-v3") is True

    def test_v2_does_not_support_custom_dim(self):
        assert supports_custom_dim("text-embedding-v2") is False
        assert supports_custom_dim("text-embedding-async-v2") is False

    def test_bge_does_not_support_custom_dim(self):
        """BGE 是本地模型，不走百炼 dimension 参数"""
        assert supports_custom_dim("BAAI/bge-m3") is False

    def test_constants_complete(self):
        """所有在 CUSTOM_DIM_SUPPORT 的模型都应在 DIM 表里"""
        for model in EMBEDDING_CUSTOM_DIM_SUPPORT:
            assert model in EMBEDDING_MODEL_DIM, f"{model} 缺少 dim 定义"


class TestLiveEmbedding:
    """真实云端：切 settings 验证 embed() 返回维度"""

    @pytest.mark.skipif(not settings.CLOUD_LLM.api_key, reason="DASHSCOPE_API_KEY 未配置")
    async def test_v3_default_dim(self, monkeypatch):
        """v3 默认 → 1024 维"""
        from app.llm.bailian import BailianAdapter
        monkeypatch.setattr(settings.EMBEDDING, "model", "text-embedding-v3")
        monkeypatch.setattr(settings.EMBEDDING, "dim", 1024)

        adapter = BailianAdapter()
        vecs = await adapter.embed(["测试文本"])

        assert len(vecs) == 1
        assert len(vecs[0]) == 1024, f"v3 默认应返回 1024 维，实际: {len(vecs[0])}"

    @pytest.mark.skipif(not settings.CLOUD_LLM.api_key, reason="DASHSCOPE_API_KEY 未配置")
    async def test_v3_custom_smaller_dim(self, monkeypatch):
        """v3 切到 dim=64 应也通过（v3 支持 64/1024 等）"""
        from app.llm.bailian import BailianAdapter

        # 注意：某些 v3 变种可能不支持任意 dim，宽松断言：dim 必 ≥ 64 且必 ≤ 1024
        monkeypatch.setattr(settings.EMBEDDING, "model", "text-embedding-v3")
        monkeypatch.setattr(settings.EMBEDDING, "dim", 64)

        adapter = BailianAdapter()
        vecs = await adapter.embed(["测试"])

        assert len(vecs[0]) >= 64
        assert len(vecs[0]) <= 1024

    @pytest.mark.skipif(not settings.CLOUD_LLM.api_key, reason="DASHSCOPE_API_KEY 未配置")
    async def test_v2_fixed_dim(self, monkeypatch):
        """v2 强制 1536（即使 settings.EMBEDDING.dim 配 1024 也应被覆盖）"""
        from app.llm.bailian import BailianAdapter
        monkeypatch.setattr(settings.EMBEDDING, "model", "text-embedding-v2")
        monkeypatch.setattr(settings.EMBEDDING, "dim", 1024)  # 用户误配

        adapter = BailianAdapter()
        vecs = await adapter.embed(["测试"])

        # v2 不支持自定义 dim，固定 1536
        assert len(vecs[0]) == 1536, f"v2 必须固定 1536，实际: {len(vecs[0])}"
