from __future__ import annotations

from typing import Sequence

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_session
from ...repositories.reputations import ReputationRepository
from ...schemas import ReputationFilters, ReputationRead

router = APIRouter(prefix="/api/reputations", tags=["reputations"])


@router.get("", response_model=list[ReputationRead])
async def list_reputations(
    filters: ReputationFilters = Depends(),
    session: AsyncSession = Depends(get_session),
) -> Sequence[ReputationRead]:
    """Return reputation records filtered by the requested criteria."""
    repository = ReputationRepository(session)
    records = await repository.list(filters)
    return [ReputationRead.model_validate(record) for record in records]
