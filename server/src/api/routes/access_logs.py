from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_session
from ...repositories.access_logs import AccessLogRepository
from ...schemas import AccessLogRead

router = APIRouter(prefix="/api/access-logs", tags=["access-logs"])


@router.get("", response_model=list[AccessLogRead], tags=["raw"])
async def list_access_logs(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of access log rows to return"),
    session: AsyncSession = Depends(get_session),
) -> list[AccessLogRead]:
    repo = AccessLogRepository(session)
    records = await repo.list_recent(limit)
    return list(records)
