"""Post, reply and like schemas."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.user import UserPublic

PostContent = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=280)]


class PostCreate(BaseModel):
    """Body for creating a post."""

    content: PostContent


class ReplyCreate(BaseModel):
    """Body for creating a reply."""

    content: PostContent


class PostOut(BaseModel):
    """A post with author, aggregate counts and the viewer's like state."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content: str
    created_at: datetime
    author: UserPublic
    like_count: int
    reply_count: int
    liked_by_me: bool


class ReplyOut(BaseModel):
    """A reply with its author."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    post_id: UUID
    content: str
    created_at: datetime
    author: UserPublic


class PostDetail(BaseModel):
    """A post plus all of its replies, oldest first."""

    post: PostOut
    replies: list[ReplyOut]


class FeedPage(BaseModel):
    """One page of posts."""

    items: list[PostOut]
    page: int
    limit: int
    has_more: bool


class LikeStatus(BaseModel):
    """Result of toggling a like."""

    liked: bool
    like_count: int
