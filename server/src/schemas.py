from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LogEntryCreate(BaseModel):
    source: str = Field(..., description="Absolute path to the log file")
    content: str = Field(..., description="Raw log line content")


class LogEntryRead(BaseModel):
    id: int
    source: str
    content: str
    ingested_at: datetime
    processed: bool

    class Config:
        from_attributes = True


class LogEntryFilters(BaseModel):
    source: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=1000)
