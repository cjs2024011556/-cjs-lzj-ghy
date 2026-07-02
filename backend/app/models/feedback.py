"""反馈模型 - 用户对模型输出的修正和评价"""
from sqlalchemy import Column, String, Text, DateTime, Integer, JSON
from sqlalchemy.sql import func

from app.db import Base


class Feedback(Base):
    """用户反馈"""
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query = Column(Text, nullable=False)
    original_answer = Column(Text)
    correction = Column(Text)
    rating = Column(Integer, default=5)  # 1-5
    user = Column(String(64), default="anonymous")
    meta = Column("metadata", JSON)

    created_at = Column(DateTime, server_default=func.now())
