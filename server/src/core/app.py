from __future__ import annotations

import logging
from server.src.core.logging import get_logger
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from ..api.routes import (
    health,
    logs,
    nodes,
    reputations,
    transfer_grouped,
    transfers,
    overall_status,
    loggers,
    payout,
    held_amounts,
    paystubs,
    diskusage,
    satelliteusage,
    access_logs,
    dash,
)
from ..config import Settings
from ..database import configure_database, init_database
from ..services.cleanup import CleanupService
from ..services.log_monitor import LogMonitorService
from ..services.node_api import NodeApiService
from ..services.transfer_grouping import TransferGroupingService

logger = get_logger(__name__)


class SPAStaticFiles(StaticFiles):
    """Serve SPA assets with index.html fallback for client-side routes."""

    async def get_response(self, path: str, scope):  # type: ignore[override]
        response: Response = await super().get_response(path, scope)
        if response.status_code == 404:
            response = await super().get_response("index.html", scope)
        return response


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construct the FastAPI application with configured lifespan hooks."""
    settings = settings or Settings()
    configure_database(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        await init_database(settings)

        log_monitor = LogMonitorService(settings)
        nodeapi_service = NodeApiService(settings)
        cleanup_service = CleanupService(settings)
        transfer_grouping = TransferGroupingService(settings)

        await log_monitor.start()
        await nodeapi_service.start()
        await cleanup_service.start()
        await transfer_grouping.start()

        app.state.log_monitor = log_monitor
        app.state.nodeapi_service = nodeapi_service
        app.state.cleanup_service = cleanup_service
        app.state.transfer_grouping = transfer_grouping

        try:
            yield
        finally:
            await log_monitor.stop()
            await nodeapi_service.stop()
            await cleanup_service.stop()
            await transfer_grouping.stop()

    app = FastAPI(
        title="Monstr Log Monitor",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # Request-finish middleware: always-registered but gated by the runtime
    # setting `debug_log_request_finish` so it can be toggled via the admin API.

    class RequestFinishMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):

            start = time.time()
            response = await call_next(request)
            duration_ms = (time.time() - start) * 1000.0
            try:
                access_logger = logging.getLogger("api.call")
                # Only emit the message when the api.call logger is enabled
                # for DEBUG so this behavior is controlled entirely via
                # logging configuration (env/CLI/admin endpoints).
                if access_logger.isEnabledFor(logging.DEBUG):
                    client_addr = "-"
                    try:
                        client = request.client
                        if client:
                            client_addr = client[0] if isinstance(client, (list, tuple)) else getattr(client, "host", str(client))
                    except Exception:
                        client_addr = "-"

                    full_path = request.url.path or "/"
                    if request.url.query:
                        full_path = f"{full_path}?{request.url.query}"

                    access_logger.debug(
                        "Finished %s %s %s %s in %.3fms",
                        client_addr,
                        request.method,
                        full_path,
                        response.status_code,
                        duration_ms,
                    )
            except Exception:
                # Don't let logging errors break request handling
                pass
            return response

    app.add_middleware(RequestFinishMiddleware)

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
    app.include_router(loggers.router)
    app.include_router(payout.router)
    app.include_router(held_amounts.router)
    app.include_router(paystubs.router)
    app.include_router(diskusage.router)
    app.include_router(satelliteusage.router)
    app.include_router(access_logs.router)
    app.include_router(dash.router)

    frontend_path = settings.frontend_path
    if frontend_path and frontend_path.exists():
        app.mount(
            "/",
            SPAStaticFiles(directory=frontend_path, html=True),
            name="frontend",
        )
    else:
        logger.info(
            "Frontend build directory not found at %s. Serve API only.",
            frontend_path,
        )

    return app
