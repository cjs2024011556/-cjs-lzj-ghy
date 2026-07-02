"""
日志配置 - 基于 loguru
统一管理后端日志，支持控制台 + 文件双输出
"""
import sys
from pathlib import Path
from loguru import logger

from app.core.config import settings


def setup_logger():
    """配置全局 logger"""
    # 让 stdout 支持 utf-8（Windows GBK console 不会因为 emoji 崩溃）
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    # 移除默认 handler
    logger.remove()

    # 控制台 handler（带颜色）
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        level=settings.LOG_LEVEL,
        colorize=True,
    )

    # 文件 handler（按天轮转）
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.add(
        log_dir / "app_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
               "{name}:{function}:{line} | {message}",
        level=settings.LOG_LEVEL,
        rotation="00:00",      # 每天 0 点轮转
        retention="30 days",   # 保留 30 天
        compression="zip",     # 压缩归档
        encoding="utf-8",
    )

    # 错误日志单独记录
    logger.add(
        log_dir / "error_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
               "{name}:{function}:{line} | {message}",
        level="ERROR",
        rotation="00:00",
        retention="90 days",
        compression="zip",
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
    )

    logger.info(f"✅ 日志系统初始化完成 (level={settings.LOG_LEVEL})")
    return logger


# 导出
__all__ = ["logger", "setup_logger"]
