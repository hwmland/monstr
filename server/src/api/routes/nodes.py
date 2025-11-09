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
    try:
        sources = settings.parsed_sources
    except ValueError:
        return []

    nodes: list[NodeConfig] = []
    for source in sources:
        if source.kind == "file" and source.path is not None:
            nodes.append(
                NodeConfig(name=source.name, path=str(source.path), nodeapi=source.nodeapi)
            )
            continue

        if source.kind == "tcp" and source.host is not None and source.port is not None:
            nodes.append(
                NodeConfig(
                    name=source.name,
                    path=f"tcp://{source.host}:{source.port}",
                    nodeapi=source.nodeapi,
                )
            )

    return nodes
