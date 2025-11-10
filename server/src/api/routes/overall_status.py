from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_session
from ...repositories.reputations import ReputationRepository
from ...repositories.transfers import TransferRepository
from ...schemas import OverallStatusRequest, OverallStatusResponse, NodeOverallMetrics, TransferWindowMetrics
from ...services.node_api import NodeApiService
from datetime import datetime, timezone, timedelta
from typing import Optional

router = APIRouter(prefix="/api/overall-status", tags=["overall-status"])


@router.post("", response_model=OverallStatusResponse)
async def overall_status(payload: OverallStatusRequest, request: Request, session: AsyncSession = Depends(get_session)) -> OverallStatusResponse:
    now = datetime.now(timezone.utc)

    # reputations
    rep_repo = ReputationRepository(session)
    requested_nodes = sorted({n for n in payload.nodes if n})
    fetch_all = not requested_nodes

    if fetch_all:
        reputations = await rep_repo.list_all()
    else:
        reputations = await rep_repo.list_for_sources(requested_nodes)

    # group reputations per node
    reps_by_node: dict[str, list] = {}
    for r in reputations:
        reps_by_node.setdefault(r.source, []).append(r)

    nodes = requested_nodes if not fetch_all else sorted(reps_by_node.keys())

    # Attempt to obtain NodeApiService instance from the running app state so
    # we can enrich per-node metrics with current-month payout information.
    # The route accepts a Request parameter so FastAPI will provide access to
    # `request.app.state` where the service is stored on startup.
    nodeapi_service: NodeApiService | None = None
    # The request object will be available as a parameter to the route; if
    # the service isn't registered we simply skip enrichment.
    try:
        svc = getattr(request.app.state, "nodeapi_service", None) or getattr(request.app.state, "node_api_service", None)
        if isinstance(svc, NodeApiService):
            nodeapi_service = svc
    except Exception:
        nodeapi_service = None

    # transfers in last 5 minutes
    transfer_repo = TransferRepository(session)
    start_5 = now - timedelta(minutes=5)
    transfers = await transfer_repo.list_for_sources_between(requested_nodes or None, start_5, now)

    # group transfers per node
    tx_by_node: dict[str, list] = {}
    for t in transfers:
        tx_by_node.setdefault(t.source, []).append(t)

    def _to_utc(dt: datetime) -> datetime:
        if dt is None:
            return dt
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def compute_transfer_metrics(tx_list: list, window_seconds: int) -> TransferWindowMetrics:
        # tx_list is list of Transfer objects filtered to the desired window
        download_size = sum(t.size for t in tx_list if t.action == 'DL' and t.is_success)
        upload_size = sum(t.size for t in tx_list if t.action == 'UL' and t.is_success)
        download_count = sum(1 for t in tx_list if t.action == 'DL' and t.is_success)
        upload_count = sum(1 for t in tx_list if t.action == 'UL' and t.is_success)
        download_count_total = sum(1 for t in tx_list if t.action == 'DL')
        upload_count_total = sum(1 for t in tx_list if t.action == 'UL')
        download_success_rate = (download_count / download_count_total) if download_count_total > 0 else 0.0
        upload_success_rate = (upload_count / upload_count_total) if upload_count_total > 0 else 0.0
        download_speed = (download_size / window_seconds) * 8.0  # bps
        upload_speed = (upload_size / window_seconds) * 8.0
        return TransferWindowMetrics(
            download_size=download_size,
            upload_size=upload_size,
            download_count=download_count,
            upload_count=upload_count,
            download_count_total=download_count_total,
            upload_count_total=upload_count_total,
            download_success_rate=download_success_rate,
            upload_success_rate=upload_success_rate,
            download_speed=download_speed,
            upload_speed=upload_speed,
        )

    per_node_metrics: list[NodeOverallMetrics] = []

    for node in nodes:
        # reputations
        reps = reps_by_node.get(node, [])
        if reps:
            min_online = min(r.score_online for r in reps)
            min_audit = min(r.score_audit for r in reps)
            min_suspension = min(r.score_suspension for r in reps)
            avg_online = sum(r.score_online for r in reps) / len(reps)
            avg_audit = sum(r.score_audit for r in reps) / len(reps)
            avg_suspension = sum(r.score_suspension for r in reps) / len(reps)
        else:
            min_online = min_audit = min_suspension = 0.0
            avg_online = avg_audit = avg_suspension = 0.0

        txs = tx_by_node.get(node, [])
        # compute minute1 (last 1 minute), minute3 (last 3), minute5 (last 5)
        cutoff1 = now - timedelta(minutes=1)
        cutoff3 = now - timedelta(minutes=3)
        minute1_list = [t for t in txs if _to_utc(t.timestamp) >= cutoff1]
        minute3_list = [t for t in txs if _to_utc(t.timestamp) >= cutoff3]
        minute5_list = [t for t in txs if _to_utc(t.timestamp) >= start_5]

        minute1 = compute_transfer_metrics(minute1_list, 60)
        minute3 = compute_transfer_metrics(minute3_list, 3 * 60)
        minute5 = compute_transfer_metrics(minute5_list, 5 * 60)

        per_node_metrics.append(
            NodeOverallMetrics(
                node=node,
                min_online=min_online,
                min_audit=min_audit,
                min_suspension=min_suspension,
                avg_online=avg_online,
                avg_audit=avg_audit,
                avg_suspension=avg_suspension,
                minute1=minute1,
                minute3=minute3,
                minute5=minute5,
            )
        )

    # If nodeapi service is available, fetch NodeData snapshots and attach
    # current month payout information to the corresponding NodeOverallMetrics
    if nodeapi_service is not None:
        try:
            node_data_map = await nodeapi_service.get_node_data(nodes or None)
            # node_data_map: dict[str, NodeData]
            for n in per_node_metrics:
                nd = node_data_map.get(n.node)
                if not nd:
                    continue
                # populate the current_month_payout field
                n.current_month_payout = NodeOverallMetrics.CurrentMonthPayout(
                    estimated_payout=nd.estimated_payout,
                    held_back_payout=nd.held_back_payout,
                    download_payout=nd.download_payout,
                    repair_payout=nd.repair_payout,
                    disk_payout=nd.disk_payout,
                    total_held_payout=nd.total_held_amount,
                )
        except Exception:
            # non-fatal: if enrichment fails, continue without payout data
            pass

    # compute overall totals by summing per-node values
    if per_node_metrics:
        # reputations: min of mins, average of averages (weighted by satellite count isn't available here so use simple mean)
        total_min_online = min(n.min_online for n in per_node_metrics)
        total_min_audit = min(n.min_audit for n in per_node_metrics)
        total_min_suspension = min(n.min_suspension for n in per_node_metrics)
        total_avg_online = sum(n.avg_online for n in per_node_metrics) / len(per_node_metrics)
        total_avg_audit = sum(n.avg_audit for n in per_node_metrics) / len(per_node_metrics)
        total_avg_suspension = sum(n.avg_suspension for n in per_node_metrics) / len(per_node_metrics)

        # transfer windows: sum sizes and counts, recompute rates and speeds over combined window
        def sum_windows(attr: str, window_name: str) -> int:
            return sum(getattr(getattr(n, window_name), attr) for n in per_node_metrics)

        total_minute1 = TransferWindowMetrics(
            download_size=sum_windows('download_size', 'minute1'),
            upload_size=sum_windows('upload_size', 'minute1'),
            download_count=sum_windows('download_count', 'minute1'),
            upload_count=sum_windows('upload_count', 'minute1'),
            download_count_total=sum_windows('download_count_total', 'minute1'),
            upload_count_total=sum_windows('upload_count_total', 'minute1'),
            download_success_rate=(sum_windows('download_count', 'minute1') / sum_windows('download_count_total', 'minute1')) if sum_windows('download_count_total', 'minute1') > 0 else 0.0,
            upload_success_rate=(sum_windows('upload_count', 'minute1') / sum_windows('upload_count_total', 'minute1')) if sum_windows('upload_count_total', 'minute1') > 0 else 0.0,
            download_speed=(sum_windows('download_size', 'minute1') / 60.0) * 8.0,
            upload_speed=(sum_windows('upload_size', 'minute1') / 60.0) * 8.0,
        )

        total_minute3 = TransferWindowMetrics(
            download_size=sum_windows('download_size', 'minute3'),
            upload_size=sum_windows('upload_size', 'minute3'),
            download_count=sum_windows('download_count', 'minute3'),
            upload_count=sum_windows('upload_count', 'minute3'),
            download_count_total=sum_windows('download_count_total', 'minute3'),
            upload_count_total=sum_windows('upload_count_total', 'minute3'),
            download_success_rate=(sum_windows('download_count', 'minute3') / sum_windows('download_count_total', 'minute3')) if sum_windows('download_count_total', 'minute3') > 0 else 0.0,
            upload_success_rate=(sum_windows('upload_count', 'minute3') / sum_windows('upload_count_total', 'minute3')) if sum_windows('upload_count_total', 'minute3') > 0 else 0.0,
            download_speed=(sum_windows('download_size', 'minute3') / (3.0 * 60.0)) * 8.0,
            upload_speed=(sum_windows('upload_size', 'minute3') / (3.0 * 60.0)) * 8.0,
        )

        total_minute5 = TransferWindowMetrics(
            download_size=sum_windows('download_size', 'minute5'),
            upload_size=sum_windows('upload_size', 'minute5'),
            download_count=sum_windows('download_count', 'minute5'),
            upload_count=sum_windows('upload_count', 'minute5'),
            download_count_total=sum_windows('download_count_total', 'minute5'),
            upload_count_total=sum_windows('upload_count_total', 'minute5'),
            download_success_rate=(sum_windows('download_count', 'minute5') / sum_windows('download_count_total', 'minute5')) if sum_windows('download_count_total', 'minute5') > 0 else 0.0,
            upload_success_rate=(sum_windows('upload_count', 'minute5') / sum_windows('upload_count_total', 'minute5')) if sum_windows('upload_count_total', 'minute5') > 0 else 0.0,
            download_speed=(sum_windows('download_size', 'minute5') / (5.0 * 60.0)) * 8.0,
            upload_speed=(sum_windows('upload_size', 'minute5') / (5.0 * 60.0)) * 8.0,
        )

        total_node = NodeOverallMetrics(
            node="total",
            min_online=total_min_online,
            min_audit=total_min_audit,
            min_suspension=total_min_suspension,
            avg_online=total_avg_online,
            avg_audit=total_avg_audit,
            avg_suspension=total_avg_suspension,
            minute1=total_minute1,
            minute3=total_minute3,
            minute5=total_minute5,
        )
    else:
        total_node = NodeOverallMetrics(
            node="total",
        )

    # convert list to mapping node->metrics to match schema change
    per_node_map: dict[str, NodeOverallMetrics] = {n.node: n for n in per_node_metrics}

    # Aggregate currentMonthPayout across nodes for the total. Use the
    # per-node `current_month_payout` values when present; if no node has a
    # non-null value for a given field keep it as None on the total.
    def _aggregate_field(field_name: str) -> Optional[float]:
        vals: list[float] = []
        for n in per_node_metrics:
            cmp = getattr(n, "current_month_payout", None)
            if cmp is None:
                continue
            v = getattr(cmp, field_name, None)
            if v is None:
                continue
            try:
                vals.append(float(v))
            except Exception:
                continue
        if not vals:
            return None
        return sum(vals)

    total_node.current_month_payout = NodeOverallMetrics.CurrentMonthPayout(
        estimated_payout=_aggregate_field("estimated_payout"),
        held_back_payout=_aggregate_field("held_back_payout"),
        download_payout=_aggregate_field("download_payout"),
        repair_payout=_aggregate_field("repair_payout"),
        disk_payout=_aggregate_field("disk_payout"),
        total_held_payout=_aggregate_field("total_held_payout"),
    )

    return OverallStatusResponse(total=total_node, nodes=per_node_map)
