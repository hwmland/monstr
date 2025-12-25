from __future__ import annotations

from typing import Optional

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...repositories.access_logs import AccessLogRepository


def extract_client_meta(request: Request) -> tuple[str, int, Optional[str], Optional[str], Optional[str]]:
    client = request.client
    host = "unknown"
    port_value = None

    if client is not None:
        if isinstance(client, (list, tuple)) and client:
            host = str(client[0] or "unknown")
            if len(client) > 1:
                port_value = client[1]
        else:
            host = getattr(client, "host", None) or "unknown"
            port_value = getattr(client, "port", None)

    try:
        port = int(port_value) if port_value is not None else 0
    except (TypeError, ValueError):
        port = 0

    forwarded_for = request.headers.get("x-forwarded-for")
    real_ip = request.headers.get("x-real-ip")
    user_agent = request.headers.get("user-agent")
    return host, port, forwarded_for, real_ip, user_agent


async def persist_access_log(
    session: AsyncSession,
    *,
    host: str,
    port: int,
    forwarded_for: Optional[str],
    real_ip: Optional[str],
    user_agent: Optional[str],
) -> None:
    repo = AccessLogRepository(session)
    await repo.record(
        host=host,
        port=port,
        forwarded_for=forwarded_for,
        real_ip=real_ip,
        user_agent=user_agent,
    )
