"""
聚群 C 评测框架

目录：
- metrics.py:  4 个 RAG 评测指标（Hit Rate@K / MRR / NDCG@K / Citation Accuracy）
- runner.py:   跑黄金集，输出 JSON 报告
- gold_set.py: 加载 / 验证黄金集
"""
from app.services.eval.metrics import (
    hit_rate_at_k, mrr, ndcg_at_k, citation_accuracy,
    compute_all_metrics, EvalMetrics, EvalItemResult,
)
from app.services.eval.runner import EvalRunner, run_evaluation
from app.services.eval.gold_set import load_gold_set, validate_gold_set

__all__ = [
    "hit_rate_at_k",
    "mrr",
    "ndcg_at_k",
    "citation_accuracy",
    "compute_all_metrics",
    "EvalMetrics",
    "EvalItemResult",
    "EvalRunner",
    "run_evaluation",
    "load_gold_set",
    "validate_gold_set",
]
