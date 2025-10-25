from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class LogEntryCreate(BaseModel):
    source: str = Field(..., description="Configured node name for the log source")
    timestamp: datetime = Field(..., description="Timestamp recorded in the log entry")
    level: str = Field(..., description="Log severity level")
    area: str = Field(..., description="Subsystem emitting the log entry")
    action: str = Field(..., description="Event descriptor within the subsystem")
    details: Dict[str, Any] = Field(default_factory=dict, description="Parsed log metadata payload")


class LogEntryRead(BaseModel):
    id: int
    source: str
    timestamp: datetime
    level: str
    area: str
    action: str
    details: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class LogEntryFilters(BaseModel):
    source: Optional[str] = Field(
        default=None, description="Filter by the configured node name that produced the log entry"
    )
    level: Optional[str] = Field(
        default=None, description="Filter by log level, e.g. INFO, WARN, ERROR"
    )
    area: Optional[str] = Field(
        default=None, description="Filter by Storj subsystem area value"
    )
    action: Optional[str] = Field(
        default=None, description="Filter by action within the subsystem"
    )
    limit: int = Field(default=100, ge=1, le=1000, description="Maximum number of records to return")


class ReputationCreate(BaseModel):
    source: str
    satellite_id: str
    timestamp: datetime
    audits_total: int
    audits_success: int
    score_audit: float
    score_online: float
    score_suspension: float


class ReputationRead(BaseModel):
    source: str
    satellite_id: str
    timestamp: datetime
    audits_total: int
    audits_success: int
    score_audit: float
    score_online: float
    score_suspension: float
    model_config = ConfigDict(from_attributes=True)


class ReputationFilters(BaseModel):
    source: Optional[str] = Field(default=None, description="Filter by configured node name")
    satellite_id: Optional[str] = Field(default=None, description="Filter by satellite identifier")
    limit: int = Field(default=100, ge=1, le=1000, description="Maximum number of records to return")


class TransferCreate(BaseModel):
    source: str = Field(..., description="Configured node name for the log source")
    timestamp: datetime = Field(..., description="Timestamp recorded in the log entry")
    action: str = Field(..., description="Transfer action code (DL or UL)")
    is_success: bool = Field(..., description="True when the transfer completed successfully")
    piece_id: str = Field(..., description="Piece identifier")
    satellite_id: str = Field(..., description="Satellite identifier")
    is_repair: bool = Field(..., description="True when the transfer is a repair operation")
    size: int = Field(..., description="Transfer size in bytes")
    offset: Optional[int] = Field(default=None, description="Transfer offset")
    remote_address: Optional[str] = Field(default=None, description="Remote address for the transfer")


class TransferRead(BaseModel):
    id: int
    source: str
    timestamp: datetime
    action: str
    is_success: bool
    piece_id: str
    satellite_id: str
    is_repair: bool
    size: int
    offset: Optional[int]
    remote_address: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class TransferFilters(BaseModel):
    source: Optional[str] = None
    action: Optional[str] = None
    satellite_id: Optional[str] = None
    piece_id: Optional[str] = None
    is_success: Optional[bool] = None
    is_repair: Optional[bool] = None
    limit: int = Field(default=100, ge=1, le=1000)


class NodeConfig(BaseModel):
    name: str = Field(..., description="Node identifier configured in settings")
    path: str = Field(..., description="Absolute path to the node log file")
