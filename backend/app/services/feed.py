"""Post queries: feed, explore, per-user timelines and single posts, with counts computed in SQL."""

import uuid
from typing import Any

from sqlalchemy import Row, Select, exists, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import Follow, Like, Post, Reply
from app.schemas import FeedPage, PostOut, UserPublic


def _post_select(viewer_id: uuid.UUID | None) -> Select[Any]:
    """SELECT Post + like_count + reply_count + liked_by_me, with the author eagerly loaded."""
    like_count = (
        select(func.count()).select_from(Like).where(Like.post_id == Post.id).correlate(Post).scalar_subquery()
    )
    reply_count = (
        select(func.count()).select_from(Reply).where(Reply.post_id == Post.id).correlate(Post).scalar_subquery()
    )
    liked_by_me = (
        exists().where(Like.post_id == Post.id, Like.user_id == viewer_id).correlate(Post)
        if viewer_id is not None
        else false()
    )
    return select(
        Post,
        like_count.label("like_count"),
        reply_count.label("reply_count"),
        liked_by_me.label("liked_by_me"),
    ).options(joinedload(Post.user))


def _to_post_out(row: Row[Any]) -> PostOut:
    post, like_count, reply_count, liked_by_me = row
    return PostOut(
        id=post.id,
        content=post.content,
        created_at=post.created_at,
        author=UserPublic.model_validate(post.user),
        like_count=like_count,
        reply_count=reply_count,
        liked_by_me=bool(liked_by_me),
    )


async def _paginate(db: AsyncSession, stmt: Select[Any], page: int, limit: int) -> FeedPage:
    """Newest-first offset pagination; fetches one extra row to compute has_more."""
    stmt = stmt.order_by(Post.created_at.desc(), Post.id.desc()).offset((page - 1) * limit).limit(limit + 1)
    rows = (await db.execute(stmt)).all()
    return FeedPage(
        items=[_to_post_out(r) for r in rows[:limit]], page=page, limit=limit, has_more=len(rows) > limit
    )


async def get_feed(db: AsyncSession, user_id: uuid.UUID, page: int, limit: int) -> FeedPage:
    """Posts by the user and everyone they follow."""
    followed = select(Follow.following_id).where(Follow.follower_id == user_id)
    stmt = _post_select(user_id).where(or_(Post.user_id == user_id, Post.user_id.in_(followed)))
    return await _paginate(db, stmt, page, limit)


async def get_explore(db: AsyncSession, viewer_id: uuid.UUID | None, page: int, limit: int) -> FeedPage:
    """All posts, newest first — lets new users discover people to follow."""
    return await _paginate(db, _post_select(viewer_id), page, limit)


async def get_user_posts(
    db: AsyncSession, author_id: uuid.UUID, viewer_id: uuid.UUID | None, limit: int = 10
) -> list[PostOut]:
    """The author's most recent posts."""
    page = await _paginate(db, _post_select(viewer_id).where(Post.user_id == author_id), 1, limit)
    return page.items


async def get_post_out(db: AsyncSession, post_id: uuid.UUID, viewer_id: uuid.UUID | None) -> PostOut | None:
    """A single post with counts, or None."""
    row = (await db.execute(_post_select(viewer_id).where(Post.id == post_id))).first()
    return _to_post_out(row) if row else None
