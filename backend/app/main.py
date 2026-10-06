"""FastAPI application: middleware, error handlers, routers and lifespan."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import models  # noqa: F401  # registers all tables on Base.metadata
from app.config import settings
from app.core.deps import DbSession
from app.database import Base, engine
from app.routers import auth, follows, notifications, posts, users

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Create tables on startup in development only; production relies on Alembic migrations."""
    if settings.environment == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Social API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Return HTTP errors as {"detail": ...} JSON."""
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Return 422 with a readable summary plus the field-level errors."""
    errors = jsonable_encoder(exc.errors(), exclude={"ctx", "input", "url"})
    first = errors[0] if errors else {}
    field = ".".join(str(p) for p in first.get("loc", []) if p != "body")
    message = f"{field}: {first.get('msg', 'Invalid request')}" if field else first.get("msg", "Invalid request")
    return JSONResponse(
        {"detail": message, "errors": errors}, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Log unexpected errors and return a generic 500 without leaking internals."""
    logger.exception("Unhandled error", exc_info=exc)
    return JSONResponse({"detail": "Internal server error"}, status_code=500)


@app.get("/api/health", tags=["health"])
async def health(db: DbSession) -> dict[str, str]:
    """Liveness + database connectivity check (used by Docker and Render health checks)."""
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}


app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(posts.router, prefix="/api", tags=["posts"])
app.include_router(users.router, prefix="/api", tags=["users"])
app.include_router(follows.router, prefix="/api/follows", tags=["follows"])
app.include_router(notifications.router, tags=["notifications"])
