"""User request/response schemas."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from app.schemas.post import PostOut


class UserPublic(BaseModel):
    """Publicly visible user fields."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    display_name: str
    bio: str | None
    avatar_url: str | None
    created_at: datetime


class UserMe(UserPublic):
    """The authenticated user, including private fields."""

    email: str


class UserProfile(UserPublic):
    """A profile page: user, counts, viewer relationship and recent posts."""

    followers_count: int
    following_count: int
    posts_count: int
    is_following: bool
    is_self: bool
    recent_posts: list["PostOut"]


class UserPage(BaseModel):
    """One page of users (followers / following / suggestions)."""

    items: list[UserPublic]
    page: int
    limit: int
    has_more: bool


class FollowStatus(BaseModel):
    """Result of a follow action."""

    following: bool
    followers_count: int
