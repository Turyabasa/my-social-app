"""Auth endpoint tests."""

from httpx import AsyncClient

REGISTER = {"email": "Alice@Example.com", "username": "Alice_1", "password": "password123"}


async def test_register_sets_httponly_cookie_and_normalizes(client: AsyncClient) -> None:
    resp = await client.post("/api/auth/register", json=REGISTER)
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "alice_1"
    assert body["email"] == "alice@example.com"
    assert "password_hash" not in body
    cookie = resp.headers["set-cookie"]
    assert "access_token=" in cookie and "HttpOnly" in cookie

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == body["id"]


async def test_register_duplicates_conflict(client: AsyncClient) -> None:
    await client.post("/api/auth/register", json=REGISTER)
    dup_email = await client.post("/api/auth/register", json={**REGISTER, "username": "other"})
    dup_username = await client.post("/api/auth/register", json={**REGISTER, "email": "x@example.com"})
    assert dup_email.status_code == 409
    assert dup_username.status_code == 409


async def test_register_validation(client: AsyncClient) -> None:
    bad = [
        {**REGISTER, "username": "has space"},
        {**REGISTER, "username": "a" * 31},
        {**REGISTER, "password": "short"},
        {**REGISTER, "email": "not-an-email"},
    ]
    for payload in bad:
        resp = await client.post("/api/auth/register", json=payload)
        assert resp.status_code == 422, payload
        assert isinstance(resp.json()["detail"], str)


async def test_login_logout(client: AsyncClient) -> None:
    await client.post("/api/auth/register", json=REGISTER)
    client.cookies.clear()

    wrong = await client.post("/api/auth/login", json={"email": "alice@example.com", "password": "nope"})
    assert wrong.status_code == 401
    unknown = await client.post("/api/auth/login", json={"email": "no@example.com", "password": "password123"})
    assert unknown.status_code == 401

    ok = await client.post("/api/auth/login", json={"email": "ALICE@example.com", "password": "password123"})
    assert ok.status_code == 200
    assert (await client.get("/api/auth/me")).status_code == 200

    out = await client.post("/api/auth/logout")
    assert out.status_code == 200
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_me_rejects_invalid_token(client: AsyncClient) -> None:
    client.cookies.set("access_token", "garbage")
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_ws_token_is_not_an_access_token(client: AsyncClient) -> None:
    await client.post("/api/auth/register", json=REGISTER)
    token = (await client.get("/api/auth/ws-token")).json()["token"]
    client.cookies.clear()
    client.cookies.set("access_token", token)
    assert (await client.get("/api/auth/me")).status_code == 401
