"""Post model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utcnow

if TYPE_CHECKING:
    from app.models.like import Like
    from app.models.reply import Reply
    from app.models.user import User


class Post(Base):
    """A top-level post (tweet) of at most 280 characters."""

    __tablename__ = "posts"
    # (user_id, created_at) serves both "posts by user" lookups and the reverse-chronological feed.
    __table_args__ = (Index("ix_posts_user_id_created_at", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(String(280))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), index=True
    )

    user: Mapped["User"] = relationship(back_populates="posts", lazy="raise")
    likes: Mapped[list["Like"]] = relationship(
        back_populates="post", cascade="all, delete-orphan", passive_deletes=True, lazy="raise"
    )
    replies: Mapped[list["Reply"]] = relationship(
        back_populates="post", cascade="all, delete-orphan", passive_deletes=True, lazy="raise"
    )
