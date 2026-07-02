"""文档模型 - 检修手册、操作规程等"""
from sqlalchemy import Column, String, Text, DateTime, Integer, JSON
from sqlalchemy.sql import func

from app.db import Base


class Document(Base):
    """知识库文档"""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(String(64), unique=True, index=True, nullable=False, comment="文档ID")
    title = Column(String(255), nullable=False, comment="标题")
    doc_type = Column(String(32), comment="类型: manual/sop/spec/case")
    equipment_type = Column(String(64), index=True, comment="设备类型")
    equipment_model = Column(String(128), index=True, comment="设备型号")
    source = Column(String(255), comment="来源")
    file_path = Column(String(512), comment="文件路径")
    content = Column(Text, comment="文档内容（已解析）")
    content_hash = Column(String(64), index=True, comment="内容哈希")
    meta = Column("metadata", JSON, comment="额外元数据")
    chunk_count = Column(Integer, default=0, comment="分块数")
    indexed = Column(Integer, default=0, comment="是否已索引 0/1")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
