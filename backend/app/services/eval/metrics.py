"""
RAG 评测指标（聚群 C 评测框架核心）

4 个指标：
1. Hit Rate@K    召回命中率：top-K 内是否含相关文档（任意一个）
2. MRR           Mean Reciprocal Rank：第一个相关文档的排名倒数均值
3. NDCG@K        Normalized DCG：考虑排序质量
4. Citation      引用准确率：相关文档中带正确页码的比例

所有指标取值 [0, 1]，越高越好。

设计要点：
- 纯函数式，输入 List[List[relevance]] → 输出 float
- 易于单测
- 支持 binary 和 graded relevance
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


# ============================================================
# 单个问题的评测结果
# ============================================================
@dataclass
class EvalItemResult:
    """单题评测结果"""
    query: str
    # top-K 命中的相关度列表（0/1 或 0-3）
    relevances: List[int] = field(default_factory=list)
    # 命中的 chunk_id 列表（用于溯源）
    retrieved_ids: List[str] = field(default_factory=list)
    # 真实相关 chunk_id 列表
    gold_ids: List[str] = field(default_factory=list)
    # 引用的页码（用于 Citation Accuracy）
    retrieved_pages: List[int] = field(default_factory=list)
    gold_pages: List[int] = field(default_factory=list)

    # 派生
    hit: bool = False                       # 任意一个命中
    first_relevant_rank: Optional[int] = None   # 1-based
    ndcg: float = 0.0
    citation_correct: Optional[bool] = None     # 三态：True / False / None(无 gold page)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "relevances": self.relevances,
            "retrieved_ids": self.retrieved_ids,
            "gold_ids": self.gold_ids,
            "retrieved_pages": self.retrieved_pages,
            "gold_pages": self.gold_pages,
            "hit": self.hit,
            "first_relevant_rank": self.first_relevant_rank,
            "ndcg": round(self.ndcg, 4),
            "citation_correct": self.citation_correct,
        }


# ============================================================
# 指标函数
# ============================================================
def hit_rate_at_k(relevances_list: Sequence[Sequence[int]]) -> float:
    """Hit Rate@K：top-K 内是否含至少一个相关文档

    Args:
        relevances_list: 每题的 relevances 列表（0/1）
            e.g. [[1,0,0,0,0], [0,0,0,0,0], [0,1,0,0,0]]  →  2/3 = 0.667
    """
    if not relevances_list:
        return 0.0
    hits = sum(1 for r in relevances_list if any(x > 0 for x in r))
    return hits / len(relevances_list)


def mrr(relevances_list: Sequence[Sequence[int]]) -> float:
    """Mean Reciprocal Rank：第一个相关文档排名的倒数均值

    rank=1 → 1.0, rank=2 → 0.5, rank=3 → 0.333, ...
    没找到 → 0
    """
    if not relevances_list:
        return 0.0
    total = 0.0
    for r in relevances_list:
        rr = 0.0
        for i, rel in enumerate(r, start=1):
            if rel > 0:
                rr = 1.0 / i
                break
        total += rr
    return total / len(relevances_list)


def ndcg_at_k(relevances_list: Sequence[Sequence[int]], k: int = 5) -> float:
    """Normalized Discounted Cumulative Gain @ K

    Args:
        relevances_list: 每题的 relevances 列表（graded: 0-3）
        k: 截断位置
    """
    if not relevances_list:
        return 0.0
    total = 0.0
    for r in relevances_list:
        # DCG@K
        dcg = 0.0
        for i, rel in enumerate(r[:k], start=1):
            dcg += (2 ** rel - 1) / math.log2(i + 1)
        # ideal DCG（按降序排）
        ideal = sorted(r[:k], reverse=True)
        idcg = 0.0
        for i, rel in enumerate(ideal, start=1):
            idcg += (2 ** rel - 1) / math.log2(i + 1)
        # NDCG
        if idcg > 0:
            total += dcg / idcg
    return total / len(relevances_list)


def citation_accuracy(
    retrieved_pages_list: Sequence[Sequence[int]],
    gold_pages_list: Sequence[Sequence[int]],
) -> Optional[float]:
    """页码引用准确率：top-K 命中含 gold page 的比例

    Args:
        retrieved_pages_list: 每题召回的页码列表
        gold_pages_list: 每题真实相关页码列表

    Returns:
        准确率（0-1）；若所有题都没有 gold page → 返回 None
    """
    if not retrieved_pages_list:
        return None
    if len(retrieved_pages_list) != len(gold_pages_list):
        raise ValueError("retrieved/gold 数量必须一致")
    correct = 0
    total_with_gold = 0
    for rp, gp in zip(retrieved_pages_list, gold_pages_list):
        if not gp:
            continue  # 这题没 gold page，跳过
        total_with_gold += 1
        if any(p in gp for p in rp):
            correct += 1
    if total_with_gold == 0:
        return None
    return correct / total_with_gold


# ============================================================
# 聚合结果
# ============================================================
@dataclass
class EvalMetrics:
    """聚合指标结果"""
    total: int = 0
    hit_rate_at_5: float = 0.0
    hit_rate_at_10: float = 0.0
    mrr: float = 0.0
    ndcg_at_5: float = 0.0
    ndcg_at_10: float = 0.0
    citation_accuracy: Optional[float] = None
    # 按 source 拆分（如 manual / case / sop）
    by_source: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "hit_rate_at_5": round(self.hit_rate_at_5, 4),
            "hit_rate_at_10": round(self.hit_rate_at_10, 4),
            "mrr": round(self.mrr, 4),
            "ndcg_at_5": round(self.ndcg_at_5, 4),
            "ndcg_at_10": round(self.ndcg_at_10, 4),
            "citation_accuracy": (
                round(self.citation_accuracy, 4)
                if self.citation_accuracy is not None
                else None
            ),
            "by_source": self.by_source,
        }


def compute_all_metrics(items: List[EvalItemResult]) -> EvalMetrics:
    """一次性算全部指标"""
    if not items:
        return EvalMetrics()

    relevances_5 = [r.relevances[:5] for r in items]
    relevances_10 = [r.relevances[:10] for r in items]
    m = EvalMetrics(
        total=len(items),
        hit_rate_at_5=hit_rate_at_k(relevances_5),
        hit_rate_at_10=hit_rate_at_k(relevances_10),
        mrr=mrr(relevances_10),
        ndcg_at_5=ndcg_at_k(relevances_10, k=5),
        ndcg_at_10=ndcg_at_k(relevances_10, k=10),
    )
    # 页码准确率
    ca = citation_accuracy(
        [r.retrieved_pages for r in items],
        [r.gold_pages for r in items],
    )
    m.citation_accuracy = ca
    return m
