"""Password hashing and JWT helpers."""

from datetime import UTC, datetime, timedelta
from typing import Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

TokenType = Literal["access", "ws"]

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Verified against when the email doesn't exist, so login timing doesn't reveal registered emails.
DUMMY_PASSWORD_HASH = _pwd_context.hash("not-a-real-password")


def hash_password(password: str) -> str:
    """Return a bcrypt hash of the password."""
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Check a plaintext password against a stored hash."""
    return _pwd_context.verify(password, password_hash)


def create_access_token(
    subject: str, *, token_type: TokenType = "access", expires_minutes: int | None = None
) -> str:
    """Create a signed JWT whose ``sub`` is the user id."""
    now = datetime.now(UTC)
    minutes = expires_minutes if expires_minutes is not None else settings.access_token_expire_minutes
    payload = {"sub": subject, "type": token_type, "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, *, token_type: TokenType = "access") -> str | None:
    """Return the token's subject, or None if it is invalid, expired or of the wrong type."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    if payload.get("type") != token_type:
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) else None
