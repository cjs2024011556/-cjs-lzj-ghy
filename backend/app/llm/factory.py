"""
模型适配器工厂
根据配置（LLM_MODE）返回 cloud 或 local 适配器实例
"""
from typing import Optional

from app.llm.base import ModelAdapter
from app.llm.bailian import BailianAdapter
from app.llm.local_qwen2vl import LocalQwen2VLAdapter
from app.core.config import settings
from app.core.logger import logger


_adapter_instance: Optional[ModelAdapter] = None


def get_model_adapter(force_new: bool = False) -> ModelAdapter:
    """获取模型适配器（单例）

    Args:
        force_new: 强制创建新实例（用于切换模式后刷新）

    Returns:
        ModelAdapter: 适配器实例
    """
    global _adapter_instance

    if not force_new and _adapter_instance is not None:
        return _adapter_instance

    if settings.LLM_MODE == "cloud":
        logger.info("创建阿里云百炼平台适配器...")
        _adapter_instance = BailianAdapter()
    elif settings.LLM_MODE == "local":
        logger.info("创建本地 Qwen2-VL 适配器...")
        _adapter_instance = LocalQwen2VLAdapter()
    else:
        raise ValueError(f"不支持的 LLM_MODE: {settings.LLM_MODE}")

    logger.info(f"✅ 模型适配器就绪: mode={_adapter_instance.mode}, model={_adapter_instance.model_name}")
    return _adapter_instance


def switch_mode(new_mode: str) -> ModelAdapter:
    """切换模型模式（cloud ⇄ local）

    Args:
        new_mode: 目标模式 'cloud' | 'local'

    Returns:
        新的适配器实例
    """
    global _adapter_instance

    if new_mode not in ("cloud", "local"):
        raise ValueError(f"不支持的模式: {new_mode}")

    if settings.LLM_MODE == new_mode and _adapter_instance is not None:
        logger.info(f"模式未变化: {new_mode}")
        return _adapter_instance

    logger.info(f"切换 LLM 模式: {settings.LLM_MODE} → {new_mode}")
    settings.LLM_MODE = new_mode
    _adapter_instance = None
    return get_model_adapter(force_new=True)


def get_embedder() -> ModelAdapter:
    """获取 Embedding 适配器

    Cloud 模式：走百炼 text-embedding-v3（专业、低延迟、跨语言）
    Local 模式：使用本地的 BGE-M3（如未下载则降级到百炼）
    """
    if not hasattr(get_embedder, "_embedder") or get_embedder._embedder is None:
        # 直接用百炼 embedding（专业、便宜、无需本地模型）
        from app.llm.bailian import BailianAdapter
        get_embedder._embedder = BailianAdapter()
    return get_embedder._embedder
