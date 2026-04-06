"""
tests/integration/test_auth_api.py
────────────────────────────────────
Integration tests for auth endpoints.
Uses a mock DB session so no real database is required.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.user import User


def _make_mock_user(user_id: str | None = None) -> User:
    user = MagicMock(spec=User)
    user.id = uuid.UUID(user_id or str(uuid.uuid4()))
    user.email = "alice@example.com"
    user.username = "alice"
    user.is_active = True
    user.password_hash = "$2b$12$fakehashfakehashfakehashfakehashfakehash"
    return user


class TestRegister:

    @pytest.mark.asyncio
    async def test_register_success(self, async_client):
        mock_user = _make_mock_user()

        with (
            patch("app.repositories.user_repo.UserRepository.exists_email", new_callable=AsyncMock, return_value=False),
            patch("app.repositories.user_repo.UserRepository.exists_username", new_callable=AsyncMock, return_value=False),
            patch("app.repositories.user_repo.UserRepository.create", new_callable=AsyncMock, return_value=mock_user),
        ):
            resp = await async_client.post("/api/v1/auth/register", json={
                "email": "alice@example.com",
                "username": "alice",
                "password": "supersecret123",
            })

        assert resp.status_code == 201
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, async_client):
        with patch("app.repositories.user_repo.UserRepository.exists_email", new_callable=AsyncMock, return_value=True):
            resp = await async_client.post("/api/v1/auth/register", json={
                "email": "alice@example.com",
                "username": "alice2",
                "password": "supersecret123",
            })

        assert resp.status_code == 409
        assert resp.json()["error"] == "CONFLICT"

    @pytest.mark.asyncio
    async def test_register_short_password(self, async_client):
        resp = await async_client.post("/api/v1/auth/register", json={
            "email": "bob@example.com",
            "username": "bob",
            "password": "short",
        })
        assert resp.status_code == 422  # Pydantic validation

    @pytest.mark.asyncio
    async def test_register_invalid_username(self, async_client):
        resp = await async_client.post("/api/v1/auth/register", json={
            "email": "bob@example.com",
            "username": "bo",  # too short
            "password": "validpassword",
        })
        assert resp.status_code == 422


class TestLogin:

    @pytest.mark.asyncio
    async def test_login_success(self, async_client):
        from app.core.security import hash_password
        mock_user = _make_mock_user()
        mock_user.password_hash = hash_password("password123")

        with patch("app.repositories.user_repo.UserRepository.get_by_email", new_callable=AsyncMock, return_value=mock_user):
            resp = await async_client.post("/api/v1/auth/login", json={
                "email": "alice@example.com",
                "password": "password123",
            })

        assert resp.status_code == 200
        assert "access_token" in resp.json()

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, async_client):
        from app.core.security import hash_password
        mock_user = _make_mock_user()
        mock_user.password_hash = hash_password("correctpassword")

        with patch("app.repositories.user_repo.UserRepository.get_by_email", new_callable=AsyncMock, return_value=mock_user):
            resp = await async_client.post("/api/v1/auth/login", json={
                "email": "alice@example.com",
                "password": "wrongpassword",
            })

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_user_not_found(self, async_client):
        with patch("app.repositories.user_repo.UserRepository.get_by_email", new_callable=AsyncMock, return_value=None):
            resp = await async_client.post("/api/v1/auth/login", json={
                "email": "ghost@example.com",
                "password": "password123",
            })
        assert resp.status_code == 401


class TestRefresh:

    @pytest.mark.asyncio
    async def test_refresh_success(self, async_client):
        from app.core.security import create_refresh_token
        user_id = str(uuid.uuid4())
        mock_user = _make_mock_user(user_id)
        refresh_token = create_refresh_token(user_id)

        with patch("app.repositories.user_repo.UserRepository.get_by_id", new_callable=AsyncMock, return_value=mock_user):
            resp = await async_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

        assert resp.status_code == 200
        assert "access_token" in resp.json()

    @pytest.mark.asyncio
    async def test_refresh_with_access_token_fails(self, async_client):
        from app.core.security import create_access_token
        access_token = create_access_token(str(uuid.uuid4()))

        resp = await async_client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
        assert resp.status_code == 401
