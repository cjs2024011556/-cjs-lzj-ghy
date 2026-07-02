"""设备模型 - 设备类型与型号"""
from sqlalchemy import Column, String, DateTime, Integer, JSON
from sqlalchemy.sql import func

from app.db import Base


class Device(Base):
    """设备类型与型号"""
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_type = Column(String(64), index=True, nullable=False)
    device_model = Column(String(128), index=True, nullable=False)
    manufacturer = Column(String(128))
    specs = Column(JSON, comment="技术规格")
    common_faults = Column(JSON, default=list, comment="常见故障")
    recommended_sop = Column(String(64), comment="推荐 SOP ID")
    description = Column(Text)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
