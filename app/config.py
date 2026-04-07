"""
app/config.py
─────────────
Centralized configuration using Pydantic BaseSettings.
All values are loaded from environment variables / .env file.
"""
from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # ✅ silently ignores unknown env vars
    )

    # ── Application ──────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    APP_DEBUG: bool = False
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    SECRET_KEY: str

    # ── JWT ──────────────────────────────────────────────────────────────────
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── PostgreSQL ───────────────────────────────────────────────────────────
    DB_USER: str 
    DB_PASSWORD: str 
    DB_HOST: str 
    DB_PORT: str 
    DB_NAME: str 

    # ── Qdrant ───────────────────────────────────────────────────────────────
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION: str = "memories"

    # ── Grok API ─────────────────────────────────────────────────────────────
    GROK_API_KEY: str
    GROK_API_BASE: str = "https://api.x.ai/v1"
    GROK_MODEL: str = "grok-beta"

    # ── Embeddings ───────────────────────────────────────────────────────────
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    HF_TOKEN: str | None = None 
    EMBEDDING_DIMENSION: int = 384

    # ── Memory / RAG ─────────────────────────────────────────────────────────
    MEMORY_TOP_K: int = 5
    MEMORY_SCORE_THRESHOLD: float = 0.72

    # ── Redis ────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Rate Limiting ────────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 60

    BREVO_API_KEY : str
    EMAIL_SENDER : str
    EMAIL_SENDER_NAME : str 
    FRONTEND_URL : str 

    @property
    def DATABASE_URL(self):
        return (
            f"postgresql+asyncpg://{self.DB_USER}:"
            f"{self.DB_PASSWORD}@{self.DB_HOST}:"
            f"{self.DB_PORT}/{self.DB_NAME}"
        )
    
    @property
    def SYNC_DATABASE_URL(self):
        return (
            f"postgresql://{self.DB_USER}:"
            f"{self.DB_PASSWORD}@{self.DB_HOST}:"
            f"{self.DB_PORT}/{self.DB_NAME}"
        )

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_min_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return v


@lru_cache()  # ✅ Fixed: parentheses required for correct decorator behavior
def get_settings() -> Settings:
    """Cached settings singleton — safe to call repeatedly."""
    return Settings()