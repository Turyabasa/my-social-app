"""Post, feed, like and reply endpoint tests."""

from httpx import AsyncClient

MISSING = "00000000-0000-0000-0000-000000000000"


async def _post(c: AsyncClient, content: str) -> str:
    resp = await c.post("/api/posts", json={"content": content})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_create_post_validation(users: dict[str, AsyncClient], client: AsyncClient) -> None:
    alice = users["alice"]
    resp = await alice.post("/api/posts", json={"content": "  hello  "})
    assert resp.status_code == 201
    assert resp.json()["content"] == "hello"
    assert resp.json()["author"]["username"] == "alice"

    assert (await alice.post("/api/posts", json={"content": "   "})).status_code == 422
    assert (await alice.post("/api/posts", json={"content": "x" * 281})).status_code == 422
    assert (await alice.post("/api/posts", json={"content": "x" * 280})).status_code == 201
    assert (await client.post("/api/posts", json={"content": "anon"})).status_code == 401


async def test_feed_contains_self_and_followed_only(users: dict[str, AsyncClient]) -> None:
    alice, bob, carol = users["alice"], users["bob"], users["carol"]
    await _post(alice, "alice 1")
    await _post(bob, "bob 1")
    await _post(carol, "carol 1")
    await alice.post("/api/follows/bob")

    feed = (await alice.get("/api/feed")).json()
    assert [p["content"] for p in feed["items"]] == ["bob 1", "alice 1"]
    assert feed["has_more"] is False

    page1 = (await alice.get("/api/feed", params={"limit": 1})).json()
    page2 = (await alice.get("/api/feed", params={"limit": 1, "page": 2})).json()
    assert page1["has_more"] is True and page2["has_more"] is False
    assert page1["items"][0]["content"] == "bob 1" and page2["items"][0]["content"] == "alice 1"

    assert (await alice.get("/api/feed", params={"limit": 101})).status_code == 422


async def test_feed_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/feed")).status_code == 401


async def test_like_toggle_and_counts(users: dict[str, AsyncClient], client: AsyncClient) -> None:
    alice, bob = users["alice"], users["bob"]
    post_id = await _post(bob, "like me")

    first = await alice.post(f"/api/posts/{post_id}/like")
    assert first.status_code == 201 and first.json() == {"liked": True, "like_count": 1}
    second = await alice.post(f"/api/posts/{post_id}/like")
    assert second.status_code == 200 and second.json() == {"liked": False, "like_count": 0}
    await alice.post(f"/api/posts/{post_id}/like")

    detail = (await alice.get(f"/api/posts/{post_id}")).json()
    assert detail["post"]["like_count"] == 1 and detail["post"]["liked_by_me"] is True
    anon = (await client.get(f"/api/posts/{post_id}")).json()
    assert anon["post"]["liked_by_me"] is False

    assert (await alice.post(f"/api/posts/{MISSING}/like")).status_code == 404


async def test_replies(users: dict[str, AsyncClient]) -> None:
    alice, bob = users["alice"], users["bob"]
    post_id = await _post(bob, "reply to me")
    r1 = await alice.post(f"/api/posts/{post_id}/replies", json={"content": "first"})
    r2 = await bob.post(f"/api/posts/{post_id}/replies", json={"content": "second"})
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["author"]["username"] == "alice"

    detail = (await alice.get(f"/api/posts/{post_id}")).json()
    assert detail["post"]["reply_count"] == 2
    assert [r["content"] for r in detail["replies"]] == ["first", "second"]

    assert (await alice.post(f"/api/posts/{post_id}/replies", json={"content": ""})).status_code == 422
    assert (await alice.post(f"/api/posts/{MISSING}/replies", json={"content": "x"})).status_code == 404


async def test_get_post_errors(client: AsyncClient) -> None:
    assert (await client.get(f"/api/posts/{MISSING}")).status_code == 404
    assert (await client.get("/api/posts/not-a-uuid")).status_code == 422


async def test_delete_owner_only_and_cascades(users: dict[str, AsyncClient]) -> None:
    alice, bob = users["alice"], users["bob"]
    post_id = await _post(bob, "delete me")
    await alice.post(f"/api/posts/{post_id}/like")
    await alice.post(f"/api/posts/{post_id}/replies", json={"content": "hi"})

    assert (await alice.delete(f"/api/posts/{post_id}")).status_code == 403
    assert (await bob.delete(f"/api/posts/{post_id}")).status_code == 204
    assert (await bob.get(f"/api/posts/{post_id}")).status_code == 404
    assert (await bob.delete(f"/api/posts/{post_id}")).status_code == 404


async def test_explore_shows_everyone(users: dict[str, AsyncClient], client: AsyncClient) -> None:
    await _post(users["carol"], "carol explore")
    items = (await client.get("/api/explore")).json()["items"]
    assert [p["content"] for p in items] == ["carol explore"]
