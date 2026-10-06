"""Async SQLAlchemy engine, session factory, declarative base and the get_db dependency."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import normalize_database_url, settings

_url, _connect_args = normalize_database_url(settings.database_url)

# pool_pre_ping + pool_recycle survive serverless databases (Neon) that drop idle connections.
engine = create_async_engine(_url, connect_args=_connect_args, pool_pre_ping=True, pool_recycle=300)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""


def utcnow() -> datetime:
    """Timezone-aware current UTC time (datetime.utcnow is deprecated)."""
    return datetime.now(UTC)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding one AsyncSession per request."""
    async with SessionLocal() as session:
        yield session
