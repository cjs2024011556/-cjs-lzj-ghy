"""
BM25 关键词索引（聚群 C：与 Milvus 向量检索互补）

为什么需要 BM25：
- 向量检索擅长语义近似（"电机热" → "马达高温"）
- BM25 擅长精确关键词（型号、报警码、参数值）
- 双路召回 + 加权融合，命中率提升 10-20%（企业 RAG 通用做法）

实现要点：
- rank_bm25 库（已装）
- jieba 切词（中文友好）
- 内存索引（per app lifetime，文档变更时重建）
- 与 Milvus indexer 互不依赖

性能：
- 10k chunks 索引 ~100MB 内存
- 检索 ~1ms（vs 向量 ~10ms）
"""
from __future__ import annotations

import re
import threading
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    from rank_bm25 import BM25Okapi
    _HAS_BM25 = True
except ImportError:
    _HAS_BM25 = False
    logger.warning("rank_bm25 未装，BM25 检索不可用")


# ============================================================
# 切词
# ============================================================
def _tokenize(text: str) -> List[str]:
    """中英混合切词

    - 中文：jieba.cut（保留英文 token）
    - 英文：按空格 + 标点切
    - 转小写
    """
    if not text:
        return []
    text = text.strip().lower()
    tokens: List[str] = []
    try:
        import jieba
        for tok in jieba.cut(text):
            tok = tok.strip()
            if not tok or len(tok) > 50:
                continue
            # 过滤纯标点
            if re.match(r'^[\s\W]+$', tok):
                continue
            tokens.append(tok)
    except ImportError:
        # jieba 不在：退化为字符级
        tokens = [c for c in text if not re.match(r'^\s$', c)]
    return tokens


# ============================================================
# 主类
# ============================================================
class BM25Indexer:
    """内存 BM25 索引

    用法：
        idx = BM25Indexer()
        idx.add_chunks(chunks)  # chunks: List[{chunk_id, content, source, ...}]
        results = idx.search("电机过热", top_k=5)
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        if not _HAS_BM25:
            raise ImportError("请安装 rank_bm25: pip install rank_bm25")
        self.k1 = k1
        self.b = b
        self._corpus_tokens: List[List[str]] = []
        self._metadata: List[Dict[str, Any]] = []
        self._bm25: Optional[BM25Okapi] = None
        self._lock = threading.RLock()

    @property
    def size(self) -> int:
        return len(self._metadata)

    def add_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        """批量添加 chunks（每次 add 都重建索引，简单实现）"""
        with self._lock:
            new_tokens = [_tokenize(c.get("content", "")) for c in chunks]
            self._corpus_tokens.extend(new_tokens)
            self._metadata.extend(chunks)
            self._rebuild()
            return len(chunks)

    def clear(self) -> None:
        """清空索引"""
        with self._lock:
            self._corpus_tokens.clear()
            self._metadata.clear()
            self._bm25 = None

    def _rebuild(self) -> None:
        """重建 BM25 索引（O(n)）"""
        if not self._corpus_tokens:
            self._bm25 = None
            return
        self._bm25 = BM25Okapi(
            self._corpus_tokens,
            k1=self.k1,
            b=self.b,
        )
        logger.debug(f"🔍 BM25 重建: {len(self._corpus_tokens)} docs")

    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_fn: Optional[callable] = None,
    ) -> List[Dict[str, Any]]:
        """关键词检索

        Args:
            query: 查询文本
            top_k: 返回数量
            filter_fn: 可选过滤函数 (meta) -> bool

        Returns:
            List[{chunk_id, content, source, score, page_number, chapter, ...}]
            按 BM25 分数降序
        """
        with self._lock:
            if self._bm25 is None or not self._metadata:
                return []
            query_tokens = _tokenize(query)
            if not query_tokens:
                return []
            scores = self._bm25.get_scores(query_tokens)
            # 排序
            ranked = sorted(
                enumerate(scores),
                key=lambda x: -x[1],
            )
            results: List[Dict[str, Any]] = []
            for idx, score in ranked:
                if score <= 0:
                    break  # BM25 分数 ≤ 0 没意义
                meta = self._metadata[idx]
                if filter_fn and not filter_fn(meta):
                    continue
                hit = {**meta, "score": float(score)}
                results.append(hit)
                if len(results) >= top_k:
                    break
            return results

    def save_snapshot(self) -> Dict[str, Any]:
        """导出元数据快照（用于持久化）"""
        return {
            "size": self.size,
            "metadata": self._metadata,
        }

    def load_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """从快照恢复"""
        with self._lock:
            self.clear()
            self.add_chunks(snapshot.get("metadata", []))
