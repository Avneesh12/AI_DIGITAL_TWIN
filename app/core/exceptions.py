"""
app/core/exceptions.py
──────────────────────
Custom application exceptions + FastAPI exception handlers.
All errors return structured JSON with consistent shape.
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger


# ── Base ─────────────────────────────────────────────────────────────────────

class AppException(Exception):
    """Base class for all application-level exceptions."""
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred"

    def __init__(self, message: str | None = None, detail: str | None = None):
        self.message = message or self.__class__.message
        self.detail = detail
        super().__init__(self.message)


# ── Auth ─────────────────────────────────────────────────────────────────────

class AuthenticationError(AppException):
    status_code = 401
    error_code = "AUTHENTICATION_FAILED"
    message = "Authentication failed"


class TokenExpiredError(AppException):
    status_code = 401
    error_code = "TOKEN_EXPIRED"
    message = "Token has expired"


class InvalidTokenError(AppException):
    status_code = 401
    error_code = "INVALID_TOKEN"
    message = "Invalid token"


class PermissionDeniedError(AppException):
    status_code = 403
    error_code = "PERMISSION_DENIED"
    message = "Permission denied"


# ── Resource ─────────────────────────────────────────────────────────────────

class NotFoundError(AppException):
    status_code = 404
    error_code = "NOT_FOUND"
    message = "Resource not found"


class ConflictError(AppException):
    status_code = 409
    error_code = "CONFLICT"
    message = "Resource already exists"


# ── Validation ───────────────────────────────────────────────────────────────

class ValidationError(AppException):
    status_code = 422
    error_code = "VALIDATION_ERROR"
    message = "Validation failed"


# ── External Services ────────────────────────────────────────────────────────

class LLMServiceError(AppException):
    status_code = 502
    error_code = "LLM_SERVICE_ERROR"
    message = "LLM service returned an error"


class EmbeddingError(AppException):
    status_code = 502
    error_code = "EMBEDDING_ERROR"
    message = "Failed to generate embeddings"


class VectorStoreError(AppException):
    status_code = 502
    error_code = "VECTOR_STORE_ERROR"
    message = "Vector store operation failed"


# ── Handler Registration ─────────────────────────────────────────────────────

def register_exception_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to the FastAPI app."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        logger.warning(
            "App exception",
            error_code=exc.error_code,
            message=exc.message,
            detail=exc.detail,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
                "detail": exc.detail,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception", path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "detail": None,
            },
        )
