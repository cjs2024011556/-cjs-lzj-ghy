"""
黄金评测集加载与校验（聚群 C 评测框架）

黄金集 JSON 格式：
[
    {
        "query": "电机过热怎么排查？",
        "gold_chunk_ids": ["c1", "c2"],      # 期望召回的 chunk_id（可选）
        "gold_pages": [12, 23],              # 期望命中的页码（用于 Citation Accuracy）
        "gold_source": "manual",             # 期望来源类型（可选）
        "category": "故障排查",              # 分类（可选，用于按类拆分）
        "difficulty": "easy"                 # 难度（可选）
    },
    ...
]
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


# 默认黄金集路径
DEFAULT_GOLD_SET_PATH = Path(__file__).parent.parent.parent.parent / "data" / "eval" / "gold_set.json"


def load_gold_set(path: str | Path | None = None) -> List[Dict[str, Any]]:
    """加载黄金集（不存在则返回默认最小集）"""
    p = Path(path) if path else DEFAULT_GOLD_SET_PATH
    if not p.exists():
        return _default_minimal_set()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("黄金集必须是 JSON 数组")
        return data
    except Exception as e:
        from loguru import logger
        logger.warning(f"加载黄金集失败 ({p}): {e}，使用默认集")
        return _default_minimal_set()


def _default_minimal_set() -> List[Dict[str, Any]]:
    """最小黄金集（5 题 - 用于跑通链路 / 离线 smoke test）"""
    return [
        {
            "query": "油温过高",
            "gold_chunk_ids": [],
            "gold_pages": [],
            "gold_source": "manual",
            "category": "故障诊断",
            "difficulty": "easy",
        },
        {
            "query": "电机轴承报警 E0123",
            "gold_chunk_ids": [],
            "gold_pages": [],
            "gold_source": "manual",
            "category": "报警码",
            "difficulty": "easy",
        },
        {
            "query": "更换周期",
            "gold_chunk_ids": [],
            "gold_pages": [],
            "gold_source": "sop",
            "category": "检修 SOP",
            "difficulty": "easy",
        },
        {
            "query": "阀门内漏",
            "gold_chunk_ids": [],
            "gold_pages": [],
            "gold_source": "case",
            "category": "故障案例",
            "difficulty": "medium",
        },
        {
            "query": "压力波动",
            "gold_chunk_ids": [],
            "gold_pages": [],
            "gold_source": "manual",
            "category": "故障诊断",
            "difficulty": "medium",
        },
    ]


def validate_gold_set(items: List[Dict[str, Any]]) -> List[str]:
    """校验黄金集格式，返回错误信息列表（空 = 全部合法）"""
    errors = []
    if not items:
        errors.append("黄金集为空")
        return errors
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"#{i+1}: 不是 dict")
            continue
        if "query" not in item or not item["query"]:
            errors.append(f"#{i+1}: 缺 query 字段")
        # 至少要有一个 gold 信号（chunk_ids / pages / source）
        if not any(k in item and item[k] for k in ("gold_chunk_ids", "gold_pages", "gold_source")):
            errors.append(f"#{i+1}: 缺 gold 信号（至少一个 chunk_id / page / source）")
    return errors


def write_default_gold_set(path: str | Path | None = None) -> None:
    """写出默认黄金集（首次部署时用）"""
    p = Path(path) if path else DEFAULT_GOLD_SET_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(_default_minimal_set(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
