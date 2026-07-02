"""
Embedding 模型维度映射（前后端单一真相源）

支持的百炼 embedding 模型：
- text-embedding-v3：自定义维度（默认 1024，可调 64/1024）
- text-embedding-v2：固定 1536 维
- 异步版本：维度同上
- 本地 BGE：走 sentence-transformers（不在百炼）
"""

# model → 默认维度
EMBEDDING_MODEL_DIM: dict[str, int] = {
    "text-embedding-v3": 1024,
    "text-embedding-async-v3": 1024,
    "text-embedding-v2": 1536,
    "text-embedding-async-v2": 1536,
    "BAAI/bge-m3": 1024,
    "BAAI/bge-large-zh-v1.5": 1024,
}

# 这些模型支持自定义 dimension 参数（用户可配）
EMBEDDING_CUSTOM_DIM_SUPPORT: set[str] = {
    "text-embedding-v3",
    "text-embedding-async-v3",
}


def get_model_dim(model: str, fallback: int = 1024) -> int:
    """获取模型固定 dim（不支持自定义 dim 的返回固定值）"""
    return EMBEDDING_MODEL_DIM.get(model, fallback)


def supports_custom_dim(model: str) -> bool:
    """是否支持自定义 dim 参数"""
    return model in EMBEDDING_CUSTOM_DIM_SUPPORT
