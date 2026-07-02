"""用户模型"""
from sqlalchemy import Column, String, DateTime, Integer, Boolean
from sqlalchemy.sql import func

from app.db import Base


class User(Base):
    """系统用户"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(128))
    role = Column(String(32), default="worker")  # worker/expert/admin
    department = Column(String(128))
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    last_login = Column(DateTime)
