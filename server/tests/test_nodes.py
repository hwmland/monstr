from __future__ import annotations

import pytest
from datetime import datetime, timezone

from httpx import ASGITransport, AsyncClient

from server.src.config import Settings
from server.src.core.app import create_app
from server.src.services.node_api import NodeApiService, NodeData


class DummyNodeApiService(NodeApiService):
    def __init__(self, mapping: dict[str, NodeData]) -> None:
        self._mapping = mapping

    async def get_node_data(self, names=None):
        if not names:
            return dict(self._mapping)
        return {name: self._mapping[name] for name in names if name in self._mapping}


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
    assert payload[0]["vetting"] is None
    assert payload[1]["vetting"] is None


@pytest.mark.asyncio
async def test_list_nodes_includes_vetting_when_service_available(tmp_path) -> None:
    test_settings = Settings(sources=[])
    app = create_app(test_settings)
    app.state.settings = test_settings
    transport = ASGITransport(app=app)

    vetted_ts = datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    app.state.nodeapi_service = DummyNodeApiService(
        {
            "alpha": NodeData(vetting_date={"satA": vetted_ts, "satB": None}),
            "beta": NodeData(),
        }
    )

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        app.state.settings.sources = [
            f"alpha:{tmp_path / 'alpha.log'}",
            f"beta:{tmp_path / 'beta.log'}",
        ]

        response = await client.get("/api/nodes")

    assert response.status_code == 200
    payload = response.json()
    payload_by_name = {item["name"]: item for item in payload}
    expected_iso = vetted_ts.isoformat().replace("+00:00", "Z")
    assert payload_by_name["alpha"]["vetting"] == {
        "satA": expected_iso,
        "satB": None,
    }
    assert payload_by_name["beta"]["vetting"] is None
