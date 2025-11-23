from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Column, DateTime, Float, String, Boolean, Integer
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

    is_processed: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="0", index=True),
        description="Flag indicating transfer has been processed",
    )


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


class TransferGrouped(SQLModel, table=True):
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
    granularity: int = Field(
        sa_column=Column("granularity", Integer, nullable=False),
        description="Granularity in minutes used to group this record",
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


class Paystub(SQLModel, table=True):
    """Monthly paystub snapshot sourced from Storj node metrics."""

    source: str = Field(
        sa_column=Column(String(32), primary_key=True, nullable=False),
        description="Configured node name for the log source",
    )
    satellite_id: str = Field(
        sa_column=Column(String(64), primary_key=True, nullable=False),
        description="Satellite identifier",
    )
    period: str = Field(
        sa_column=Column(String(32), primary_key=True, nullable=False, index=True),
        description="Pay period identifier (e.g. 2025-10)",
    )
    created: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
        description="Timestamp when the paystub snapshot was recorded",
    )
    usage_at_rest: float = Field(
        sa_column=Column(Float, nullable=False),
        description="TB-hours used at rest",
    )
    usage_get: float = Field(sa_column=Column(Float, nullable=False), description="Egress usage")
    usage_put: float = Field(sa_column=Column(Float, nullable=False), description="Ingress usage")
    usage_get_repair: float = Field(
        sa_column=Column(Float, nullable=False), description="Repair egress usage"
    )
    usage_put_repair: float = Field(
        sa_column=Column(Float, nullable=False), description="Repair ingress usage"
    )
    usage_get_audit: float = Field(
        sa_column=Column(Float, nullable=False), description="Audit egress usage"
    )
    comp_at_rest: float = Field(sa_column=Column(Float, nullable=False), description="At rest compensation")
    comp_get: float = Field(sa_column=Column(Float, nullable=False), description="Download compensation")
    comp_put: float = Field(sa_column=Column(Float, nullable=False), description="Upload compensation")
    comp_get_repair: float = Field(
        sa_column=Column(Float, nullable=False), description="Repair download compensation"
    )
    comp_put_repair: float = Field(
        sa_column=Column(Float, nullable=False), description="Repair upload compensation"
    )
    comp_get_audit: float = Field(
        sa_column=Column(Float, nullable=False), description="Audit download compensation"
    )
    surge_percent: float = Field(
        sa_column=Column(Float, nullable=False), description="Applied surge percentage"
    )
    held: float = Field(sa_column=Column(Float, nullable=False), description="Held amount")
    owed: float = Field(sa_column=Column(Float, nullable=False), description="Owed amount")
    disposed: float = Field(sa_column=Column(Float, nullable=False), description="Disposed amount")
    paid: float = Field(sa_column=Column(Float, nullable=False), description="Paid amount")
    distributed: float = Field(
        sa_column=Column(Float, nullable=False), description="Distributed (payout) amount"
    )


class HeldAmount(SQLModel, table=True):
    """Per-node held payout amounts recorded from nodeapi or other sources."""

    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(
        sa_column=Column(String(32), index=True, nullable=False),
        description="Configured node name for the log source",
    )
    satellite_id: str = Field(
        sa_column=Column(String(64), nullable=False),
        description="Satellite identifier",
    )
    timestamp: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
        description="Timestamp associated with the held amount",
    )
    amount: float = Field(
        sa_column=Column(Float, nullable=False),
        description="Held amount (flat)",
    )
