from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AccessLog


class AccessLogRepository:
    """Persist and query API access log records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        host: str,
        port: Optional[int],
        forwarded_for: Optional[str],
        real_ip: Optional[str],
        user_agent: Optional[str],
    ) -> AccessLog:
        entry = AccessLog(
            host=(host or "unknown")[:64],
            port=int(port or 0),
            fwd_for=forwarded_for[:64] if forwarded_for else None,
            real_ip=real_ip[:64] if real_ip else None,
            user_agent=user_agent[:1024] if user_agent else None,
        )
        self._session.add(entry)
        await self._session.flush()
        await self._session.commit()
        return entry

    async def list_recent(self, limit: int = 100) -> Sequence[AccessLog]:
        stmt = (
            select(AccessLog)
            .order_by(AccessLog.timestamp.desc(), AccessLog.id.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return tuple(result.scalars())
