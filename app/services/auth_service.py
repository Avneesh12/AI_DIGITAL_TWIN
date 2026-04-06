"""app/services/auth_service.py — Registration, login, token lifecycle."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    extract_user_id,
    hash_password,
    verify_password,
)
from app.repositories.user_repo import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


class AuthService:
    def __init__(self, user_repo: UserRepository) -> None:
        self._users = user_repo

    async def register(self, data: RegisterRequest) -> TokenResponse:
        if await self._users.exists_email(data.email):
            raise ConflictError("Email already registered")
        if await self._users.exists_username(data.username):
            raise ConflictError("Username already taken")

        user = await self._users.create(
            email=data.email,
            username=data.username,
            password_hash=hash_password(data.password),
        )

        return TokenResponse(
            access_token=create_access_token(str(user.id)),
            refresh_token=create_refresh_token(str(user.id)),
        )

    async def login(self, data: LoginRequest) -> TokenResponse:
        user = await self._users.get_by_email(data.email)
        if user is None or not verify_password(data.password, user.password_hash):
            raise AuthenticationError("Invalid email or password")
        if not user.is_active:
            raise AuthenticationError("Account is deactivated")

        return TokenResponse(
            access_token=create_access_token(str(user.id)),
            refresh_token=create_refresh_token(str(user.id)),
        )

    async def refresh(self, refresh_token: str) -> TokenResponse:
        user_id = extract_user_id(refresh_token, expected_type="refresh")
        # Verify user still exists and is active
        import uuid
        user = await self._users.get_by_id(uuid.UUID(user_id))
        if user is None or not user.is_active:
            raise AuthenticationError("User not found or inactive")

        return TokenResponse(
            access_token=create_access_token(user_id),
            refresh_token=create_refresh_token(user_id),
        )
