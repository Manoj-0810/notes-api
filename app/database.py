"""Database configuration.

Provides SQLAlchemy engine, async session factory, declarative base,
and a dependency-injectable get_db() for FastAPI.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.config import settings

# Create async engine with appropriate args for SQLite vs PostgreSQL
_engine_kwargs = {
    "echo": settings.ENVIRONMENT == "development",
    "future": True,
}

# SQLite-specific: allow same thread for aiosqlite
if settings.DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(
    settings.DATABASE_URL,
    **_engine_kwargs,
)

# Session factory with auto-commit/begin disabled (we control transactions)
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# Declarative base for all models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session.

    Session is properly closed after the request completes, even on exceptions.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
