from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..config import Settings


def getVirtualNow(settings: Settings) -> datetime:
    """Return the logical 'now' value adjusted by configured day offsets."""
    return datetime.now(timezone.utc) - timedelta(days=getattr(settings, "days_offset", 0))
