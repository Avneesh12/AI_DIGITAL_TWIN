"""
app/core/database.py
────────────────────
Async SQLAlchemy engine + session factory.
Uses asyncpg driver for PostgreSQL 15+.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# ── Engine ────────────────────────────────────────────────────────────────────

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,          # Detect stale connections
    pool_recycle=3600,           # Recycle connections every hour
)

# ── Session Factory ───────────────────────────────────────────────────────────

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,      # Prevent lazy-load errors after commit
    autoflush=False,
)


# ── Base ORM Class ────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


# ── Dependency ───────────────────────────────────────────────────────────────

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async DB session.
    Automatically rolls back on exception, closes when done.
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
