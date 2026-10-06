"""Follow routes: follow and unfollow by username. Both are idempotent."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Path, Response, status
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from app.core.deps import CurrentUser, DbSession
from app.models import Follow
from app.routers.users import count_followers, get_user_or_404
from app.schemas import FollowStatus
from app.services.notification import notify

router = APIRouter()

UsernamePath = Annotated[str, Path(min_length=1, max_length=30)]


@router.post("/{username}", response_model=FollowStatus, status_code=status.HTTP_201_CREATED)
async def follow(
    username: UsernamePath, user: CurrentUser, db: DbSession, background: BackgroundTasks
) -> FollowStatus:
    """Follow a user. 400 on self-follow, 404 if the user doesn't exist."""
    target = await get_user_or_404(db, username)
    if target.id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't follow yourself")
    inserted = await db.scalar(
        insert(Follow)
        .values(follower_id=user.id, following_id=target.id)
        .on_conflict_do_nothing()
        .returning(Follow.following_id)
    )
    await db.commit()
    if inserted is not None:
        background.add_task(
            notify,
            target.id,
            actor_id=user.id,
            actor_username=user.username,
            actor_display_name=user.display_name,
            kind="follow",
        )
    return FollowStatus(following=True, followers_count=await count_followers(db, target.id))


@router.delete("/{username}", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow(username: UsernamePath, user: CurrentUser, db: DbSession) -> Response:
    """Unfollow a user. 404 if the user doesn't exist."""
    target = await get_user_or_404(db, username)
    await db.execute(delete(Follow).where(Follow.follower_id == user.id, Follow.following_id == target.id))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
