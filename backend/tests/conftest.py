"""Test fixtures: an isolated Postgres database, truncated between tests, and an HTTP client."""

import os
from collections.abc import AsyncIterator

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/social_test"
)
# Must be set before `app` is imported: settings are read at import time.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["ENVIRONMENT"] = "test"
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-at-least-32-characters-long")

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.config import normalize_database_url  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

_url, _connect_args = normalize_database_url(TEST_DATABASE_URL)
# NullPool: each test runs on its own event loop, so connections must not be reused across tests.
test_engine = create_async_engine(_url, connect_args=_connect_args, poolclass=NullPool)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


async def _override_get_db() -> AsyncIterator[AsyncSession]:
    async with TestSession() as session:
        yield session


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
async def _clean_db() -> AsyncIterator[None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        await conn.execute(text(f"TRUNCATE {tables} CASCADE"))
    yield


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def register(username: str) -> AsyncClient:
    """Register a user on a fresh client (own cookie jar) and return that client."""
    user_client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    resp = await user_client.post(
        "/api/auth/register",
        json={"email": f"{username}@example.com", "username": username, "password": "password123"},
    )
    assert resp.status_code == 201, resp.text
    return user_client


@pytest.fixture
async def users() -> AsyncIterator[dict[str, AsyncClient]]:
    """Three logged-in clients: alice, bob and carol."""
    clients = {name: await register(name) for name in ("alice", "bob", "carol")}
    yield clients
    for c in clients.values():
        await c.aclose()
