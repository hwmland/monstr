from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ...config import Settings
from ...schemas import NodeConfig

router = APIRouter(prefix="/api/nodes", tags=["nodes"])


def get_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if isinstance(settings, Settings):
        return settings
    return Settings()


@router.get("", response_model=list[NodeConfig])
async def list_nodes(settings: Settings = Depends(get_settings)) -> list[NodeConfig]:
    """Return the configured log nodes with their resolved log paths."""
    nodes = []
    for name, path in settings.parsed_log_sources:
        nodes.append(NodeConfig(name=name, path=str(path)))
    for name, host, port in settings.parsed_remote_sources:
        nodes.append(NodeConfig(name=name, path=f"tcp://{host}:{port}"))
    return nodes
