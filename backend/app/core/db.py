from collections.abc import AsyncIterator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.persistence.models import Base

settings = get_settings()

engine: AsyncEngine = create_async_engine(settings.database_url, future=True, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(_ensure_chat_session_owner_id_column)


def _ensure_chat_session_owner_id_column(connection) -> None:
    inspector = inspect(connection)
    columns = {column["name"] for column in inspector.get_columns("chat_sessions")}
    if "owner_id" not in columns:
        connection.execute(text("ALTER TABLE chat_sessions ADD COLUMN owner_id VARCHAR(128)"))

    connection.execute(
        text("UPDATE chat_sessions SET owner_id = 'legacy:' || id WHERE owner_id IS NULL OR owner_id = ''")
    )


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
