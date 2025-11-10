from __future__ import annotations

from typing import Sequence

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_session
from ...repositories.held_amounts import HeldAmountRepository
from ...schemas import HeldAmountFilters, HeldAmountRead


router = APIRouter(prefix="/api/held-amounts", tags=["held-amounts"])


@router.get("/", response_model=list[HeldAmountRead], tags=["raw"])
async def list_held_amounts(
    filters: HeldAmountFilters = Depends(),
    session: AsyncSession = Depends(get_session),
) -> Sequence[HeldAmountRead]:
    """Return held amount records filtered by the requested criteria."""
    repository = HeldAmountRepository(session)
    records = await repository.list(filters)
    return [HeldAmountRead.model_validate(record) for record in records]
