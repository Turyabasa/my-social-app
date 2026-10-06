"""Shared FastAPI dependencies: DB session and current-user resolution."""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import decode_token
from app.database import get_db
from app.models import User

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user_optional(request: Request, db: DbSession) -> User | None:
    """Return the user identified by the auth cookie, or None when absent/invalid."""
    token = request.cookies.get(settings.cookie_name)
    if not token:
        return None
    subject = decode_token(token)
    if subject is None:
        return None
    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        return None
    return await db.get(User, user_id)


async def get_current_user(
    user: Annotated[User | None, Depends(get_current_user_optional)],
) -> User:
    """Return the authenticated user or raise 401."""
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]
