# tests/test_auth.py
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    r = await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "SuperSecret123"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data.get("token_type") == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    await client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "SuperSecret123"},
    )
    r = await client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "OtherPass456"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    await client.post(
        "/auth/register",
        json={"email": "login@example.com", "password": "SuperSecret123"},
    )
    r = await client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": "SuperSecret123"},
    )
    assert r.status_code == 200
    assert "access_token" in r.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post(
        "/auth/register",
        json={"email": "wrong@example.com", "password": "SuperSecret123"},
    )
    r = await client.post(
        "/auth/login",
        json={"email": "wrong@example.com", "password": "WrongPass"},
    )
    assert r.status_code == 401
