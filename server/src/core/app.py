from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ..api.routes import health, logs, nodes, reputations, transfer_grouped, transfers, overall_status
from ..config import Settings
from ..database import configure_database, init_database
from ..services.cleanup import CleanupService
from ..services.log_monitor import LogMonitorService
from ..services.transfer_grouping import TransferGroupingService

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construct the FastAPI application with configured lifespan hooks."""
    settings = settings or Settings()
    configure_database(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        await init_database(settings)

        log_monitor = LogMonitorService(settings)
        cleanup_service = CleanupService(settings)
        transfer_grouping = TransferGroupingService(settings)

        await log_monitor.start()
        await cleanup_service.start()
        await transfer_grouping.start()

        app.state.log_monitor = log_monitor
        app.state.cleanup_service = cleanup_service
        app.state.transfer_grouping = transfer_grouping

        try:
            yield
        finally:
            await log_monitor.stop()
            await cleanup_service.stop()
            await transfer_grouping.stop()

    app = FastAPI(
        title="Monstr Log Monitor",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # Expose settings early so request handlers can access configuration even if
    # startup lifespan hooks are bypassed (e.g. during direct testing scenarios).
    app.state.settings = settings

    if settings.cors_allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allow_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(health.router)
    app.include_router(logs.router)
    app.include_router(nodes.router)
    app.include_router(reputations.router)
    app.include_router(transfer_grouped.router)
    app.include_router(transfers.router)
    app.include_router(overall_status.router)

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
