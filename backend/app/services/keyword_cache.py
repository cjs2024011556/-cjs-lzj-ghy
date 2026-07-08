"""
关键词降级检索的共享文件 cache（H-Fix-3 思路）

- 抽到独立模块，避免 chat.py ↔ retrieval_service.py 的循环依赖
- key=path, value=(mtime, parsed_data)
- mtime 变了就重读；不存在的文件返回 default
"""
from pathlib import Path
from typing import Any, Dict, Optional
from loguru import logger

# 模块级 cache（单例）
_KEYWORD_CACHE: Dict[Any, tuple] = {}


def read_cached_json(path: Path, default: Optional[list] = None):
    """读 JSON 带 mtime 缓存"""
    if default is None:
        default = []
    try:
        if not path.exists():
            return default
        mtime = path.stat().st_mtime
        cached = _KEYWORD_CACHE.get(path)
        if cached is not None and cached[0] == mtime:
            return cached[1]
        import json as json_mod
        data = json_mod.loads(path.read_text(encoding="utf-8"))
        _KEYWORD_CACHE[path] = (mtime, data)
        return data
    except Exception as e:
        logger.warning(f"读 {path.name} 失败: {e}")
        return default


def read_cached_manuals(manuals_dir: Path) -> Dict[str, str]:
    """读 manuals_dir/*.md 带 mtime 缓存 → {stem: text}"""
    if not manuals_dir.exists():
        return {}
    result: Dict[str, str] = {}
    for manual_path in manuals_dir.glob("*.md"):
        try:
            mtime = manual_path.stat().st_mtime
            cached = _KEYWORD_CACHE.get(manual_path)
            if cached is not None and cached[0] == mtime:
                result[manual_path.stem] = cached[1]
                continue
            text = manual_path.read_text(encoding="utf-8")
            _KEYWORD_CACHE[manual_path] = (mtime, text)
            result[manual_path.stem] = text
        except Exception:
            continue
    return result


def invalidate():
    """失效全部缓存（上传/删除文件后调用）"""
    _KEYWORD_CACHE.clear()
