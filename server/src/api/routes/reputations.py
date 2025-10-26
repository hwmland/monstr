from __future__ import annotations

from typing import Sequence

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_session
from ...repositories.reputations import ReputationRepository
from ...schemas import (
    NodeReputationRead,
    ReputationFilters,
    ReputationPanelRequest,
    ReputationRead,
    SatelliteReputationRead,
)

router = APIRouter(prefix="/api/reputations", tags=["reputations"])


@router.get("", response_model=list[ReputationRead], tags=["raw"])
async def list_reputations(
    filters: ReputationFilters = Depends(),
    session: AsyncSession = Depends(get_session),
) -> Sequence[ReputationRead]:
    """Return reputation records filtered by the requested criteria."""
    repository = ReputationRepository(session)
    records = await repository.list(filters)
    return [ReputationRead.model_validate(record) for record in records]


@router.post("/panel", response_model=list[NodeReputationRead])
async def list_reputations_panel(
    payload: ReputationPanelRequest,
    session: AsyncSession = Depends(get_session),
) -> list[NodeReputationRead]:
    """Return reputations grouped per node for the requested set of sources."""
    repository = ReputationRepository(session)

    requested_nodes = sorted({node for node in payload.nodes if node})
    fetch_all = not requested_nodes

    if fetch_all:
        records = await repository.list_all()
    else:
        records = await repository.list_for_sources(requested_nodes)

    if fetch_all:
        nodes_for_response = sorted({record.source for record in records})
    else:
        nodes_for_response = requested_nodes

    if not nodes_for_response:
        return []

    grouped: dict[str, list[SatelliteReputationRead]] = {node: [] for node in nodes_for_response}
    for record in records:
        grouped.setdefault(record.source, []).append(
            SatelliteReputationRead(
                satellite_id=record.satellite_id,
                timestamp=record.timestamp,
                audits_total=record.audits_total,
                audits_success=record.audits_success,
                score_audit=record.score_audit,
                score_online=record.score_online,
                score_suspension=record.score_suspension,
            )
        )

    return [NodeReputationRead(node=node, satellites=grouped.get(node, [])) for node in nodes_for_response]
