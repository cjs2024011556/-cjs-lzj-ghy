"""数据库连接管理"""
from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

# SQLAlchemy 异步引擎
engine = create_async_engine(
    settings.POSTGRES.async_url,
    echo=settings.APP_DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db() -> AsyncSession:
    """FastAPI 依赖：获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """初始化数据库（建表）"""
    async with engine.begin() as conn:
        # 导入所有模型
        from app.models import (  # noqa
            document, case, feedback, device, sop, user,
        )
        await conn.run_sync(Base.metadata.create_all)
