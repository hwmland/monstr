from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from server.src.config import Settings
from server.src.core.app import create_app
from server.src.database import SessionFactory, init_database
from server.src.models import Reputation
from server.src.repositories.reputations import ReputationRepository
from server.src.schemas import ReputationCreate


@pytest.mark.asyncio
async def test_list_reputations_empty() -> None:
    app = create_app(Settings(log_sources=[]))
    await init_database()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        async with SessionFactory() as session:
            await session.execute(delete(Reputation))
            await session.commit()

        response = await client.get("/api/reputations")

        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.asyncio
async def test_list_reputations_filters() -> None:
    app = create_app(Settings(log_sources=[]))
    payload = ReputationCreate(
        source="node-a",
        satellite_id="sat-1",
        timestamp=datetime.now(timezone.utc),
        audits_total=200,
        audits_success=199,
        score_audit=0.995,
        score_online=0.99,
        score_suspension=1.0,
    )

    await init_database()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        async with SessionFactory() as session:
            await session.execute(delete(Reputation))
            await session.commit()

            repository = ReputationRepository(session)
            await repository.upsert_many([payload])

        response = await client.get(
            "/api/reputations",
            params={"source": "node-a", "satellite_id": "sat-1"},
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    record = body[0]
    assert record["source"] == payload.source
    assert record["satellite_id"] == payload.satellite_id
    assert record["audits_total"] == payload.audits_total
    assert record["audits_success"] == payload.audits_success
    assert record["score_audit"] == pytest.approx(payload.score_audit)
    assert record["score_online"] == pytest.approx(payload.score_online)
    assert record["score_suspension"] == pytest.approx(payload.score_suspension)
