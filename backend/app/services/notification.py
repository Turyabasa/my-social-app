"""Real-time notifications pushed over WebSocket.

Connections are held in process memory, so this works with a single backend instance
(the Render free tier). Scaling out would need a shared pub/sub such as Redis or Postgres LISTEN/NOTIFY.
"""

import logging
import uuid
from collections import defaultdict
from typing import Literal, TypedDict

from fastapi import WebSocket

logger = logging.getLogger(__name__)

NotificationKind = Literal["like", "reply", "follow"]


class NotificationPayload(TypedDict):
    """Wire format sent to clients."""

    type: NotificationKind
    actor_username: str
    actor_display_name: str
    post_id: str | None


class NotificationManager:
    """Tracks open WebSockets per user and fans messages out to them."""

    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)

    async def connect(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        """Accept and register a socket for the user."""
        await websocket.accept()
        self._connections[user_id].add(websocket)

    def disconnect(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        """Forget a socket; drop the user's entry once empty."""
        sockets = self._connections.get(user_id)
        if sockets is None:
            return
        sockets.discard(websocket)
        if not sockets:
            del self._connections[user_id]

    async def send(self, user_id: uuid.UUID, payload: NotificationPayload) -> None:
        """Send to every socket the user has open, pruning dead ones."""
        for websocket in list(self._connections.get(user_id, ())):
            try:
                await websocket.send_json(payload)
            except Exception:  # client went away mid-send
                logger.debug("Dropping dead websocket for user %s", user_id)
                self.disconnect(user_id, websocket)


manager = NotificationManager()


async def notify(
    recipient_id: uuid.UUID,
    *,
    actor_id: uuid.UUID,
    actor_username: str,
    actor_display_name: str,
    kind: NotificationKind,
    post_id: uuid.UUID | None = None,
) -> None:
    """Push a notification to the recipient, skipping self-notifications."""
    if recipient_id == actor_id:
        return
    await manager.send(
        recipient_id,
        NotificationPayload(
            type=kind,
            actor_username=actor_username,
            actor_display_name=actor_display_name,
            post_id=str(post_id) if post_id else None,
        ),
    )
