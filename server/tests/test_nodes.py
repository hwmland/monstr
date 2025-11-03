from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from server.src.config import Settings
from server.src.core.app import create_app


@pytest.mark.asyncio
async def test_list_nodes_returns_configured_sources(tmp_path) -> None:
    test_settings = Settings(sources=[])
    app = create_app(test_settings)
    app.state.settings = test_settings
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        app.state.settings.sources = [
            f"alpha:{tmp_path / 'alpha.log'}",
            f"beta:{tmp_path / 'beta.log'}",
        ]

        response = await client.get("/api/nodes")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert payload[0]["name"] == "alpha"
    assert payload[1]["name"] == "beta"
