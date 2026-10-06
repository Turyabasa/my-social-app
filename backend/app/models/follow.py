"""Follow model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utcnow

if TYPE_CHECKING:
    from app.models.user import User


class Follow(Base):
    """A directed edge: follower_id follows following_id."""

    __tablename__ = "follows"
    __table_args__ = (CheckConstraint("follower_id <> following_id", name="ck_follows_no_self_follow"),)

    follower_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # Indexed separately: the PK only covers lookups that start with follower_id.
    following_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )

    follower_user: Mapped["User"] = relationship(
        foreign_keys=[follower_id], back_populates="following", lazy="raise"
    )
    followed_user: Mapped["User"] = relationship(
        foreign_keys=[following_id], back_populates="followers", lazy="raise"
    )
