"""User routes: profiles, follower/following lists, follow suggestions."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlalchemy import Select, exists, func, select

from app.core.deps import CurrentUser, DbSession, OptionalUser
from app.models import Follow, Post, User
from app.schemas import UserPage, UserProfile, UserPublic
from app.services import feed

router = APIRouter()

UsernamePath = Annotated[str, Path(min_length=1, max_length=30)]
Page = Annotated[int, Query(ge=1, le=10_000)]
Limit = Annotated[int, Query(ge=1, le=100)]


async def get_user_or_404(db: DbSession, username: str) -> User:
    """Look up a user by (case-insensitive) username or raise 404."""
    user = await db.scalar(select(User).where(User.username == username.lower()))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


async def count_followers(db: DbSession, user_id: object) -> int:
    """Number of users following user_id."""
    return await db.scalar(select(func.count()).select_from(Follow).where(Follow.following_id == user_id)) or 0


async def _user_page(db: DbSession, stmt: Select[tuple[User]], page: int, limit: int) -> UserPage:
    rows = list(await db.scalars(stmt.offset((page - 1) * limit).limit(limit + 1)))
    return UserPage(
        items=[UserPublic.model_validate(u) for u in rows[:limit]],
        page=page,
        limit=limit,
        has_more=len(rows) > limit,
    )


@router.get("/suggestions", response_model=UserPage)
async def suggestions(user: CurrentUser, db: DbSession, limit: Annotated[int, Query(ge=1, le=20)] = 5) -> UserPage:
    """Newest users the current user doesn't follow yet ("Who to follow")."""
    already_following = exists().where(Follow.follower_id == user.id, Follow.following_id == User.id)
    stmt = (
        select(User)
        .where(User.id != user.id, ~already_following)
        .order_by(User.created_at.desc(), User.id)
    )
    return await _user_page(db, stmt, 1, limit)


@router.get("/users/{username}", response_model=UserProfile)
async def get_profile(username: UsernamePath, viewer: OptionalUser, db: DbSession) -> UserProfile:
    """Profile with follower/following/post counts, viewer's follow state and the last 10 posts."""
    user = await get_user_or_404(db, username)
    following_count = (
        await db.scalar(select(func.count()).select_from(Follow).where(Follow.follower_id == user.id)) or 0
    )
    posts_count = await db.scalar(select(func.count()).select_from(Post).where(Post.user_id == user.id)) or 0
    is_following = False
    if viewer is not None and viewer.id != user.id:
        is_following = bool(
            await db.scalar(
                select(exists().where(Follow.follower_id == viewer.id, Follow.following_id == user.id))
            )
        )
    return UserProfile(
        **UserPublic.model_validate(user).model_dump(),
        followers_count=await count_followers(db, user.id),
        following_count=following_count,
        posts_count=posts_count,
        is_following=is_following,
        is_self=viewer is not None and viewer.id == user.id,
        recent_posts=await feed.get_user_posts(db, user.id, viewer.id if viewer else None, limit=10),
    )


@router.get("/users/{username}/followers", response_model=UserPage)
async def get_followers(username: UsernamePath, db: DbSession, page: Page = 1, limit: Limit = 20) -> UserPage:
    """Paginated users who follow this user, most recent first."""
    user = await get_user_or_404(db, username)
    stmt = (
        select(User)
        .join(Follow, Follow.follower_id == User.id)
        .where(Follow.following_id == user.id)
        .order_by(Follow.created_at.desc(), User.id)
    )
    return await _user_page(db, stmt, page, limit)


@router.get("/users/{username}/following", response_model=UserPage)
async def get_following(username: UsernamePath, db: DbSession, page: Page = 1, limit: Limit = 20) -> UserPage:
    """Paginated users this user follows, most recent first."""
    user = await get_user_or_404(db, username)
    stmt = (
        select(User)
        .join(Follow, Follow.following_id == User.id)
        .where(Follow.follower_id == user.id)
        .order_by(Follow.created_at.desc(), User.id)
    )
    return await _user_page(db, stmt, page, limit)
