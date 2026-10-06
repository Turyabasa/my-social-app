"""Post routes: create, feed, explore, detail, delete, like toggle, replies."""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import joinedload

from app.core.deps import CurrentUser, DbSession, OptionalUser
from app.models import Like, Post, Reply, User
from app.schemas import (
    FeedPage,
    LikeStatus,
    PostCreate,
    PostDetail,
    PostOut,
    ReplyCreate,
    ReplyOut,
    UserPublic,
)
from app.services import feed
from app.services.notification import notify

router = APIRouter()

Page = Annotated[int, Query(ge=1, le=10_000)]
Limit = Annotated[int, Query(ge=1, le=100)]


def _reply_out(reply: Reply, author: User) -> ReplyOut:
    return ReplyOut(
        id=reply.id,
        post_id=reply.post_id,
        content=reply.content,
        created_at=reply.created_at,
        author=UserPublic.model_validate(author),
    )


async def _get_post_or_404(db: DbSession, post_id: uuid.UUID) -> Post:
    post = await db.get(Post, post_id)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    return post


@router.post("/posts", response_model=PostOut, status_code=status.HTTP_201_CREATED)
async def create_post(body: PostCreate, user: CurrentUser, db: DbSession) -> PostOut:
    """Create a post (max 280 chars) as the current user."""
    post = Post(user_id=user.id, content=body.content)
    db.add(post)
    await db.commit()
    return PostOut(
        id=post.id,
        content=post.content,
        created_at=post.created_at,
        author=UserPublic.model_validate(user),
        like_count=0,
        reply_count=0,
        liked_by_me=False,
    )


@router.get("/feed", response_model=FeedPage)
async def get_feed(user: CurrentUser, db: DbSession, page: Page = 1, limit: Limit = 20) -> FeedPage:
    """Paginated posts from the current user and everyone they follow, newest first."""
    return await feed.get_feed(db, user.id, page, limit)


@router.get("/explore", response_model=FeedPage)
async def get_explore(user: OptionalUser, db: DbSession, page: Page = 1, limit: Limit = 20) -> FeedPage:
    """Paginated posts from everyone, newest first."""
    return await feed.get_explore(db, user.id if user else None, page, limit)


@router.get("/posts/{post_id}", response_model=PostDetail)
async def get_post(post_id: uuid.UUID, user: OptionalUser, db: DbSession) -> PostDetail:
    """A post plus all of its replies (oldest first)."""
    post = await feed.get_post_out(db, post_id, user.id if user else None)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    replies = await db.scalars(
        select(Reply)
        .options(joinedload(Reply.user))
        .where(Reply.post_id == post_id)
        .order_by(Reply.created_at, Reply.id)
    )
    return PostDetail(post=post, replies=[_reply_out(r, r.user) for r in replies])


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(post_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    """Delete a post (owner only). Likes and replies cascade in the database."""
    post = await _get_post_or_404(db, post_id)
    if post.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only delete your own posts")
    await db.execute(delete(Post).where(Post.id == post_id))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/posts/{post_id}/like", response_model=LikeStatus, status_code=status.HTTP_201_CREATED)
async def toggle_like(
    post_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    response: Response,
    background: BackgroundTasks,
) -> LikeStatus:
    """Toggle the current user's like: 201 when a like is created, 200 when it is removed."""
    post = await _get_post_or_404(db, post_id)
    inserted = await db.scalar(
        insert(Like)
        .values(user_id=user.id, post_id=post_id)
        .on_conflict_do_nothing()
        .returning(Like.post_id)
    )
    liked = inserted is not None
    if not liked:
        await db.execute(delete(Like).where(Like.user_id == user.id, Like.post_id == post_id))
        response.status_code = status.HTTP_200_OK
    await db.commit()

    like_count = await db.scalar(select(func.count()).select_from(Like).where(Like.post_id == post_id)) or 0
    if liked:
        background.add_task(
            notify,
            post.user_id,
            actor_id=user.id,
            actor_username=user.username,
            actor_display_name=user.display_name,
            kind="like",
            post_id=post_id,
        )
    return LikeStatus(liked=liked, like_count=like_count)


@router.post("/posts/{post_id}/replies", response_model=ReplyOut, status_code=status.HTTP_201_CREATED)
async def create_reply(
    post_id: uuid.UUID,
    body: ReplyCreate,
    user: CurrentUser,
    db: DbSession,
    background: BackgroundTasks,
) -> ReplyOut:
    """Reply to a post (max 280 chars)."""
    post = await _get_post_or_404(db, post_id)
    reply = Reply(post_id=post_id, user_id=user.id, content=body.content)
    db.add(reply)
    await db.commit()
    background.add_task(
        notify,
        post.user_id,
        actor_id=user.id,
        actor_username=user.username,
        actor_display_name=user.display_name,
        kind="reply",
        post_id=post_id,
    )
    return _reply_out(reply, user)
