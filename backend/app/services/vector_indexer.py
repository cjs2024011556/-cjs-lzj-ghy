"""
向量索引服务 - Milvus 集成
将文档分块向量化并存入 Milvus

聚群 A 升级：
- schema 加 8 个结构化字段（page_number / chapter / section_title / ...）
- 启动时 schema diff 检测 → 不匹配自动 drop+recreate
- index_chunks / search 全字段透传

聚群 B 升级：
- schema 加 2 个视觉理解字段（image_description / image_facts）
- 启动时缺字段自动触发 drop+recreate + 全量重传
"""
import hashlib
from collections import OrderedDict
from typing import List, Dict, Any, Optional
from loguru import logger

from app.services.document_parser import DocumentChunk
from app.core.config import settings


# ============================================================
# Milvus collection schema 定义（含聚群 A/B 新字段）
# ============================================================
# 注意：字段顺序会影响 data 列表的对齐（pymilvus 按声明顺序填数据）
COLLECTION_NAME = "a1_knowledge"

EXPECTED_FIELDS = {
    # 旧字段
    "id", "chunk_id", "content", "embedding", "source",
    "doc_type", "equipment_type", "equipment_model", "chunk_index",
    # 聚群 A 新增（PDF-A.4）
    "page_number", "page_end", "chapter", "section_title",
    "section_type", "section_level", "doc_id", "keywords",
    # 聚群 B 新增（PDF-B.5）
    "image_description", "image_facts",
}


class MilvusIndexer:
    """Milvus 向量索引器"""

    @property
    def DIM(self) -> int:
        """向量维度 - 从配置读取"""
        return settings.EMBEDDING.dim

    def __init__(self):
        self._client = None
        self._collection = None
        self._embedder = None

    # ============================================================
    # 连接 & schema 管理
    # ============================================================
    def _ensure_connected(self):
        """懒连接 + schema 自检 + 不匹配 drop+recreate"""
        if self._client is not None:
            return

        try:
            from pymilvus import (
                connections, Collection, FieldSchema, CollectionSchema,
                DataType, utility
            )
        except ImportError:
            raise ImportError("请安装 pymilvus: pip install pymilvus")

        connections.connect(
            alias="default",
            host=settings.MILVUS.host,
            port=str(settings.MILVUS.port),
            user=settings.MILVUS.user,
            password=settings.MILVUS.password,
            db_name=settings.MILVUS.db,
        )

        if not utility.has_collection(self.COLLECTION_NAME, using="default"):
            self._create_collection()
        else:
            # 自检：dim + 字段集合
            desc = utility.describe_collection(self.COLLECTION_NAME, using="default")
            existing_dim = self._extract_dim(desc)
            existing_fields = self._extract_field_names(desc)
            missing = EXPECTED_FIELDS - existing_fields
            needs_recreate = (
                (existing_dim is not None and existing_dim != self.DIM)
                or len(missing) > 0
            )
            if needs_recreate:
                reasons = []
                if existing_dim is not None and existing_dim != self.DIM:
                    reasons.append(f"dim 不匹配 ({existing_dim} → {self.DIM})")
                if missing:
                    reasons.append(f"缺失字段 {sorted(missing)}")
                logger.warning(
                    f"⚠️ Milvus collection 需要重建: {', '.join(reasons)}"
                )
                utility.drop_collection(self.COLLECTION_NAME, using="default")
                self._create_collection()
            else:
                self._collection = Collection(self.COLLECTION_NAME, using="default")

        self._collection.load(using="default")
        self._client = connections
        logger.info("✅ Milvus 连接成功")

    def _create_collection(self):
        """创建 collection（聚群 A: 17 字段 + 聚群 B: 19 字段）"""
        from pymilvus import (
            FieldSchema, CollectionSchema, Collection, DataType
        )
        fields = [
            # 基础
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8192),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.DIM),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=512),
            # 业务
            FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=32),
            FieldSchema(name="equipment_type", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="equipment_model", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
            # 聚群 A: 结构化字段
            FieldSchema(name="page_number", dtype=DataType.INT64),
            FieldSchema(name="page_end", dtype=DataType.INT64),
            FieldSchema(name="chapter", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="section_title", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="section_type", dtype=DataType.VARCHAR, max_length=32),
            FieldSchema(name="section_level", dtype=DataType.INT8),
            FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="keywords", dtype=DataType.VARCHAR, max_length=512),
            # 聚群 B: 视觉理解字段
            FieldSchema(name="image_description", dtype=DataType.VARCHAR, max_length=2048),
            FieldSchema(name="image_facts", dtype=DataType.VARCHAR, max_length=1024),
        ]
        schema = CollectionSchema(fields, description="A1 设备检修知识库 - 聚群 A/B 结构化版")
        self._collection = Collection(COLLECTION_NAME, schema=schema, using="default")

        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128},
        }
        self._collection.create_index("embedding", index_params, using="default")
        logger.info(
            f"✅ Milvus Collection 创建: {COLLECTION_NAME} "
            f"(dim={self.DIM}, 字段={len(fields)}, 含结构化字段)"
        )

    # ============================================================
    # 字段名 / 维度提取
    # ============================================================
    @staticmethod
    def _extract_dim(desc: dict) -> int | None:
        for f in desc.get("fields", []):
            if f.get("name") == "embedding":
                return f.get("type", {}).get("params", {}).get("dim")
        return None

    @staticmethod
    def _extract_field_names(desc: dict) -> set:
        return {f.get("name") for f in desc.get("fields", []) if f.get("name")}

    # ============================================================
    # Embedding LRU 缓存（保留旧逻辑）
    # ============================================================
    def _embed_lookup(self, texts: list):
        if not hasattr(self, '_embed_cache'):
            self._embed_cache: "OrderedDict[str, list]" = OrderedDict()
        CACHE_MAX = 256
        results = [None] * len(texts)
        miss_indices = []
        miss_texts = []
        for i, t in enumerate(texts):
            if t in self._embed_cache:
                self._embed_cache.move_to_end(t)
                results[i] = self._embed_cache[t]
            else:
                miss_indices.append(i)
                miss_texts.append(t)
        return results, miss_indices, miss_texts

    def _embed_store(self, miss_texts, miss_vectors):
        CACHE_MAX = 256
        for t, v in zip(miss_texts, miss_vectors):
            self._embed_cache[t] = v
            while len(self._embed_cache) > CACHE_MAX:
                self._embed_cache.popitem(last=False)

    async def _get_embedder(self):
        if self._embedder is None:
            from app.llm.factory import get_embedder
            self._embedder = get_embedder()
        return self._embedder

    @staticmethod
    def _make_chunk_id(content: str, source: str, idx: int) -> str:
        raw = f"{source}:{idx}:{content[:100]}"
        return hashlib.md5(raw.encode()).hexdigest()

    # ============================================================
    # 写 / 读
    # ============================================================
    async def index_chunks(
        self,
        chunks: List[DocumentChunk],
        doc_type: str = "manual",
        equipment_type: str = "",
        equipment_model: str = "",
    ) -> int:
        """索引一批分块（含聚群 A 结构化字段）"""
        self._ensure_connected()
        if not chunks:
            return 0

        texts = [c.content for c in chunks]
        results, miss_indices, miss_texts = self._embed_lookup(texts)
        if miss_texts:
            embedder = await self._get_embedder()
            miss_vectors = await embedder.embed(miss_texts)
            self._embed_store(miss_texts, miss_vectors)
            for idx, vec in zip(miss_indices, miss_vectors):
                results[idx] = vec
        embeddings = results
        logger.info(f"向量化完成: {len(embeddings)} 条, 维度: {len(embeddings[0])}")

        chunk_ids = [
            self._make_chunk_id(
                c.content,
                c.metadata.get("source", ""),
                c.metadata.get("chunk_index", 0),
            )
            for c in chunks
        ]

        def _meta(c: DocumentChunk, key: str, default):
            return c.metadata.get(key, default)

        # 19 字段（按 schema 声明顺序：聚群 A 17 + 聚群 B 2）
        data = [
            chunk_ids,                                                     # 1 chunk_id
            [c.content for c in chunks],                                   # 2 content
            embeddings,                                                    # 3 embedding
            [_meta(c, "source", "") for c in chunks],                      # 4 source
            [doc_type] * len(chunks),                                      # 5 doc_type
            [equipment_type] * len(chunks),                                # 6 equipment_type
            [equipment_model] * len(chunks),                               # 7 equipment_model
            [_meta(c, "chunk_index", 0) for c in chunks],                  # 8 chunk_index
            # 聚群 A 新增
            [_meta(c, "page_number", 0) for c in chunks],                  # 9 page_number
            [_meta(c, "page_end", _meta(c, "page_number", 0)) for c in chunks],  # 10 page_end
            [_meta(c, "chapter", "") for c in chunks],                     # 11 chapter
            [_meta(c, "section_title", "") for c in chunks],               # 12 section_title
            [_meta(c, "section_type", "text") for c in chunks],            # 13 section_type
            [_meta(c, "section_level", 0) for c in chunks],                # 14 section_level
            [_meta(c, "doc_id", "") for c in chunks],                      # 15 doc_id
            [_meta(c, "keywords", "") for c in chunks],                    # 16 keywords
            # 聚群 B 新增
            [_meta(c, "image_description", "") for c in chunks],          # 17 image_description
            [_meta(c, "image_facts", "") for c in chunks],                 # 18 image_facts
        ]

        mr = self._collection.insert(data, using="default")
        logger.info(f"✅ Milvus 索引完成: 插入 {mr.insert_count} 条")
        return mr.insert_count

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter_expr: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """向量检索（含聚群 A 结构化字段）"""
        self._ensure_connected()

        results, miss_indices, miss_texts = self._embed_lookup([query])
        if miss_texts:
            embedder = await self._get_embedder()
            miss_vectors = await embedder.embed(miss_texts)
            self._embed_store(miss_texts, miss_vectors)
            for idx, vec in zip(miss_indices, miss_vectors):
                results[idx] = vec
        query_vec = results[0]

        search_params = {"metric_type": "COSINE", "params": {"nprobe": 16}}
        results = self._collection.search(
            data=[query_vec],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=filter_expr,
            output_fields=[
                "chunk_id", "content", "source", "doc_type",
                "equipment_type", "equipment_model", "chunk_index",
                # 聚群 A
                "page_number", "page_end", "chapter", "section_title",
                "section_type", "section_level", "doc_id", "keywords",
                # 聚群 B
                "image_description", "image_facts",
            ],
            using="default",
        )

        hits = []
        for hit in results[0]:
            hits.append({
                "chunk_id": hit.entity.get("chunk_id"),
                "content": hit.entity.get("content"),
                "source": hit.entity.get("source"),
                "doc_type": hit.entity.get("doc_type"),
                "equipment_type": hit.entity.get("equipment_type"),
                "equipment_model": hit.entity.get("equipment_model"),
                "chunk_index": hit.entity.get("chunk_index"),
                # 聚群 A 字段（透传）
                "page_number": hit.entity.get("page_number") or 0,
                "page_end": hit.entity.get("page_end") or 0,
                "chapter": hit.entity.get("chapter") or "",
                "section_title": hit.entity.get("section_title") or "",
                "section_type": hit.entity.get("section_type") or "text",
                "section_level": hit.entity.get("section_level") or 0,
                "doc_id": hit.entity.get("doc_id") or "",
                "keywords": hit.entity.get("keywords") or "",
                # 聚群 B 字段（透传）
                "image_description": hit.entity.get("image_description") or "",
                "image_facts": hit.entity.get("image_facts") or "",
                "score": float(hit.distance),
            })
        return hits

    async def delete_by_source(self, source: str) -> int:
        self._ensure_connected()
        expr = f'source == "{source}"'
        mr = self._collection.delete(expr, using="default")
        self._collection.flush(using="default")
        return mr.delete_count

    async def count(self) -> int:
        self._ensure_connected()
        return self._collection.num_entities
