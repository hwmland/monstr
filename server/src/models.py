from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class LogEntry(SQLModel, table=True):
    """Persisted representation of a parsed log line."""

    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(index=True, description="Absolute path to the originating log file")
    content: str = Field(description="Raw line content captured from the log")
    ingested_at: datetime = Field(
        default_factory=datetime.utcnow,
        index=True,
        description="Timestamp when the line was persisted",
    )
    processed: bool = Field(
        default=False,
        description="Marks whether downstream enrichment has already been performed.",
    )
