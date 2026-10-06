"""Database URL normalization for hosted Postgres providers."""

from app.config import normalize_database_url


def test_neon_url_is_converted_for_asyncpg() -> None:
    url, connect_args = normalize_database_url(
        "postgresql://user:pw@ep-cool-123.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    )
    assert url == "postgresql+asyncpg://user:pw@ep-cool-123.us-east-2.aws.neon.tech/neondb"
    assert connect_args == {"ssl": "require"}


def test_postgres_scheme_and_plain_urls() -> None:
    assert normalize_database_url("postgres://u:p@h:5432/db") == ("postgresql+asyncpg://u:p@h:5432/db", {})
    assert normalize_database_url("postgresql+asyncpg://u:p@h/db?sslmode=disable") == (
        "postgresql+asyncpg://u:p@h/db",
        {},
    )
