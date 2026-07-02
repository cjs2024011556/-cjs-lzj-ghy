"""
向量索引服务 - Milvus 集成
将文档分块向量化并存入 Milvus
"""
import hashlib
from collections import OrderedDict
from typing import List, Dict, Any, Optional
from loguru import logger

from app.services.document_parser import DocumentChunk
from app.core.config import settings


class MilvusIndexer:
    """Milvus 向量索引器

    Collection 结构:
    - id: 主键（自增）
    - chunk_id: 业务 ID（hash）
    - content: 文本
    - embedding: 向量（dim 1024）
    - source: 来源文件
    - doc_type: 类型 (manual/case/sop)
    - equipment_type: 设备类型
    - equipment_model: 设备型号
    - chunk_index: 分块序号
    - metadata: JSON
    """

    COLLECTION_NAME = "a1_knowledge"

    @property
    def DIM(self) -> int:
        """向量维度 - 从配置读取（支持不同 embedding 模型）"""
        return settings.EMBEDDING.dim

    def __init__(self):
        self._client = None
        self._collection = None
        self._embedder = None

    def _ensure_connected(self):
        """懒连接"""
        if self._client is not None:
            return

        try:
            from pymilvus import (
                connections, Collection, FieldSchema, CollectionSchema,
                DataType, utility
            )
        except ImportError:
            raise ImportError("请安装 pymilvus: pip install pymilvus")

        # 连接
        connections.connect(
            alias="default",
            host=settings.MILVUS.host,
            port=str(settings.MILVUS.port),
            user=settings.MILVUS.user,
            password=settings.MILVUS.password,
            db_name=settings.MILVUS.db,
        )

        # 创建集合（如果不存在）
        if not utility.has_collection(self.COLLECTION_NAME, using="default"):
            self._create_collection()
        else:
            # U1: 校验已有 collection 的 dim 与当前 settings 是否匹配
            existing = utility.describe_collection(self.COLLECTION_NAME, using="default")
            existing_dim = self._extract_dim(existing)
            if existing_dim is not None and existing_dim != self.DIM:
                logger.warning(
                    f"⚠️ Milvus collection dim 不匹配 ({existing_dim} → {self.DIM})，"
                    f"重建 collection（数据会丢失）"
                )
                utility.drop_collection(self.COLLECTION_NAME, using="default")
                self._create_collection()
            else:
                self._collection = Collection(self.COLLECTION_NAME, using="default")

        self._collection.load(using="default")
        self._client = connections
        logger.info("✅ Milvus 连接成功")

    def _create_collection(self):
        """创建 Milvus collection（U1 自适应 dim）"""
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8192),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.DIM),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=32),
            FieldSchema(name="equipment_type", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="equipment_model", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
        ]
        schema = CollectionSchema(fields, description="A1 设备检修知识库")
        self._collection = Collection(self.COLLECTION_NAME, schema=schema, using="default")

        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128},
        }
        self._collection.create_index("embedding", index_params, using="default")
        logger.info(f"✅ Milvus Collection 创建: {self.COLLECTION_NAME} (dim={self.DIM})")

    @staticmethod
    def _extract_dim(collection_desc: dict) -> int | None:
        """从 Milvus collection 描述中提取 embedding 字段的 dim"""
        for field in collection_desc.get("fields", []):
            if field.get("name") == "embedding":
                return field.get("type", {}).get("params", {}).get("dim")
        return None

    def _embed_lookup(self, texts: list):
        """Embedding LRU 缓存查询（返回 (results, miss_indices, miss_texts)）

        LRU 256 条：相同 text 直接复用，淘汰最久未用。
        """
        if not hasattr(self, '_embed_cache'):
            self._embed_cache: "OrderedDict[str, list]" = OrderedDict()
        CACHE_MAX = 256
        results = [None] * len(texts)
        miss_indices: list[int] = []
        miss_texts: list[str] = []
        for i, t in enumerate(texts):
            if t in self._embed_cache:
                self._embed_cache.move_to_end(t)
                results[i] = self._embed_cache[t]
            else:
                miss_indices.append(i)
                miss_texts.append(t)
        return results, miss_indices, miss_texts

    def _embed_store(self, miss_texts: list, miss_vectors: list):
        """把新算的向量写回 LRU"""
        CACHE_MAX = 256
        for t, v in zip(miss_texts, miss_vectors):
            self._embed_cache[t] = v
            while len(self._embed_cache) > CACHE_MAX:
                self._embed_cache.popitem(last=False)

    async def _get_embedder(self):
        """获取 Embedding 模型"""
        if self._embedder is None:
            from app.llm.factory import get_embedder
            self._embedder = get_embedder()
        return self._embedder

    @staticmethod
    def _make_chunk_id(content: str, source: str, idx: int) -> str:
        """生成 chunk 业务 ID"""
        raw = f"{source}:{idx}:{content[:100]}"
        return hashlib.md5(raw.encode()).hexdigest()

    async def index_chunks(
        self,
        chunks: List[DocumentChunk],
        doc_type: str = "manual",
        equipment_type: str = "",
        equipment_model: str = "",
    ) -> int:
        """索引一批分块"""
        self._ensure_connected()

        if not chunks:
            return 0

        # 1. 准备文本
        texts = [c.content for c in chunks]

        # 2. 向量化（带 LRU 缓存）
        results, miss_indices, miss_texts = self._embed_lookup(texts)
        if miss_texts:
            embedder = await self._get_embedder()
            miss_vectors = await embedder.embed(miss_texts)
            self._embed_store(miss_texts, miss_vectors)
            for idx, vec in zip(miss_indices, miss_vectors):
                results[idx] = vec
        embeddings = results
        logger.info(f"向量化完成: {len(embeddings)} 条, 维度: {len(embeddings[0])}")

        # 3. 构造数据
        chunk_ids = [self._make_chunk_id(c.content, c.metadata.get("source", ""), c.metadata.get("chunk_index", 0)) for c in chunks]
        sources = [c.metadata.get("source", "") for c in chunks]
        indices = [c.metadata.get("chunk_index", 0) for c in chunks]

        data = [
            chunk_ids,
            [c.content for c in chunks],
            embeddings,
            sources,
            [doc_type] * len(chunks),
            [equipment_type] * len(chunks),
            [equipment_model] * len(chunks),
            indices,
        ]

        # 4. 插入（依赖 Milvus auto-flush，不显式 flush 以避免每个 batch 同步阻塞）
        mr = self._collection.insert(data, using="default")
        logger.info(f"✅ Milvus 索引完成: 插入 {mr.insert_count} 条")
        return mr.insert_count

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter_expr: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """向量检索"""
        self._ensure_connected()

        # 1. query embedding（带 LRU 缓存）
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
            output_fields=["chunk_id", "content", "source", "doc_type", "equipment_type", "equipment_model", "chunk_index"],
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
                "score": float(hit.distance),
            })
        return hits

    async def delete_by_source(self, source: str) -> int:
        """按来源删除"""
        self._ensure_connected()
        expr = f'source == "{source}"'
        mr = self._collection.delete(expr, using="default")
        self._collection.flush(using="default")
        return mr.delete_count

    async def count(self) -> int:
        """统计条数"""
        self._ensure_connected()
        return self._collection.num_entities
