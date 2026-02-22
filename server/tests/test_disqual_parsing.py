from __future__ import annotations

import pytest

from server.src.config import DisqualDefinition, Settings


# ---------------------------------------------------------------------------
# Coercion tests (raw string → list)
# ---------------------------------------------------------------------------

def test_disqual_comma_separated():
    s = Settings(disqual="Node1::2025-06,Node2:sat123:2025-10")
    assert isinstance(s.disqual, list)
    assert s.disqual == ["Node1::2025-06", "Node2:sat123:2025-10"]


def test_disqual_newline_separated():
    s = Settings(disqual="Node1::2025-06\nNode2:sat123:2025-10")
    assert s.disqual == ["Node1::2025-06", "Node2:sat123:2025-10"]


def test_disqual_list_input():
    s = Settings(disqual=["Node1::2025-06", "Node2:sat123:2025-10"])
    assert s.disqual == ["Node1::2025-06", "Node2:sat123:2025-10"]


def test_disqual_json_array_string():
    json_array = '["Node1::2025-06", "Node2:sat123:2025-10"]'
    s = Settings(disqual=json_array)
    assert s.disqual == ["Node1::2025-06", "Node2:sat123:2025-10"]


def test_disqual_empty_string():
    s = Settings(disqual="")
    assert s.disqual == []


def test_disqual_none():
    s = Settings(disqual=None)
    assert s.disqual == []


def test_disqual_default_empty():
    s = Settings()
    assert s.disqual == []


# ---------------------------------------------------------------------------
# Parsing tests (list → DisqualDefinition objects)
# ---------------------------------------------------------------------------

def test_parsed_disqual_all_satellites():
    s = Settings(disqual=["Node1::2025-06"])
    dqs = s.parsed_disqual
    assert len(dqs) == 1
    assert dqs[0] == DisqualDefinition(source="Node1", satellite_id="", period="2025-06")


def test_parsed_disqual_specific_satellite():
    s = Settings(disqual=["Node1:1wFTAgs9DP5RSnCqKV1eLf6N9wtk4EAtmN5DpSxcs8EjT69tGE:2025-10"])
    dqs = s.parsed_disqual
    assert len(dqs) == 1
    assert dqs[0].source == "Node1"
    assert dqs[0].satellite_id == "1wFTAgs9DP5RSnCqKV1eLf6N9wtk4EAtmN5DpSxcs8EjT69tGE"
    assert dqs[0].period == "2025-10"


def test_parsed_disqual_multiple():
    s = Settings(disqual=["Node1::2025-06", "Node2:sat456:2025-12"])
    dqs = s.parsed_disqual
    assert len(dqs) == 2
    assert dqs[0] == DisqualDefinition(source="Node1", satellite_id="", period="2025-06")
    assert dqs[1] == DisqualDefinition(source="Node2", satellite_id="sat456", period="2025-12")


def test_parsed_disqual_invalid_period():
    s = Settings(disqual=["Node1::2025"])
    with pytest.raises(ValueError, match="expected yyyy-mm"):
        s.parsed_disqual


def test_parsed_disqual_missing_source():
    s = Settings(disqual=["::2025-06"])
    with pytest.raises(ValueError, match="missing a source name"):
        s.parsed_disqual


def test_parsed_disqual_too_few_segments():
    s = Settings(disqual=["Node1:2025-06"])
    with pytest.raises(ValueError, match="expected SOURCE:SATELLITE_ID:PERIOD"):
        s.parsed_disqual


def test_parsed_disqual_satellite_with_colons():
    """Satellite IDs may contain colons; only the first and last segments
    are treated as source and period respectively."""
    s = Settings(disqual=["Node1:a:b:c:2025-03"])
    dqs = s.parsed_disqual
    assert len(dqs) == 1
    assert dqs[0].source == "Node1"
    assert dqs[0].satellite_id == "a:b:c"
    assert dqs[0].period == "2025-03"
