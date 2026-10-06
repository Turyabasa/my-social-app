"""Like model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utcnow

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.user import User


class Like(Base):
    """A user's like on a post; the composite PK makes it one like per user per post."""

    __tablename__ = "likes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # Indexed separately so counting likes per post doesn't scan the whole table.
    post_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="likes", lazy="raise")
    post: Mapped["Post"] = relationship(back_populates="likes", lazy="raise")
