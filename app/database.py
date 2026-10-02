from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


settings = get_settings()
if sqlite_path := settings.sqlite_path:
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(settings.database_url, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Migration check for SQLite existing memories table
        try:
            result = await conn.execute(text("PRAGMA table_info(memories)"))
            columns = [row[1] for row in result.fetchall()]
            if columns and "embedding" not in columns:
                await conn.execute(text("ALTER TABLE memories ADD COLUMN embedding JSON"))
        except Exception:
            pass
