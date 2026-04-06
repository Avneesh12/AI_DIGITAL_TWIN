"""app/api/v1/auth.py — /register, /login, /refresh endpoints."""
from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import get_auth_service
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    data: RegisterRequest,
    auth_svc: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """Register a new user and return access + refresh tokens."""
    return await auth_svc.register(data)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    auth_svc: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """Authenticate an existing user."""
    return await auth_svc.login(data)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    data: RefreshRequest,
    auth_svc: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """Exchange a refresh token for a new token pair."""
    return await auth_svc.refresh(data.refresh_token)
