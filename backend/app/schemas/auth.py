"""Authentication request/response schemas."""

from typing import Annotated

from pydantic import BaseModel, EmailStr, StringConstraints, field_validator, model_validator

Username = Annotated[
    str,
    StringConstraints(
        # pattern is checked before to_lower, so it must accept uppercase too.
        strip_whitespace=True, to_lower=True, min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_]+$"
    ),
]
DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


def _check_password(value: str) -> str:
    # bcrypt silently ignores everything past 72 bytes, so reject longer passwords outright.
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 bytes")
    return value


class RegisterRequest(BaseModel):
    """Body for creating an account. display_name defaults to the username."""

    email: EmailStr
    username: Username
    password: Annotated[str, StringConstraints(min_length=8)]
    display_name: DisplayName | None = None

    _password = field_validator("password")(_check_password)

    @field_validator("email")
    @classmethod
    def _lower_email(cls, value: str) -> str:
        return value.lower()

    @model_validator(mode="after")
    def _default_display_name(self) -> "RegisterRequest":
        if self.display_name is None:
            self.display_name = self.username
        return self


class LoginRequest(BaseModel):
    """Body for logging in."""

    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]

    @field_validator("email")
    @classmethod
    def _lower_email(cls, value: str) -> str:
        return value.lower()


class WsToken(BaseModel):
    """Short-lived token for authenticating the notifications WebSocket."""

    token: str


class Message(BaseModel):
    """Generic human-readable response."""

    detail: str
