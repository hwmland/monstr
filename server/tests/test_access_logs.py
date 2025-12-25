from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from server.src.config import Settings
from server.src.core.app import create_app
from server.src.database import init_database


@pytest.mark.asyncio
async def test_access_logs_endpoint_returns_entries(tmp_path) -> None:
    settings = Settings(sources=[])
    await init_database(settings)
    app = create_app(settings)
    app.state.settings = settings
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        app.state.settings.sources = [f"alpha:{tmp_path / 'alpha.log'}"]
        response = await client.get("/api/nodes")
        assert response.status_code == 200

        access_response = await client.get("/api/access-logs")
        assert access_response.status_code == 200
        entries = access_response.json()
        assert entries, "Expected at least one access log entry"
        first = entries[0]
        assert "host" in first
        assert "port" in first
        assert first["port"] >= 0


@pytest.mark.asyncio
async def test_access_logs_endpoint_respects_limit(tmp_path) -> None:
    settings = Settings(sources=[])
    await init_database(settings)
    app = create_app(settings)
    app.state.settings = settings
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        app.state.settings.sources = [f"beta:{tmp_path / 'beta.log'}"]
        for _ in range(3):
            await client.get("/api/nodes")

        limited = await client.get("/api/access-logs", params={"limit": 2})
        assert limited.status_code == 200
        entries = limited.json()
        assert len(entries) == 2
