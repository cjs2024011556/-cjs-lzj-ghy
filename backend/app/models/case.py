"""案例模型 - 检修经验与故障案例"""
from sqlalchemy import Column, String, Text, DateTime, Integer, JSON, Enum
from sqlalchemy.sql import func

from app.db import Base


class Case(Base):
    """检修案例"""
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(64), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    equipment_type = Column(String(64), index=True)
    equipment_model = Column(String(128), index=True)
    fault_description = Column(Text)
    solution = Column(Text)
    tags = Column(JSON, default=list)
    status = Column(String(16), default="pending", index=True)  # pending/approved/rejected
    submitter = Column(String(64), default="anonymous")
    reviewer = Column(String(64))
    review_comment = Column(Text)
    file_path = Column(String(512))
    meta = Column("metadata", JSON)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    reviewed_at = Column(DateTime)
