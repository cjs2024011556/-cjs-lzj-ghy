"""SOP 模型 - 标准化作业流程"""
from sqlalchemy import Column, String, DateTime, Integer, JSON, Text
from sqlalchemy.sql import func

from app.db import Base


class SOP(Base):
    """标准化作业流程"""
    __tablename__ = "sops"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sop_id = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    equipment_type = Column(String(64), index=True)
    maintenance_level = Column(String(32), index=True)  # daily/level_1/level_2/level_3/overhaul
    steps = Column(JSON, nullable=False)  # 步骤列表
    tools = Column(JSON, default=list)  # 所需工具
    safety_warnings = Column(JSON, default=list)  # 安全警告
    estimated_minutes = Column(Integer, default=0)
    description = Column(Text)
    version = Column(String(16), default="1.0")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
