from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Column, DateTime, Float, String
from sqlmodel import Field, SQLModel


class LogEntry(SQLModel, table=True):
    """Persisted representation of a parsed log line."""

    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(
        sa_column=Column(
            String(32),
            index=True,
            nullable=False,
        ),
        description="Configured node name for the log source",
    )
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
    source: str = Field(
        sa_column=Column(
            String(32),
            index=True,
            nullable=False,
        ),
        description="Configured node name for the log source",
    )
    timestamp: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
        description="Timestamp from the original log entry",
    )
    action: str = Field(description="Transfer action code (DL or UL)")
    is_success: bool = Field(description="True when transfer completed successfully")
    piece_id: str = Field(description="Piece identifier")
    satellite_id: str = Field(
        sa_column=Column(String(64), nullable=False),
        description="Satellite identifier",
    )
    is_repair: bool = Field(description="True when the transfer is a repair operation")
    size: int = Field(description="Transfer size in bytes")
    offset: Optional[int] = Field(default=None, description="Transfer offset")
    remote_address: Optional[str] = Field(default=None, description="Remote address for the transfer")


class Reputation(SQLModel, table=True):
    """Latest reputation metrics per source and satellite pair."""

    source: str = Field(
        sa_column=Column(
            String(32),
            primary_key=True,
            nullable=False,
        ),
        description="Configured node name for the log source",
    )
    satellite_id: str = Field(
        sa_column=Column(String(64), primary_key=True, nullable=False),
        description="Satellite identifier",
    )
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


class TransportGrouped(SQLModel, table=True):
    """Aggregated transfer metrics grouped by interval, satellite, and size class."""

    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(
        sa_column=Column(String(32), index=True, nullable=False),
        description="Configured node name for the log source",
    )
    satellite_id: str = Field(
        sa_column=Column(String(64), nullable=False),
        description="Satellite identifier",
    )
    interval_start: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
        description="Inclusive interval start",
    )
    interval_end: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="Exclusive interval end",
    )
    size_class: str = Field(
        sa_column=Column(String(8), nullable=False),
        description="Payload size class (e.g. 1K, 4K, 256K)",
    )
    size_dl_succ_nor: int = Field(default=0, description="Bytes for successful normal downloads")
    size_ul_succ_nor: int = Field(default=0, description="Bytes for successful normal uploads")
    size_dl_fail_nor: int = Field(default=0, description="Bytes for failed normal downloads")
    size_ul_fail_nor: int = Field(default=0, description="Bytes for failed normal uploads")
    size_dl_succ_rep: int = Field(default=0, description="Bytes for successful repair downloads")
    size_ul_succ_rep: int = Field(default=0, description="Bytes for successful repair uploads")
    size_dl_fail_rep: int = Field(default=0, description="Bytes for failed repair downloads")
    size_ul_fail_rep: int = Field(default=0, description="Bytes for failed repair uploads")
    count_dl_succ_nor: int = Field(default=0, description="Successful normal download count")
    count_ul_succ_nor: int = Field(default=0, description="Successful normal upload count")
    count_dl_fail_nor: int = Field(default=0, description="Failed normal download count")
    count_ul_fail_nor: int = Field(default=0, description="Failed normal upload count")
    count_dl_succ_rep: int = Field(default=0, description="Successful repair download count")
    count_ul_succ_rep: int = Field(default=0, description="Successful repair upload count")
    count_dl_fail_rep: int = Field(default=0, description="Failed repair download count")
    count_ul_fail_rep: int = Field(default=0, description="Failed repair upload count")
