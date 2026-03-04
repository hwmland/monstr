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


@pytest.mark.asyncio
async def test_reputation_service_snake_case_format(tmp_path) -> None:
    """Test that new snake_case format logs are parsed correctly."""
    settings = Settings(sources=[], unprocessed_log_dir=str(tmp_path))
    service = LogMonitorService(settings)

    details = json.dumps(
        {
            "satellite_id": "12T",
            "total_audits": "100",
            "successful_audits": 98,
            "audit_score": "0.98",
            "online_score": "0.97",
            "suspension_score": "1.0",
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
async def test_reputation_service_snake_case_missing_fields(tmp_path) -> None:
    """Test that incomplete snake_case format logs are properly skipped."""
    settings = Settings(sources=[], unprocessed_log_dir=str(tmp_path))
    service = LogMonitorService(settings)

    details = json.dumps(
        {
            "satellite_id": "34F",
            "total_audits": "10",
            "audit_score": "0.91",
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
async def test_piecestore_transfer_old_format(tmp_path) -> None:
    """Test that old Title Case format transfer logs are parsed correctly."""
    settings = Settings(sources=[], unprocessed_log_dir=str(tmp_path))
    service = LogMonitorService(settings)

    details = json.dumps(
        {
            "Piece ID": "U3SLQ3CUOFHTVT5DKPGVS23RCURKBQPGRBAE2XPFX5FNBQ2QUN3Q",
            "Satellite ID": "12EayRS2V1kEsWESU9QMRseFhdxYxKicsiFmxrsLZHeLUtdps3S",
            "Action": "GET",
            "Size": 256,
            "Offset": 0,
            "Remote Address": "156.146.43.227:59558",
        }
    )
    raw_line = f"2026-03-04T20:00:17Z\tINFO\tpiecestore\tdownloaded\t{details}\n"

    entries, transfers, reputations, is_unprocessed = await service._process_line(
        "Node1", raw_line
    )

    assert is_unprocessed is False
    assert entries == []
    assert len(transfers) == 1
    assert reputations == []

    transfer = transfers[0]
    assert transfer.source == "Node1"
    assert transfer.piece_id == "U3SLQ3CUOFHTVT5DKPGVS23RCURKBQPGRBAE2XPFX5FNBQ2QUN3Q"
    assert transfer.satellite_id == "12EayRS2V1kEsWESU9QMRseFhdxYxKicsiFmxrsLZHeLUtdps3S"
    assert transfer.action == "DL"
    assert transfer.is_success is True
    assert transfer.size == 256
    assert transfer.offset == 0
    assert transfer.remote_address == "156.146.43.227:59558"
    assert transfer.is_repair is False
    assert transfer.timestamp == datetime(2026, 3, 4, 20, 0, 17, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_piecestore_transfer_new_format(tmp_path) -> None:
    """Test that new snake_case format transfer logs are parsed correctly."""
    settings = Settings(sources=[], unprocessed_log_dir=str(tmp_path))
    service = LogMonitorService(settings)

    details = json.dumps(
        {
            "piece_id": "G5BOWBSY3DWQZFTK3OGOS5E6MXQ4WNH2AWETL5SYYBTJIH4CG4SA",
            "satellite_id": "12EayRS2V1kEsWESU9QMRseFhdxYxKicsiFmxrsLZHeLUtdps3S",
            "action": "GET",
            "size": 2048,
            "offset": 0,
            "remote_address": "79.127.205.226:41276",
        }
    )
    raw_line = f"2026-03-04T19:58:19Z\tINFO\tpiecestore\tdownloaded\t{details}\n"

    entries, transfers, reputations, is_unprocessed = await service._process_line(
        "Node2", raw_line
    )

    assert is_unprocessed is False
    assert entries == []
    assert len(transfers) == 1
    assert reputations == []

    transfer = transfers[0]
    assert transfer.source == "Node2"
    assert transfer.piece_id == "G5BOWBSY3DWQZFTK3OGOS5E6MXQ4WNH2AWETL5SYYBTJIH4CG4SA"
    assert transfer.satellite_id == "12EayRS2V1kEsWESU9QMRseFhdxYxKicsiFmxrsLZHeLUtdps3S"
    assert transfer.action == "DL"
    assert transfer.is_success is True
    assert transfer.size == 2048
    assert transfer.offset == 0
    assert transfer.remote_address == "79.127.205.226:41276"
    assert transfer.is_repair is False
    assert transfer.timestamp == datetime(2026, 3, 4, 19, 58, 19, tzinfo=timezone.utc)


def test_normalize_details_passthrough() -> None:
    """Test that old Title Case format is passed through unchanged."""
    settings = Settings(sources=[], unprocessed_log_dir="")
    service = LogMonitorService(settings)

    old_format = {
        "Piece ID": "ABC123",
        "Satellite ID": "SAT456",
        "Size": 1024,
        "Other Field": "value",
    }

    normalized = service._normalize_details(old_format)

    # Should be unchanged (same object if no snake_case keys present)
    assert normalized == old_format


def test_normalize_details_remaps_snake_case() -> None:
    """Test that snake_case keys are remapped to Title Case."""
    settings = Settings(sources=[], unprocessed_log_dir="")
    service = LogMonitorService(settings)

    new_format = {
        "piece_id": "XYZ789",
        "satellite_id": "SAT999",
        "size": 512,
        "action": "GET",
        "unknown_field": "preserved",
    }

    normalized = service._normalize_details(new_format)

    assert normalized == {
        "Piece ID": "XYZ789",
        "Satellite ID": "SAT999",
        "Size": 512,
        "Action": "GET",
        "unknown_field": "preserved",
    }
