from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ..api.routes import health, logs, nodes, reputations, transfers
from ..config import Settings
from ..database import init_database
from ..services.cleanup import CleanupService
from ..services.log_monitor import LogMonitorService

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construct the FastAPI application with configured lifespan hooks."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        await init_database()

        log_monitor = LogMonitorService(settings)
        cleanup_service = CleanupService(settings)

        await log_monitor.start()
        await cleanup_service.start()

        app.state.log_monitor = log_monitor
        app.state.cleanup_service = cleanup_service

        try:
            yield
        finally:
            await log_monitor.stop()
            await cleanup_service.stop()

    app = FastAPI(
        title="Monstr Log Monitor",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    app.include_router(health.router)
    app.include_router(logs.router)
    app.include_router(nodes.router)
    app.include_router(reputations.router)
    app.include_router(transfers.router)

    frontend_path = settings.frontend_path
    if frontend_path and frontend_path.exists():
        app.mount(
            "/",
            StaticFiles(directory=frontend_path, html=True),
            name="frontend",
        )
    else:
        logger.info(
            "Frontend build directory not found at %s. Serve API only.",
            frontend_path,
        )

    return app
