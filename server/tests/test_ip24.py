from __future__ import annotations

import httpx
import pytest

from server.src.config import IP24Definition, Settings
from server.src.services.ip24 import IP24Service


def test_ip24_comma_separated():
    s = Settings(ip24="1.2.3.4:2,Home|host.example.com:4")
    assert isinstance(s.ip24, list)
    assert s.ip24 == ["1.2.3.4:2", "Home|host.example.com:4"]


def test_parsed_ip24_without_alias_uses_ip_as_alias():
    s = Settings(ip24=["1.2.3.4:2"])
    entries = s.parsed_ip24
    assert entries == [
        IP24Definition(alias="1.2.3.4", ip="1.2.3.4", expected_instances=2),
    ]


def test_parsed_ip24_with_alias():
    s = Settings(ip24=["Home|host.example.com:4"])
    entries = s.parsed_ip24
    assert entries == [
        IP24Definition(alias="Home", ip="host.example.com", expected_instances=4),
    ]


def test_parsed_ip24_rejects_empty_alias():
    s = Settings(ip24=["|host.example.com:4"])
    with pytest.raises(ValueError, match="alias cannot be empty"):
        s.parsed_ip24


@pytest.mark.asyncio
async def test_ip24_service_status_uses_alias_keys():
    settings = Settings(ip24=["Home|host.example.com:4", "1.2.3.4:2"])
    service = IP24Service(settings, client=httpx.AsyncClient())

    async def fake_run() -> None:
        await service._stop_event.wait()

    service._run = fake_run  # type: ignore[method-assign]

    await service.start()
    try:
        status = await service.get_status()
    finally:
        await service.stop()

    assert set(status) == {"Home", "1.2.3.4"}
    assert "host.example.com" not in status
    assert status["Home"] == {
        "valid": False,
        "expectedInstances": 4,
        "instances": None,
    }