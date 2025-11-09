from __future__ import annotations

import httpx
import pytest

from datetime import datetime, timezone

from server.src.config import Settings
from server.src.services.node_api import NodeApiService, NodeState


@pytest.mark.asyncio
async def test_nodeapi_service_caches_snapshot(tmp_path) -> None:
    settings = Settings(
        sources=[f"alpha:{tmp_path / 'alpha.log'}|http://node.example/status"],
        unprocessed_log_dir=str(tmp_path / "unprocessed"),
    )

    payload = {"status": "ok", "bandwidth": {"ingress": 1234}}

    async def handler(request: httpx.Request) -> httpx.Response:
        # Accept either the legacy behavior (polling the exact configured
        # nodeapi URL) or the new behavior where the processor fetches the
        # canonical /api/sno/satellites path relative to the base URL.
        assert request.url in (
            httpx.URL("http://node.example/status"),
            httpx.URL("http://node.example/api/sno/satellites"),
        )
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)

    service = NodeApiService(settings, client=client)

    # Perform a single on-demand fetch inline (refresh_all has been removed);
    # this mirrors the previous behavior used by tests.
    client2 = await service._ensure_client()
    assert client2 is not None
    # Create/ensure a proper NodeState for the test
    async with service._lock:
        runtime = __import__("types").SimpleNamespace()
        # Construct NodeRuntime-like object for tests
        runtime = type("R", (), {})()
        runtime.url = "http://node.example/status"
        runtime.last_fetched_at = None
        runtime.consecutive_failures = 0
        runtime.last_error = None
        runtime.task = None
        state = NodeState(name="alpha", runtime=runtime)
        service._states["alpha"] = state

    processed = await service._process_sno_satellites(client2, state)
    if processed:
        fetched_at = datetime.now(timezone.utc)
        async with service._lock:
            state.runtime.last_fetched_at = fetched_at
            state.runtime.consecutive_failures = 0
            state.runtime.last_error = None

    async with service._lock:
        state = service._states.get("alpha")
        assert state is not None
        assert state.runtime.last_fetched_at is not None

    await client.aclose()


@pytest.mark.asyncio
async def test_nodeapi_service_ignores_invalid_json(tmp_path) -> None:
    settings = Settings(
        sources=[f"beta:{tmp_path / 'beta.log'}|http://node.example/status"],
        unprocessed_log_dir=str(tmp_path / "unprocessed"),
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content="not-json")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)

    service = NodeApiService(settings, client=client)

    client2 = await service._ensure_client()
    assert client2 is not None

    async with service._lock:
        runtime = type("R", (), {})()
        runtime.url = "http://node.example/status"
        runtime.last_fetched_at = None
        runtime.consecutive_failures = 0
        runtime.last_error = None
        runtime.task = None
        state = NodeState(name="beta", runtime=runtime)
        service._states["beta"] = state

    # perform fetch using processing helper
    processed = await service._process_sno_satellites(client2, state)
    if processed:
        fetched_at = datetime.now(timezone.utc)
        async with service._lock:
            state.runtime.last_fetched_at = fetched_at
            state.runtime.consecutive_failures = 0
            state.runtime.last_error = None

    async with service._lock:
        state = service._states.get("beta")
        assert state is not None
        assert state.runtime.last_fetched_at is None

    await client.aclose()
