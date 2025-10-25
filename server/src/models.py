from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Column, DateTime, Float
from sqlmodel import Field, SQLModel


class LogEntry(SQLModel, table=True):
    """Persisted representation of a parsed log line."""

    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(index=True, description="Configured node name for the log source")
    timestamp: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
        description="Timestamp from the original log entry",
    )
    level: str = Field(index=True, description="Log severity level")
    area: str = Field(index=True, description="Subsystem emitting the log entry")
    action: str = Field(index=True, description="Event descriptor within the subsystem")
    details: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
        description="Structured metadata extracted from the log payload",
    )


class Transfer(SQLModel, table=True):
    """Normalized representation of piecestore transfers."""

    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(index=True, description="Configured node name for the log source")
    timestamp: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
        description="Timestamp from the original log entry",
    )
    action: str = Field(description="Transfer action code (DL or UL)")
    is_success: bool = Field(description="True when transfer completed successfully")
    piece_id: str = Field(description="Piece identifier")
    satellite_id: str = Field(description="Satellite identifier")
    is_repair: bool = Field(description="True when the transfer is a repair operation")
    size: int = Field(description="Transfer size in bytes")
    offset: Optional[int] = Field(default=None, description="Transfer offset")
    remote_address: Optional[str] = Field(default=None, description="Remote address for the transfer")


class Reputation(SQLModel, table=True):
    """Latest reputation metrics per source and satellite pair."""

    source: str = Field(primary_key=True, description="Configured node name for the log source")
    satellite_id: str = Field(primary_key=True, description="Satellite identifier")
    timestamp: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
        description="Timestamp associated with the reputation metrics",
    )
    audits_total: int = Field(description="Total number of audits recorded")
    audits_success: int = Field(description="Number of successful audits")
    score_audit: float = Field(
        sa_column=Column(Float, nullable=False), description="Audit score reported by Storj"
    )
    score_online: float = Field(
        sa_column=Column(Float, nullable=False), description="Online score reported by Storj"
    )
    score_suspension: float = Field(
        sa_column=Column(Float, nullable=False), description="Suspension score reported by Storj"
    )
