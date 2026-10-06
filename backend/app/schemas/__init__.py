"""Pydantic schemas. Importing this package resolves the user <-> post forward references."""

from app.schemas.auth import LoginRequest, Message, RegisterRequest, WsToken
from app.schemas.post import (
    FeedPage,
    LikeStatus,
    PostCreate,
    PostDetail,
    PostOut,
    ReplyCreate,
    ReplyOut,
)
from app.schemas.user import FollowStatus, UserMe, UserPage, UserProfile, UserPublic

UserProfile.model_rebuild(_types_namespace={"PostOut": PostOut})

__all__ = [
    "FeedPage",
    "FollowStatus",
    "LikeStatus",
    "LoginRequest",
    "Message",
    "PostCreate",
    "PostDetail",
    "PostOut",
    "RegisterRequest",
    "ReplyCreate",
    "ReplyOut",
    "UserMe",
    "UserPage",
    "UserProfile",
    "UserPublic",
    "WsToken",
]
