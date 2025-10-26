from __future__ import annotations

from typing import Sequence

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_session
from ...repositories.transfers import TransferRepository
from ...schemas import TransferFilters, TransferRead

router = APIRouter(prefix="/api/transfers", tags=["transfers"])


@router.get("", response_model=list[TransferRead], tags=["raw"])
async def list_transfers(
    filters: TransferFilters = Depends(),
    session: AsyncSession = Depends(get_session),
) -> Sequence[TransferRead]:
    """Return transfer records filtered by the requested criteria."""
    repository = TransferRepository(session)
    records = await repository.list(filters)
    return [TransferRead.model_validate(record) for record in records]
