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
import os
import uvicorn
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Digital Twin API", env=settings.APP_ENV)

    import os
    import asyncio
    from alembic.config import Config
    from alembic import command
    from app.core.database import Base, engine
    from app.models.user import User                       # noqa
    from app.models.chat import Chat                       # noqa
    from app.models.personality import PersonalityProfile  # noqa
    from app.models.decision import Decision               # noqa

    # Step 1 — Create any new tables that don't exist yet
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ready ✓")

    # Step 2 — Apply any migration files present in versions/
    def apply_migrations():
        alembic_cfg = Config(
            os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
        )
        command.upgrade(alembic_cfg, "head")

    await asyncio.get_event_loop().run_in_executor(None, apply_migrations)
    logger.info("Migrations applied ✓")

    embedder = get_embedder()
    logger.info("Embedder ready", dimension=embedder.dimension)

    qdrant = get_qdrant_client()
    await ensure_collection_exists(qdrant)
    logger.info("Qdrant ready")

    logger.info("API startup complete — ready to serve requests")
    yield

    logger.info("Shutting down API")
    await engine.dispose()
    await qdrant.close()
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



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))  # ✅ important
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
