from __future__ import annotations

from fastapi import APIRouter, Request

from ...config import Settings
from ...schemas import NodeGroupRead

router = APIRouter(prefix="/api/nodegroups", tags=["nodegroups"])


@router.get("", response_model=list[NodeGroupRead])
async def list_nodegroups(request: Request) -> list[NodeGroupRead]:
    """Return active configured nodegroups with flattened node names."""
    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, Settings) or not settings.has_active_nodegroups:
        return []

    return [
        NodeGroupRead(
            name=group.name,
            nodes=[node.name for location in group.locations for node in location.nodes],
            icon=group.icon,
        )
        for group in settings.nodegroups
    ]
