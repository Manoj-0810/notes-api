"""FastAPI application factory.

Configures middleware, exception handlers, and mounts all routers.
Auto-generates /openapi.json thanks to FastAPI's built-in support.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings
from app.database import engine, Base
from app.routers import auth, notes

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.ENVIRONMENT != "development" else logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Rate limiter: limits per IP address
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.NOTES_RATE_LIMIT} per minute"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler.

    Creates all database tables on startup (for dev convenience).
    In production, use Alembic migrations instead.
    """
    if settings.ENVIRONMENT == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables ensured (development mode)")

    logger.info(
        "%s starting in %s mode",
        settings.APP_NAME,
        settings.ENVIRONMENT,
    )
    yield

    await engine.dispose()
    logger.info("%s shutdown complete", settings.APP_NAME)


def create_app() -> FastAPI:
    """Application factory pattern.

    Creates and configures the FastAPI app with all middleware and routers.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        description="A production-grade multi-user notes REST API with versioning, tagging, and sharing.",
        version="1.0.0",
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global exception handler: don't leak internal errors
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Catch-all handler to prevent stack traces leaking to clients."""
        logger.exception("Unhandled exception on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    # Register routers (no prefix - paths are in the routers)
    app.include_router(auth.router)
    app.include_router(notes.router)

    return app


# Uvicorn entry point: uvicorn app.main:app
app = create_app()
