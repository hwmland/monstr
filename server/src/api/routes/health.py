from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", summary="Application health probe")
async def healthcheck() -> dict[str, str]:
    """Simple health probe endpoint used for readiness checks."""
    return {"status": "ok"}
