from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from server.src.core.app import create_app
from server.src.config import Settings


@pytest.mark.asyncio
async def test_healthcheck() -> None:
    app = create_app(Settings(sources=[]))

    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
