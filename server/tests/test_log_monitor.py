from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from server.src.config import Settings
from server.src.services.log_monitor import LogMonitorService


@pytest.mark.asyncio
async def test_collector_info_entries_are_persisted(tmp_path) -> None:
    settings = Settings(sources=[], unprocessed_log_dir=str(tmp_path))
    service = LogMonitorService(settings)

    raw_line = (
        "2025-10-25T12:00:00Z\tINFO\tcollector\tstatus\t{\"duration\": \"5s\"}\n"
    )

    entries, transfers, reputations, is_unprocessed = await service._process_line(
        "node-a", raw_line
    )

    assert is_unprocessed is False
    assert entries is not None
    assert len(entries) == 1
    assert entries[0].area == "collector"
    assert entries[0].details == {"duration": "5s"}
    assert transfers == []
    assert reputations == []


@pytest.mark.asyncio
async def test_reputation_service_emits_reputation_payload(tmp_path) -> None:
    settings = Settings(sources=[], unprocessed_log_dir=str(tmp_path))
    service = LogMonitorService(settings)

    details = json.dumps(
        {
            "Satellite ID": "12T",
            "Total Audits": "100",
            "Successful Audits": 98,
            "Audit Score": "0.98",
            "Online Score": "0.97",
            "Suspension Score": "1.0",
        }
    )
    raw_line = f"2025-10-25T12:00:00Z\tINFO\treputation:service\tupdate\t{details}\n"

    entries, transfers, reputations, is_unprocessed = await service._process_line(
        "node-1", raw_line
    )

    assert is_unprocessed is False
    assert entries is not None and len(entries) == 1
    assert transfers == []
    assert len(reputations) == 1

    reputation = reputations[0]
    assert reputation.source == "node-1"
    assert reputation.satellite_id == "12T"
    assert reputation.audits_total == 100
    assert reputation.audits_success == 98
    assert reputation.score_audit == pytest.approx(0.98)
    assert reputation.score_online == pytest.approx(0.97)
    assert reputation.score_suspension == pytest.approx(1.0)
    assert reputation.timestamp == datetime(2025, 10, 25, 12, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_reputation_service_missing_fields_skips_reputation(tmp_path) -> None:
    settings = Settings(sources=[], unprocessed_log_dir=str(tmp_path))
    service = LogMonitorService(settings)

    details = json.dumps(
        {
            "Satellite ID": "34F",
            "Total Audits": "10",
            "Audit Score": "0.91",
        }
    )
    raw_line = f"2025-10-25T12:00:00Z\tINFO\treputation:service\tupdate\t{details}\n"

    entries, transfers, reputations, is_unprocessed = await service._process_line(
        "node-2", raw_line
    )

    assert is_unprocessed is True
    assert entries == []
    assert transfers == []
    assert reputations == []


@pytest.mark.asyncio
async def test_unprocessed_records_written_per_node(tmp_path) -> None:
    settings = Settings(sources=[], unprocessed_log_dir=str(tmp_path))
    service = LogMonitorService(settings)

    await service._record_unprocessed("alpha", "first line")
    await service._record_unprocessed("beta node", "second line\n")

    node_alpha_path = tmp_path / "unprocessed-alpha.log"
    node_beta_path = tmp_path / "unprocessed-beta_node.log"

    assert node_alpha_path.exists()
    assert node_beta_path.exists()
    assert node_alpha_path.read_text(encoding="utf-8") == "first line\n"
    assert node_beta_path.read_text(encoding="utf-8") == "second line\n"
