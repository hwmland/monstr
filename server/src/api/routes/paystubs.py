from __future__ import annotations

from typing import Sequence

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_session
from ...repositories.paystubs import PaystubRepository
from ...schemas import PaystubFilters, PaystubRead


router = APIRouter(prefix="/api/paystubs", tags=["paystubs"])


@router.get("/", response_model=list[PaystubRead], tags=["raw"])
async def list_paystubs(
    filters: PaystubFilters = Depends(),
    session: AsyncSession = Depends(get_session),
) -> Sequence[PaystubRead]:
    """Return paystub records filtered by the requested criteria."""
    repository = PaystubRepository(session)
    records = await repository.list(filters)
    return [PaystubRead.model_validate(record) for record in records]
