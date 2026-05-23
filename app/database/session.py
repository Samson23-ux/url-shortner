from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


from app.core.config import get_settings

async_engine: AsyncEngine = create_async_engine(
    url=get_settings().ASYNC_DB_URL,
    connect_args={"server_settings": {"timezone": "utc"}, "statement_cache_size": 0},
    pool_size=10,
    max_overflow=5,
    pool_timeout=10.0,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    bind=async_engine,
    autocommit=False,
    autoflush=False,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
	async with async_session() as session:
		yield session
