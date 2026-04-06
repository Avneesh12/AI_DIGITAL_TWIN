"""
app/main.py
────────────
FastAPI application factory.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.v1.router import api_router
from app.config import get_settings
from app.core.database import engine
from app.core.embedder import get_embedder
from app.core.exceptions import register_exception_handlers
from app.core.qdrant_client import ensure_collection_exists, get_qdrant_client

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Digital Twin API", env=settings.APP_ENV)

    import os
    import asyncio
    from alembic.config import Config
    from alembic import command
    from app.core.database import Base, engine
    from app.models.user import User
    from app.models.chat import Chat
    from app.models.personality import PersonalityProfile
    from app.models.decision import Decision

    # Step 1 — DB tables
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables ready ✓")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise  # fatal — can't run without DB

# Run this in terminal

    # Step 2 — Migrations
    try:
        def apply_migrations():
            alembic_cfg = Config(
                os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
            )
            command.upgrade(alembic_cfg, "head")

        await asyncio.get_event_loop().run_in_executor(None, apply_migrations)
        logger.info("Migrations applied ✓")
    except Exception as e:
        logger.error(f"Migrations failed: {e}")
        raise  # fatal — schema may be out of sync

    # Step 3 — Embedder (non-fatal)
    try:
        embedder = get_embedder()
        logger.info("Embedder ready", dimension=embedder.dimension)
    except Exception as e:
        logger.warning(f"Embedder init failed (non-fatal): {e}")

    # Step 4 — Qdrant (non-fatal)
    try:
        qdrant = get_qdrant_client()
        await ensure_collection_exists(qdrant)
        logger.info("Qdrant ready ✓")
    except Exception as e:
        logger.warning(f"Qdrant connection failed (non-fatal): {e}")
        qdrant = None  # handle None safely in routes

    logger.info("API startup complete — ready to serve requests")
    yield

    # Shutdown
    try:
        await engine.dispose()
    except Exception as e:
        logger.warning(f"Engine dispose error: {e}")

    try:
        if qdrant:
            await qdrant.close()
    except Exception as e:
        logger.warning(f"Qdrant close error: {e}")

    logger.info("Shutdown complete")

def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Digital Twin API",
        description=(
            "A continuously evolving personal AI agent that understands, remembers, "
            "and speaks like its user."
        ),
        version="1.0.0",
        docs_url="/docs",   # always show docs during development
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.APP_DEBUG else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    register_exception_handlers(app)

    @app.get("/", tags=["Root"])
    async def root() -> dict:
        return {"message": "System Running", "version": "1.0.0", "env": settings.APP_ENV}

    @app.get("/health", tags=["System"])   # ✅ Fixed: was unreachable before
    async def health() -> dict:
        return {"status": "ok", "version": "1.0.0", "env": settings.APP_ENV}

    return app


app = create_app()

