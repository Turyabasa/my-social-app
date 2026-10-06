"""User profile, follow and notification tests."""

from httpx import AsyncClient
from starlette.testclient import TestClient

from app.main import app


async def test_follow_unfollow(users: dict[str, AsyncClient]) -> None:
    alice = users["alice"]
    first = await alice.post("/api/follows/BOB")
    assert first.status_code == 201 and first.json() == {"following": True, "followers_count": 1}
    again = await alice.post("/api/follows/bob")
    assert again.status_code == 201 and again.json()["followers_count"] == 1

    assert (await alice.post("/api/follows/alice")).status_code == 400
    assert (await alice.post("/api/follows/nobody")).status_code == 404

    assert (await alice.delete("/api/follows/bob")).status_code == 204
    assert (await alice.delete("/api/follows/bob")).status_code == 204
    assert (await alice.delete("/api/follows/nobody")).status_code == 404


async def test_follow_requires_auth(client: AsyncClient, users: dict[str, AsyncClient]) -> None:
    assert (await client.post("/api/follows/bob")).status_code == 401
    assert (await client.delete("/api/follows/bob")).status_code == 401


async def test_profile(users: dict[str, AsyncClient], client: AsyncClient) -> None:
    alice, bob, carol = users["alice"], users["bob"], users["carol"]
    for i in range(12):
        await bob.post("/api/posts", json={"content": f"post {i}"})
    await alice.post("/api/follows/bob")
    await carol.post("/api/follows/bob")
    await bob.post("/api/follows/alice")

    profile = (await alice.get("/api/users/bob")).json()
    assert profile["followers_count"] == 2
    assert profile["following_count"] == 1
    assert profile["posts_count"] == 12
    assert profile["is_following"] is True and profile["is_self"] is False
    assert len(profile["recent_posts"]) == 10
    assert profile["recent_posts"][0]["content"] == "post 11"

    own = (await bob.get("/api/users/bob")).json()
    assert own["is_self"] is True and own["is_following"] is False
    anon = (await client.get("/api/users/BOB")).json()
    assert anon["is_following"] is False and anon["is_self"] is False

    assert (await client.get("/api/users/nobody")).status_code == 404


async def test_followers_and_following_pagination(users: dict[str, AsyncClient], client: AsyncClient) -> None:
    await users["alice"].post("/api/follows/bob")
    await users["carol"].post("/api/follows/bob")

    page1 = (await client.get("/api/users/bob/followers", params={"limit": 1})).json()
    page2 = (await client.get("/api/users/bob/followers", params={"limit": 1, "page": 2})).json()
    assert page1["has_more"] is True and page2["has_more"] is False
    # Most recent follower first.
    assert [page1["items"][0]["username"], page2["items"][0]["username"]] == ["carol", "alice"]

    following = (await client.get("/api/users/alice/following")).json()
    assert [u["username"] for u in following["items"]] == ["bob"]
    assert (await client.get("/api/users/nobody/followers")).status_code == 404


async def test_suggestions_exclude_self_and_followed(users: dict[str, AsyncClient]) -> None:
    alice = users["alice"]
    await alice.post("/api/follows/bob")
    names = [u["username"] for u in (await alice.get("/api/suggestions")).json()["items"]]
    assert names == ["carol"]


async def test_websocket_rejects_bad_token() -> None:
    with TestClient(app) as tc:
        try:
            with tc.websocket_connect("/ws/notifications?token=bad") as ws:
                ws.receive_text()
        except Exception as exc:  # starlette raises WebSocketDisconnect on server-side close
            assert getattr(exc, "code", None) == 1008
        else:
            raise AssertionError("expected the socket to be closed")
