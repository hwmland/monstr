import pytest

from server.src.api.routes import dash as dash_module
from server.src.config import Settings


mock_response = {
    "storageDaily": None,
    "bandwidthDaily": None,
    "storageSummary": 0.0,
    "averageUsageBytes": 0.0,
    "bandwidthSummary": 0.0,
    "egressSummary": 0.0,
    "ingressSummary": 0.0,
    "earliestJoinedAt": "2020-01-01T00:00:00Z",
    "audits": None,
}


@pytest.mark.asyncio
async def test_dash_node_satellites_normalize(monkeypatch):
    async def fake_fetch_json(url):
        return mock_response.copy()

    monkeypatch.setattr(dash_module, "_fetch_json", fake_fetch_json)

    settings = Settings(sources=["node5:storj5.internal:9005|http://example:14005"])

    response = await dash_module.dash_node_satellites(node_name="node5", settings=settings)

    assert response["storageDaily"] == []
    assert response["bandwidthDaily"] == []
    assert response["audits"] == []
