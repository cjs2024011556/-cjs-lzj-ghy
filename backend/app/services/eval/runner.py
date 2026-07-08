"""
评测运行器（聚群 C 评测框架）

跑流程：
1. 加载黄金集
2. 对每题调 RAG 检索
3. 算每个 item 的 relevances / pages
4. 聚合得 EvalMetrics
5. 写报告（JSON）

支持 mock 检索（用于单测 / 离线烟测）
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from loguru import logger

from app.services.eval.metrics import (
    EvalItemResult, EvalMetrics, compute_all_metrics, hit_rate_at_k, mrr,
)
from app.services.eval.gold_set import load_gold_set


# 类型：单题检索函数
# input: query (str), top_k (int)
# output: List[{chunk_id, content, source, score, page_number}]
RetrievalFunc = Callable[[str, int], Awaitable[List[Dict[str, Any]]]]


# ============================================================
# 默认检索（用项目自带的 RetrievalService）
# ============================================================
async def _default_retrieval(query: str, top_k: int) -> List[Dict[str, Any]]:
    """默认检索函数：调 RetrievalService.retrieve"""
    try:
        from app.services.retrieval_service import RetrievalService
        service = RetrievalService()
        result = await service.retrieve(query=query, top_k=top_k)
        return result.get("hits", [])
    except Exception as e:
        logger.warning(f"默认检索失败 ({query}): {e}")
        return []


# ============================================================
# EvalRunner
# ============================================================
class EvalRunner:
    """评测运行器

    用法：
        runner = EvalRunner(retrieval_fn=my_custom_retrieval)
        report = await runner.run(top_k=5)
    """

    def __init__(
        self,
        retrieval_fn: Optional[RetrievalFunc] = None,
        gold_set: Optional[List[Dict[str, Any]]] = None,
        gold_set_path: Optional[str] = None,
    ):
        self.retrieval_fn = retrieval_fn or _default_retrieval
        if gold_set is not None:
            self.gold_set = gold_set
        else:
            self.gold_set = load_gold_set(gold_set_path)

    async def run(self, top_k: int = 5) -> Dict[str, Any]:
        """跑评测，返回完整报告

        Returns:
            {
                "timestamp": "...",
                "total": N,
                "items": [...],   # 每题详情
                "metrics": {...}  # 聚合指标
            }
        """
        logger.info(f"📊 评测开始: {len(self.gold_set)} 题, top_k={top_k}")
        items: List[EvalItemResult] = []
        t0 = time.time()

        for gold in self.gold_set:
            query = gold.get("query", "")
            if not query:
                continue
            try:
                hits = await self.retrieval_fn(query, top_k)
            except Exception as e:
                logger.warning(f"评测检索失败: {query} → {e}")
                hits = []

            # 算每题 relevances
            gold_ids = set(gold.get("gold_chunk_ids", []))
            gold_pages = set(gold.get("gold_pages", []))
            retrieved_ids = []
            retrieved_pages = []
            relevances = []
            for h in hits:
                rid = h.get("chunk_id", "")
                rpg = h.get("page_number", 0) or 0
                retrieved_ids.append(rid)
                if rpg:
                    retrieved_pages.append(rpg)
                # relevance 评分：精确 chunk_id 匹配=3，page 匹配=2，source 匹配=1
                if rid in gold_ids and gold_ids:
                    relevances.append(3)
                elif rpg and rpg in gold_pages and gold_pages:
                    relevances.append(2)
                elif gold.get("gold_source") and gold["gold_source"] in (h.get("source") or ""):
                    relevances.append(1)
                else:
                    relevances.append(0)

            item = EvalItemResult(
                query=query,
                relevances=relevances,
                retrieved_ids=retrieved_ids,
                gold_ids=list(gold_ids),
                retrieved_pages=retrieved_pages,
                gold_pages=list(gold_pages),
            )
            # 派生 hit / first_relevant_rank / ndcg
            item.hit = any(r > 0 for r in relevances)
            for i, r in enumerate(relevances, start=1):
                if r > 0:
                    item.first_relevant_rank = i
                    break
            # 单题 NDCG 用整段
            from app.services.eval.metrics import ndcg_at_k
            item.ndcg = ndcg_at_k([relevances], k=len(relevances))
            # Citation Correct：top-K 至少含一个 gold page
            if gold_pages:
                item.citation_correct = any(p in gold_pages for p in retrieved_pages)
            items.append(item)

        metrics = compute_all_metrics(items)
        elapsed_ms = (time.time() - t0) * 1000

        report = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "elapsed_ms": round(elapsed_ms, 1),
            "total": len(items),
            "top_k": top_k,
            "metrics": metrics.to_dict(),
            "items": [it.to_dict() for it in items],
        }
        logger.info(
            f"📊 评测完成: {len(items)} 题 / "
            f"Hit@5={metrics.hit_rate_at_5:.2%} / "
            f"MRR={metrics.mrr:.2%} / "
            f"NDCG@5={metrics.ndcg_at_5:.2%} / "
            f"耗时 {elapsed_ms:.0f}ms"
        )
        return report


# ============================================================
# 便捷函数
# ============================================================
async def run_evaluation(
    top_k: int = 5,
    retrieval_fn: Optional[RetrievalFunc] = None,
    gold_set_path: Optional[str] = None,
) -> Dict[str, Any]:
    """便捷函数：跑一次评测"""
    runner = EvalRunner(
        retrieval_fn=retrieval_fn,
        gold_set_path=gold_set_path,
    )
    return await runner.run(top_k=top_k)


# ============================================================
# 报告持久化
# ============================================================
def save_report(report: Dict[str, Any], path: str | Path) -> None:
    """保存报告到 JSON 文件"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
