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
    # Only the unified `sources` list is supported. Map file vs remote entries
    # directly and preserve the declared order. Malformed entries are ignored.
    for raw in (settings.sources or []):
        parts = raw.split(":")
        if len(parts) == 3:
            name, host, port = parts
            nodes.append(NodeConfig(name=name.strip(), path=f"tcp://{host.strip()}:{port.strip()}"))
            continue
        if ":" in raw:
            name, path = raw.split(":", 1)
            nodes.append(NodeConfig(name=name.strip(), path=path.strip()))
            continue
        # ignore malformed entries

    return nodes
