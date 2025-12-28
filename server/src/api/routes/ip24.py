from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ...config import Settings
from ...core.logging import get_logger
from ...services.ip24 import IP24Service
from ...schemas import IP24StatusEntry

router = APIRouter(prefix="/api/ip24", tags=["ip24"])
logger = get_logger(__name__)


def get_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if isinstance(settings, Settings):
        return settings
    return Settings()


def _get_ip24_service(request: Request) -> IP24Service | None:
    svc = getattr(request.app.state, "ip24_service", None)
    if isinstance(svc, IP24Service):
        return svc
    return None


@router.get("", response_model=dict[str, IP24StatusEntry])
async def get_ip24_status(request: Request, settings: Settings = Depends(get_settings)):
    service = _get_ip24_service(request)
    if service is None:
        logger.info("IP24Service not available; returning empty status")
        return {}
    return await service.get_status()
