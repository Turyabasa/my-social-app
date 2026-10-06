"""WebSocket endpoint streaming real-time notifications (likes, replies, follows)."""

import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.security import decode_token
from app.services.notification import manager

router = APIRouter()


@router.websocket("/ws/notifications")
async def notifications_ws(websocket: WebSocket, token: str = Query(...)) -> None:
    """Authenticate with a short-lived token from GET /api/auth/ws-token, then receive JSON events."""
    subject = decode_token(token, token_type="ws")
    if subject is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    user_id = uuid.UUID(subject)
    await manager.connect(user_id, websocket)
    try:
        while True:
            # Clients may send pings; the content is ignored. This also detects disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(user_id, websocket)
