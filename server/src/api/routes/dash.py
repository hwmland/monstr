from __future__ import annotations

import urllib.parse
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ...config import Settings, SourceDefinition
from ...schemas import DashStorjNodeStatistics, DashStorjNodeStatus
from ...core.logging import get_logger

router = APIRouter(prefix="/api/dash", tags=["dash"])
logger = get_logger(__name__)

def get_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if isinstance(settings, Settings):
        return settings
    return Settings()

def _nodeapi_sources(settings: Settings) -> list[SourceDefinition]:
    try:
        sources = settings.parsed_sources
    except ValueError as exc:
        logger.warning("Invalid MONSTR_SOURCES configuration: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid MONSTR_SOURCES") from exc
    return [s for s in sources if s.nodeapi]

def _join_url(base: str, path: str) -> str:
    normalized_base = base.rstrip("/") + "/"
    return urllib.parse.urljoin(normalized_base, path.lstrip("/"))

async def _fetch_json(url: str) -> Any:
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        logger.warning("Dash proxy request failed for %s: %s", url, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Upstream error: {exc}") from exc
    except httpx.HTTPError as exc:
        logger.warning("Dash proxy request error for %s: %s", url, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Upstream request failed") from exc
    except ValueError as exc:
        logger.warning("Dash proxy response was not valid JSON from %s", url)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid JSON from upstream") from exc

@router.get("/nodes", response_model=list[str])
async def dash_nodes(settings: Settings = Depends(get_settings)) -> list[str]:
    sources = _nodeapi_sources(settings)
    return sorted({src.name for src in sources})

@router.get("/node-info", response_model=DashStorjNodeStatus)
async def dash_node_info(
    node_name: str = Query(..., alias="nodeName"),
    settings: Settings = Depends(get_settings),
) -> Any:
    sources = _nodeapi_sources(settings)
    source = next((s for s in sources if s.name == node_name), None)
    if source is None or not source.nodeapi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found or nodeapi not configured")

    url = _join_url(source.nodeapi, "/api/sno")
    data = await _fetch_json(url)

    # Censor sensitive identifiers before returning to the client
    try:
        data["nodeID"] = "Censored"
        data["wallet"] = "Censored"
        data["walletFeatures"] = ["Censored"]
    except Exception:
        logger.warning("Failed to censor node-info response", exc_info=True)

    return data

@router.get("/node-satellites", response_model=DashStorjNodeStatistics)
async def dash_node_satellites(
    node_name: str = Query(..., alias="nodeName"),
    settings: Settings = Depends(get_settings),
) -> Any:
    sources = _nodeapi_sources(settings)
    source = next((s for s in sources if s.name == node_name), None)
    if source is None or not source.nodeapi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found or nodeapi not configured")

    url = _join_url(source.nodeapi, "/api/sno/satellites")
    return await _fetch_json(url)
