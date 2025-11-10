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


class ReputationPanelRequest(BaseModel):
    nodes: list[str] = Field(
        default_factory=list,
        description="Nodes to include when aggregating reputation metrics",
    )


class SatelliteReputationRead(BaseModel):
    satellite_id: str
    timestamp: datetime
    audits_total: int
    audits_success: int
    score_audit: float
    score_online: float
    score_suspension: float

    model_config = ConfigDict(from_attributes=True)


class NodeReputationRead(BaseModel):
    node: str = Field(..., description="Configured node name")
    satellites: list[SatelliteReputationRead] = Field(
        default_factory=list,
        description="Reputation metrics grouped by satellite",
    )


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
    is_processed: bool
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


class TransferActualRequest(BaseModel):
    nodes: list[str] = Field(default_factory=list, description="Nodes to include in the aggregation")


class TransferActualMetrics(BaseModel):
    operations_total: int = Field(alias="operationsTotal", default=0)
    operations_success: int = Field(alias="operationsSuccess", default=0)
    data_bytes: int = Field(alias="dataBytes", default=0)
    rate: float = 0.0

    model_config = ConfigDict(populate_by_name=True)


class TransferActualCategoryMetrics(BaseModel):
    normal: TransferActualMetrics
    repair: TransferActualMetrics

    model_config = ConfigDict(populate_by_name=True)


class TransferActualSatelliteMetrics(BaseModel):
    satellite_id: str = Field(alias="satelliteId")
    download: TransferActualCategoryMetrics
    upload: TransferActualCategoryMetrics

    model_config = ConfigDict(populate_by_name=True)


class TransferActualResponse(BaseModel):
    start_time: datetime = Field(alias="startTime")
    end_time: datetime = Field(alias="endTime")
    download: TransferActualCategoryMetrics
    upload: TransferActualCategoryMetrics
    satellites: list[TransferActualSatelliteMetrics] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class TransferGroupedCreate(BaseModel):
    source: str
    satellite_id: str = Field(serialization_alias="satelliteId", validation_alias="satelliteId")
    interval_start: datetime = Field(serialization_alias="intervalStart", validation_alias="intervalStart")
    interval_end: datetime = Field(serialization_alias="intervalEnd", validation_alias="intervalEnd")
    size_class: str = Field(serialization_alias="sizeClass", validation_alias="sizeClass")
    granularity: int = Field(default=0, serialization_alias="granularity", validation_alias="granularity")
    size_dl_succ_nor: int = Field(default=0, serialization_alias="sizeDlSuccNor", validation_alias="sizeDlSuccNor")
    size_ul_succ_nor: int = Field(default=0, serialization_alias="sizeUlSuccNor", validation_alias="sizeUlSuccNor")
    size_dl_fail_nor: int = Field(default=0, serialization_alias="sizeDlFailNor", validation_alias="sizeDlFailNor")
    size_ul_fail_nor: int = Field(default=0, serialization_alias="sizeUlFailNor", validation_alias="sizeUlFailNor")
    size_dl_succ_rep: int = Field(default=0, serialization_alias="sizeDlSuccRep", validation_alias="sizeDlSuccRep")
    size_ul_succ_rep: int = Field(default=0, serialization_alias="sizeUlSuccRep", validation_alias="sizeUlSuccRep")
    size_dl_fail_rep: int = Field(default=0, serialization_alias="sizeDlFailRep", validation_alias="sizeDlFailRep")
    size_ul_fail_rep: int = Field(default=0, serialization_alias="sizeUlFailRep", validation_alias="sizeUlFailRep")
    count_dl_succ_nor: int = Field(default=0, serialization_alias="countDlSuccNor", validation_alias="countDlSuccNor")
    count_ul_succ_nor: int = Field(default=0, serialization_alias="countUlSuccNor", validation_alias="countUlSuccNor")
    count_dl_fail_nor: int = Field(default=0, serialization_alias="countDlFailNor", validation_alias="countDlFailNor")
    count_ul_fail_nor: int = Field(default=0, serialization_alias="countUlFailNor", validation_alias="countUlFailNor")
    count_dl_succ_rep: int = Field(default=0, serialization_alias="countDlSuccRep", validation_alias="countDlSuccRep")
    count_ul_succ_rep: int = Field(default=0, serialization_alias="countUlSuccRep", validation_alias="countUlSuccRep")
    count_dl_fail_rep: int = Field(default=0, serialization_alias="countDlFailRep", validation_alias="countDlFailRep")
    count_ul_fail_rep: int = Field(default=0, serialization_alias="countUlFailRep", validation_alias="countUlFailRep")

    model_config = ConfigDict(populate_by_name=True)


class TransferGroupedRead(BaseModel):
    id: int
    source: str
    satellite_id: str = Field(serialization_alias="satelliteId")
    interval_start: datetime = Field(serialization_alias="intervalStart")
    interval_end: datetime = Field(serialization_alias="intervalEnd")
    size_class: str = Field(serialization_alias="sizeClass")
    size_dl_succ_nor: int = Field(serialization_alias="sizeDlSuccNor")
    size_ul_succ_nor: int = Field(serialization_alias="sizeUlSuccNor")
    size_dl_fail_nor: int = Field(serialization_alias="sizeDlFailNor")
    size_ul_fail_nor: int = Field(serialization_alias="sizeUlFailNor")
    size_dl_succ_rep: int = Field(serialization_alias="sizeDlSuccRep")
    size_ul_succ_rep: int = Field(serialization_alias="sizeUlSuccRep")
    size_dl_fail_rep: int = Field(serialization_alias="sizeDlFailRep")
    size_ul_fail_rep: int = Field(serialization_alias="sizeUlFailRep")
    granularity: int = Field(serialization_alias="granularity")
    count_dl_succ_nor: int = Field(serialization_alias="countDlSuccNor")
    count_ul_succ_nor: int = Field(serialization_alias="countUlSuccNor")
    count_dl_fail_nor: int = Field(serialization_alias="countDlFailNor")
    count_ul_fail_nor: int = Field(serialization_alias="countUlFailNor")
    count_dl_succ_rep: int = Field(serialization_alias="countDlSuccRep")
    count_ul_succ_rep: int = Field(serialization_alias="countUlSuccRep")
    count_dl_fail_rep: int = Field(serialization_alias="countDlFailRep")
    count_ul_fail_rep: int = Field(serialization_alias="countUlFailRep")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class TransferGroupedFilters(BaseModel):
    source: Optional[str] = None
    satellite_id: Optional[str] = Field(default=None, serialization_alias="satelliteId", validation_alias="satelliteId")
    size_class: Optional[str] = Field(default=None, serialization_alias="sizeClass", validation_alias="sizeClass")
    granularity: Optional[int] = Field(default=None)
    interval_start_from: Optional[datetime] = Field(default=None, serialization_alias="intervalStartFrom", validation_alias="intervalStartFrom")
    interval_start_to: Optional[datetime] = Field(default=None, serialization_alias="intervalStartTo", validation_alias="intervalStartTo")
    limit: int = Field(default=100, ge=1, le=1000)

    model_config = ConfigDict(populate_by_name=True)


class NodeConfig(BaseModel):
    name: str = Field(..., description="Node identifier configured in settings")
    path: str = Field(..., description="Absolute path to the node log file")
    nodeapi: Optional[str] = Field(default=None, description="Optional HTTP(S) node API endpoint (nodeapi)")


class DataDistributionRequest(BaseModel):
    nodes: list[str] = Field(default_factory=list, description="Nodes to include in the distribution; empty means all nodes.")


class DataDistributionItem(BaseModel):
    size_class: str = Field(serialization_alias="sizeClass")
    size_dl_succ_nor: int = Field(default=0, serialization_alias="sizeDlSuccNor")
    size_ul_succ_nor: int = Field(default=0, serialization_alias="sizeUlSuccNor")
    size_dl_fail_nor: int = Field(default=0, serialization_alias="sizeDlFailNor")
    size_ul_fail_nor: int = Field(default=0, serialization_alias="sizeUlFailNor")
    size_dl_succ_rep: int = Field(default=0, serialization_alias="sizeDlSuccRep")
    size_ul_succ_rep: int = Field(default=0, serialization_alias="sizeUlSuccRep")
    size_dl_fail_rep: int = Field(default=0, serialization_alias="sizeDlFailRep")
    size_ul_fail_rep: int = Field(default=0, serialization_alias="sizeUlFailRep")

    count_dl_succ_nor: int = Field(default=0, serialization_alias="countDlSuccNor")
    count_ul_succ_nor: int = Field(default=0, serialization_alias="countUlSuccNor")
    count_dl_fail_nor: int = Field(default=0, serialization_alias="countDlFailNor")
    count_ul_fail_nor: int = Field(default=0, serialization_alias="countUlFailNor")
    count_dl_succ_rep: int = Field(default=0, serialization_alias="countDlSuccRep")
    count_ul_succ_rep: int = Field(default=0, serialization_alias="countUlSuccRep")
    count_dl_fail_rep: int = Field(default=0, serialization_alias="countDlFailRep")
    count_ul_fail_rep: int = Field(default=0, serialization_alias="countUlFailRep")


class DataDistributionResponse(BaseModel):
    start_time: datetime = Field(serialization_alias="startTime")
    end_time: datetime = Field(serialization_alias="endTime")
    distribution: list[DataDistributionItem] = Field(serialization_alias="distribution")

    model_config = ConfigDict(populate_by_name=True)


class IntervalTransferBucket(BaseModel):
    bucket_start: datetime = Field(serialization_alias="bucketStart")
    bucket_end: datetime = Field(serialization_alias="bucketEnd")

    # size fields (bytes)
    size_dl_succ_nor: int = Field(default=0, serialization_alias="sizeDlSuccNor")
    size_ul_succ_nor: int = Field(default=0, serialization_alias="sizeUlSuccNor")
    size_dl_fail_nor: int = Field(default=0, serialization_alias="sizeDlFailNor")
    size_ul_fail_nor: int = Field(default=0, serialization_alias="sizeUlFailNor")
    size_dl_succ_rep: int = Field(default=0, serialization_alias="sizeDlSuccRep")
    size_ul_succ_rep: int = Field(default=0, serialization_alias="sizeUlSuccRep")
    size_dl_fail_rep: int = Field(default=0, serialization_alias="sizeDlFailRep")
    size_ul_fail_rep: int = Field(default=0, serialization_alias="sizeUlFailRep")

    # count fields
    count_dl_succ_nor: int = Field(default=0, serialization_alias="countDlSuccNor")
    count_ul_succ_nor: int = Field(default=0, serialization_alias="countUlSuccNor")
    count_dl_fail_nor: int = Field(default=0, serialization_alias="countDlFailNor")
    count_ul_fail_nor: int = Field(default=0, serialization_alias="countUlFailNor")
    count_dl_succ_rep: int = Field(default=0, serialization_alias="countDlSuccRep")
    count_ul_succ_rep: int = Field(default=0, serialization_alias="countUlSuccRep")
    count_dl_fail_rep: int = Field(default=0, serialization_alias="countDlFailRep")
    count_ul_fail_rep: int = Field(default=0, serialization_alias="countUlFailRep")


class IntervalTransferResponse(BaseModel):
    start_time: datetime = Field(serialization_alias="startTime")
    end_time: datetime = Field(serialization_alias="endTime")
    buckets: list[IntervalTransferBucket] = Field(serialization_alias="buckets")

    model_config = ConfigDict(populate_by_name=True)


class IntervalTransfersRequest(BaseModel):
    nodes: list[str] = Field(default_factory=list, description="Nodes to include in aggregation; empty means all nodes.")
    interval_length: str = Field(default="1h", description="Interval length string, e.g. '10s','2m','10m','1h'.", validation_alias="intervalLength", serialization_alias="intervalLength")
    number_of_intervals: int = Field(default=6, ge=1, le=1000, description="Number of intervals to include backwards from now", validation_alias="numberOfIntervals", serialization_alias="numberOfIntervals")

    model_config = ConfigDict(populate_by_name=True)


class OverallStatusRequest(BaseModel):
    nodes: list[str] = Field(default_factory=list, description="Nodes to include; empty means all nodes")


class PayoutCurrentRequest(BaseModel):
    nodes: list[str] = Field(default_factory=list, description="Nodes to include; empty means all nodes")


class PayoutNode(BaseModel):
    joined_at: Optional[datetime] = Field(default=None, serialization_alias="joinedAt")
    last_estimated_payout_at: Optional[datetime] = Field(default=None, serialization_alias="lastEstimatedPayoutAt")
    estimated_payout: Optional[float] = Field(default=None, serialization_alias="estimatedPayout")
    held_back_payout: Optional[float] = Field(default=None, serialization_alias="heldBackPayout")
    total_held_payout: Optional[float] = Field(default=None, serialization_alias="totalHeldPayout")
    download_payout: Optional[float] = Field(default=None, serialization_alias="downloadPayout")
    repair_payout: Optional[float] = Field(default=None, serialization_alias="repairPayout")
    disk_payout: Optional[float] = Field(default=None, serialization_alias="diskPayout")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PayoutCurrentResponse(BaseModel):
    nodes: dict[str, PayoutNode] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TransferWindowMetrics(BaseModel):
    download_size: int = Field(default=0, serialization_alias="downloadSize")
    upload_size: int = Field(default=0, serialization_alias="uploadSize")
    download_count: int = Field(default=0, serialization_alias="downloadCount")
    upload_count: int = Field(default=0, serialization_alias="uploadCount")
    download_count_total: int = Field(default=0, serialization_alias="downloadCountTotal")
    upload_count_total: int = Field(default=0, serialization_alias="uploadCountTotal")
    download_success_rate: float = Field(default=0.0, serialization_alias="downloadSuccessRate")
    upload_success_rate: float = Field(default=0.0, serialization_alias="uploadSuccessRate")
    download_speed: float = Field(default=0.0, serialization_alias="downloadSpeed")
    upload_speed: float = Field(default=0.0, serialization_alias="uploadSpeed")

    model_config = ConfigDict(populate_by_name=True)


class NodeOverallMetrics(BaseModel):
    node: str = Field(..., description="Node name")

    # reputation aggregates
    min_online: float = Field(default=0.0, serialization_alias="minOnline")
    min_audit: float = Field(default=0.0, serialization_alias="minAudit")
    min_suspension: float = Field(default=0.0, serialization_alias="minSuspension")
    avg_online: float = Field(default=0.0, serialization_alias="avgOnline")
    avg_audit: float = Field(default=0.0, serialization_alias="avgAudit")
    avg_suspension: float = Field(default=0.0, serialization_alias="avgSuspension")

    # transfer windows
    minute1: TransferWindowMetrics = Field(default_factory=TransferWindowMetrics)
    minute3: TransferWindowMetrics = Field(default_factory=TransferWindowMetrics)
    minute5: TransferWindowMetrics = Field(default_factory=TransferWindowMetrics)

    # current month payout information gathered from nodeapi (optional)
    class CurrentMonthPayout(BaseModel):
        estimated_payout: Optional[float] = Field(default=None, serialization_alias="estimatedPayout", validation_alias="estimatedPayout")
        held_back_payout: Optional[float] = Field(default=None, serialization_alias="heldBackPayout", validation_alias="heldBackPayout")
        download_payout: Optional[float] = Field(default=None, serialization_alias="downloadPayout", validation_alias="downloadPayout")
        repair_payout: Optional[float] = Field(default=None, serialization_alias="repairPayout", validation_alias="repairPayout")
        disk_payout: Optional[float] = Field(default=None, serialization_alias="diskPayout", validation_alias="diskPayout")
        total_held_payout: Optional[float] = Field(default=None, serialization_alias="totalHeldPayout", validation_alias="totalHeldPayout")

        model_config = ConfigDict(populate_by_name=True)

    current_month_payout: CurrentMonthPayout = Field(default_factory=CurrentMonthPayout, serialization_alias="currentMonthPayout")

    model_config = ConfigDict(populate_by_name=True)


class OverallStatusResponse(BaseModel):
    total: NodeOverallMetrics
    nodes: dict[str, NodeOverallMetrics] = Field(default_factory=dict)


class HeldAmountFilters(BaseModel):
    source: Optional[str] = Field(default=None, description="Filter by node/source name")
    satellite_id: Optional[str] = Field(default=None, serialization_alias="satelliteId", validation_alias="satelliteId")
    limit: int = Field(default=100, ge=1, le=1000)


class HeldAmountRead(BaseModel):
    id: int
    source: str
    satellite_id: str = Field(serialization_alias="satelliteId")
    timestamp: datetime
    amount: float
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
