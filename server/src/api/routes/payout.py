from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import select

from ...config import Settings
from ... import database
from ...models import Paystub
from ...services.node_api import NodeApiService
from ...schemas import (
    PayoutCurrentRequest,
    PayoutCurrentResponse,
    PayoutNode,
    PayoutPaystubsRequest,
    PayoutPaystubsResponse,
    PaystubRead,
)

router = APIRouter(prefix="/api/payout", tags=["payout"])


def get_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if isinstance(settings, Settings):
        return settings
    return Settings()


def _get_nodeapi_service(request: Request) -> NodeApiService | None:
    # Historically the app stored the service as `nodeapi_service` (no
    # underscore). Accept either form for robustness.
    svc = getattr(request.app.state, "nodeapi_service", None)
    if svc is None:
        svc = getattr(request.app.state, "node_api_service", None)
    if isinstance(svc, NodeApiService):
        return svc
    return None

@router.post("/current", response_model=PayoutCurrentResponse)
async def current_payouts(req: PayoutCurrentRequest, request: Request) -> PayoutCurrentResponse:
    """Return current payout data for the requested nodes.

    The request is a JSON object with optional `nodes` list; empty means all.
    """
    svc = _get_nodeapi_service(request)
    if svc is None:
        return PayoutCurrentResponse()

    # Use the service accessor to get a snapshot of NodeData copies
    node_data = await svc.get_node_data(req.nodes or None)

    out: dict[str, PayoutNode] = {}
    for name, data in node_data.items():
        out[name] = PayoutNode(
            joined_at=data.joined_at,
            last_estimated_payout_at=data.last_estimated_payout_at,
            estimated_payout=data.estimated_payout,
            held_back_payout=data.held_back_payout,
            total_held_payout=data.total_held_amount,
            download_payout=data.download_payout,
            repair_payout=data.repair_payout,
            disk_payout=data.disk_payout,
        )

    return PayoutCurrentResponse(nodes=out)

# Endpoint removed by request — helpers and router left in place for future use.


@router.post("/paystubs", response_model=PayoutPaystubsResponse)
async def paystub_history(req: PayoutPaystubsRequest) -> PayoutPaystubsResponse:
    stmt = select(Paystub)
    if req.nodes:
        stmt = stmt.where(Paystub.source.in_(req.nodes))
    stmt = stmt.order_by(Paystub.period, Paystub.source, Paystub.satellite_id, Paystub.created)

    periods: dict[str, list[PaystubRead]] = {}

    async with database.SessionFactory() as session:
        result = await session.execute(stmt)
        records = result.scalars().all()

    for record in records:
        bucket = periods.setdefault(record.period, [])
        bucket.append(PaystubRead.model_validate(record))

    return PayoutPaystubsResponse(periods=periods)
