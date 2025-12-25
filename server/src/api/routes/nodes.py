from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import Settings
from ...core.logging import get_logger
from ...database import get_session
from ...schemas import NodeConfig
from ...services.node_api import NodeApiService, NodeData
from ._access_log import extract_client_meta, persist_access_log

router = APIRouter(prefix="/api/nodes", tags=["nodes"])
logger = get_logger(__name__)


def get_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if isinstance(settings, Settings):
        return settings
    return Settings()


def _get_nodeapi_service(request: Request) -> NodeApiService | None:
    svc = getattr(request.app.state, "nodeapi_service", None) or getattr(
        request.app.state,
        "node_api_service",
        None,
    )
    if isinstance(svc, NodeApiService):
        return svc
    return None


@router.get("", response_model=list[NodeConfig])
async def list_nodes(
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> list[NodeConfig]:
    """Return the configured log nodes with their resolved log paths."""
    try:
        sources = settings.parsed_sources
    except ValueError:
        return []

    client_host, client_port, forwarded_for, real_ip, user_agent = extract_client_meta(request)

    try:
        await persist_access_log(
            session,
            host=client_host,
            port=client_port,
            forwarded_for=forwarded_for,
            real_ip=real_ip,
            user_agent=user_agent,
        )
    except Exception:
        logger.warning("Failed to persist access log entry", exc_info=True)

    nodeapi_service = _get_nodeapi_service(request)
    node_data_map: dict[str, NodeData] = {}
    if nodeapi_service is not None:
        try:
            node_data_map = await nodeapi_service.get_node_data([src.name for src in sources] or None)
        except Exception:
            node_data_map = {}

    nodes: list[NodeConfig] = []
    for source in sources:
        node_state = node_data_map.get(source.name) if node_data_map else None
        vetting = None
        if node_state is not None:
            state_vetting = getattr(node_state, "vetting_date", None)
            if state_vetting:
                vetting = dict(state_vetting)

        if source.kind == "file" and source.path is not None:
            nodes.append(
                NodeConfig(name=source.name, path=str(source.path), nodeapi=source.nodeapi, vetting=vetting)
            )
            continue

        if source.kind == "tcp" and source.host is not None and source.port is not None:
            nodes.append(
                NodeConfig(
                    name=source.name,
                    path=f"tcp://{source.host}:{source.port}",
                    nodeapi=source.nodeapi,
                    vetting=vetting,
                )
            )

    return nodes
