"""Authentication routes: register, login, logout, me, ws-token."""

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.core.deps import CurrentUser, DbSession
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    verify_password,
)
from app.models import User
from app.schemas import LoginRequest, Message, RegisterRequest, UserMe, WsToken

router = APIRouter()

WS_TOKEN_EXPIRE_MINUTES = 2


def _set_auth_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        key=settings.cookie_name,
        value=create_access_token(str(user.id)),
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


@router.post("/register", response_model=UserMe, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, response: Response, db: DbSession) -> User:
    """Create an account and log it in by setting the httpOnly auth cookie."""
    existing = await db.scalar(
        select(User).where(or_(User.email == body.email, User.username == body.username))
    )
    if existing is not None:
        field = "Email" if existing.email == body.email else "Username"
        raise HTTPException(status.HTTP_409_CONFLICT, f"{field} is already taken")

    user = User(
        email=body.email,
        username=body.username,
        display_name=body.display_name or body.username,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:  # lost a race with a concurrent registration
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email or username is already taken") from None

    _set_auth_cookie(response, user)
    return user


@router.post("/login", response_model=UserMe)
async def login(body: LoginRequest, response: Response, db: DbSession) -> User:
    """Verify credentials and set the httpOnly auth cookie."""
    user = await db.scalar(select(User).where(User.email == body.email))
    # Always run bcrypt so response time doesn't reveal whether the email exists.
    password_ok = verify_password(body.password, user.password_hash if user else DUMMY_PASSWORD_HASH)
    if user is None or not password_ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    _set_auth_cookie(response, user)
    return user


@router.post("/logout", response_model=Message)
async def logout(response: Response) -> Message:
    """Clear the auth cookie."""
    response.delete_cookie(
        key=settings.cookie_name,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    return Message(detail="Logged out")


@router.get("/me", response_model=UserMe)
async def me(user: CurrentUser) -> User:
    """Return the currently authenticated user."""
    return user


@router.get("/ws-token", response_model=WsToken)
async def ws_token(user: CurrentUser) -> WsToken:
    """Issue a 2-minute token for opening the notifications WebSocket.

    The auth cookie lives on the frontend's origin (requests are proxied), so the browser
    can't send it to the backend's WebSocket directly; this token bridges that gap.
    """
    return WsToken(
        token=create_access_token(str(user.id), token_type="ws", expires_minutes=WS_TOKEN_EXPIRE_MINUTES)
    )
