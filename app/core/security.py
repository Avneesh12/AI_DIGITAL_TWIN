"""
app/core/security.py
────────────────────
Password hashing (argon2) and JWT creation/validation.
Argon2 is more secure than bcrypt — no 72-byte limit, memory-hard.
"""
from datetime import UTC, datetime, timedelta
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from jose import JWTError, jwt

from app.config import get_settings
from app.core.exceptions import InvalidTokenError, TokenExpiredError

settings = get_settings()

# ── Password Hashing ─────────────────────────────────────────────────────────

_hasher = PasswordHasher(
    time_cost=2,        # Number of iterations
    memory_cost=65536,  # 64MB memory usage
    parallelism=2,      # Number of parallel threads
    hash_len=32,        # Hash length in bytes
    salt_len=16,        # Salt length in bytes
)


def hash_password(password: str) -> str:
    """Hash password using Argon2id — no length limit, memory-hard."""
    return _hasher.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify password against Argon2 hash. Returns False if invalid."""
    try:
        return _hasher.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    """Check if hash needs upgrading (e.g. after changing parameters)."""
    return _hasher.check_needs_rehash(hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────

def _create_token(
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: str) -> str:
    return _create_token(
        subject=user_id,
        token_type="access",
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: str) -> str:
    return _create_token(
        subject=user_id,
        token_type="refresh",
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    """Decode and validate a JWT. Raises TokenExpiredError or InvalidTokenError."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except JWTError as e:
        if "expired" in str(e).lower():
            raise TokenExpiredError()
        raise InvalidTokenError(detail=str(e))

    if payload.get("type") != expected_type:
        raise InvalidTokenError(detail=f"Expected token type '{expected_type}'")

    return payload


def extract_user_id(token: str, expected_type: str = "access") -> str:
    payload = decode_token(token, expected_type)
    user_id = payload.get("sub")
    if not user_id:
        raise InvalidTokenError(detail="Missing subject claim")
    return user_id