import { FC, useCallback, useEffect, useRef, useState, useLayoutEffect } from "react";
import createRequestDeduper from "../../utils/requestDeduper";
import { createPortal } from "react-dom";

import { resolveSuccessColor } from "../../utils/colors";
import type { TransferActualAggregated, PayoutNode } from "../../types";
import PanelSubtitle from "../PanelSubtitle";
import PanelHeader from "../PanelHeader";
import {
  formatRateValue,
  formatSizeValue,
  pickRatePresentation,
  pickSizePresentation,
} from "../../utils/units";
import type { RateUnit, SizeUnit } from "../../utils/units";
import { fetchPayoutCurrent } from "../../services/apiClient";
import { formatCurrency } from "../../utils/units";

interface MetricView {
  operationsTotal: number;
  operationsSuccess: number;
  successRate: number;
  bitRate: number;
  rateValue: number;
  rateUnit: RateUnit;
  dataBytes: number;
  sizeValue: number;
  sizeUnit: SizeUnit;
}

interface PayoutTotals {
  held: number;
  disk: number;
  download: number;
  repair: number;
  estimated: number;
  totalHeld: number;
}

const buildMetricView = (
  operationsTotal: number,
  operationsSuccess: number,
  rateBytesPerSecond: number,
  dataBytes: number,
): MetricView => {
  const total = Number.isFinite(operationsTotal) ? operationsTotal : 0;
  const success = Number.isFinite(operationsSuccess) ? operationsSuccess : 0;
  const bytesRate = Number.isFinite(rateBytesPerSecond) ? rateBytesPerSecond : 0;
  const bytesTotal = Number.isFinite(dataBytes) ? dataBytes : 0;

  const successRate = total > 0 ? (success / total) * 100 : 0;
  const bitRate = bytesRate * 8;
  const { value: rateValue, unit: rateUnit } = pickRatePresentation(bitRate);
  const { value: sizeValue, unit: sizeUnit } = pickSizePresentation(bytesTotal);

  return {
    operationsTotal: total,
    operationsSuccess: success,
    successRate,
    bitRate,
    rateValue,
    rateUnit,
    dataBytes: bytesTotal,
    sizeValue,
    sizeUnit,
  };
};

const toNumeric = (value: unknown): number => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

interface ActualPerformancePanelProps {
  aggregated: TransferActualAggregated | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => void;
  selectedNodes: string[];
}

const ActualPerformancePanel: FC<ActualPerformancePanelProps> = ({
  aggregated,
  isLoading,
  error,
  refresh,
  selectedNodes,
}) => {
  const [payoutTotals, setPayoutTotals] = useState<PayoutTotals | null>(null);
  const [isPayoutLoading, setIsPayoutLoading] = useState(false);
  const payoutRequestIdRef = useRef(0);
  const isMountedRef = useRef(true);
  const payoutDeduperRef = useRef(createRequestDeduper());

  // tooltip state
  const [tooltipVisible, setTooltipVisible] = useState(false);
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number } | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const refreshPayout = useCallback(async () => {
    // compute a stable nodes argument
    const nodesArg = selectedNodes.length > 0 && !selectedNodes.includes("All") ? [...selectedNodes] : [];
    // dedupe rapid duplicate calls for the same selection (avoid double load)
    const deduper = payoutDeduperRef.current;
    if (deduper.isDuplicate(nodesArg, 1000)) {
      return; // skip duplicate
    }
    const requestId = ++payoutRequestIdRef.current;

    setIsPayoutLoading(true);

    try {
      const payload = await fetchPayoutCurrent(nodesArg);
      const nodesMap: Record<string, PayoutNode | undefined> = (
        payload && typeof payload === "object" && "nodes" in payload
          ? ((payload as { nodes: Record<string, PayoutNode | undefined> }).nodes ?? {})
          : (payload as Record<string, PayoutNode | undefined>)
      ) ?? {};

      const totals: PayoutTotals = {
        held: 0,
        disk: 0,
        download: 0,
        repair: 0,
        estimated: 0,
        totalHeld: 0,
      };

      for (const entry of Object.values(nodesMap)) {
        if (!entry) {
          continue;
        }

        totals.totalHeld += toNumeric(entry.totalHeldPayout);
        totals.held += toNumeric(entry.heldBackPayout);
        totals.disk += toNumeric(entry.diskPayout);
        totals.download += toNumeric(entry.downloadPayout);
        totals.repair += toNumeric(entry.repairPayout);
        totals.estimated += toNumeric(entry.estimatedPayout);
      }

      if (isMountedRef.current && requestId === payoutRequestIdRef.current) {
        setPayoutTotals(totals);
      }
    } catch {
      if (isMountedRef.current && requestId === payoutRequestIdRef.current) {
        setPayoutTotals(null);
      }
    } finally {
      if (isMountedRef.current && requestId === payoutRequestIdRef.current) {
        setIsPayoutLoading(false);
      }
    }
  }, [selectedNodes]);

  const handleRefresh = useCallback(() => {
    refresh();
    void refreshPayout();
  }, [refresh, refreshPayout]);

  useEffect(() => {
    void refreshPayout();

    const intervalId =
      typeof window !== "undefined" ? window.setInterval(() => void refreshPayout(), 60_000) : undefined;

    return () => {
      if (intervalId !== undefined) {
        window.clearInterval(intervalId);
      }
    };
  }, [refreshPayout]);

  // clamp tooltip inside viewport after it renders
  useLayoutEffect(() => {
    if (!tooltipVisible || !tooltipRef.current || !tooltipPos) return;
    const rect = tooltipRef.current.getBoundingClientRect();
    const margin = 8;
    let left = tooltipPos.x;
    let top = tooltipPos.y;
    if (left + rect.width > window.innerWidth - margin) left = Math.max(margin, window.innerWidth - rect.width - margin);
    if (top + rect.height > window.innerHeight - margin) top = Math.max(margin, window.innerHeight - rect.height - margin);
    if (left < margin) left = margin;
    if (top < margin) top = margin;
    if (left !== tooltipPos.x || top !== tooltipPos.y) setTooltipPos({ x: left, y: top });
  }, [tooltipVisible, tooltipPos]);

  function PayoutTooltip({
    tooltipPos,
    tooltipRef,
    payoutTotals,
    displayValue,
  }: {
    tooltipPos: { x: number; y: number } | null;
    tooltipRef: React.RefObject<HTMLDivElement>;
    payoutTotals: PayoutTotals | null;
    displayValue: (v: number) => string;
  }) {
    return (
      <div
        ref={tooltipRef}
        id="payout-tooltip"
        role="tooltip"
        className="payout-tooltip"
        style={{ position: "fixed", left: tooltipPos?.x ?? 0, top: tooltipPos?.y ?? 0 }}
      >
        <div className="payout-tooltip__title">Current Payout</div>
        <div className="payout-tooltip__row"><span>Disk</span><span><strong>{displayValue(payoutTotals?.disk ?? 0)}</strong></span></div>
        <div className="payout-tooltip__row"><span>Download</span><span><strong>{displayValue(payoutTotals?.download ?? 0)}</strong></span></div>
        <div className="payout-tooltip__row"><span>Repair</span><span><strong>{displayValue(payoutTotals?.repair ?? 0)}</strong></span></div>
        <div className="payout-tooltip__row"><span>Held</span><span><strong>{displayValue(payoutTotals?.held ?? 0)}</strong></span></div>
        <div className="payout-tooltip__sep" aria-hidden="true" />
        <div className="payout-tooltip__row"><span>Month Estimated</span><span><strong>{displayValue(payoutTotals?.estimated ?? 0)}</strong></span></div>
        <div className="payout-tooltip__row"><span>Total Held</span><span><strong>{displayValue(payoutTotals?.totalHeld ?? 0)}</strong></span></div>
      </div>
    );
  }

  const downloadView = buildMetricView(
    aggregated?.download.operationsTotal ?? 0,
    aggregated?.download.operationsSuccess ?? 0,
    aggregated?.download.rate ?? 0,
    aggregated?.download.dataBytes ?? 0,
  );

  const uploadView = buildMetricView(
    aggregated?.upload.operationsTotal ?? 0,
    aggregated?.upload.operationsSuccess ?? 0,
    aggregated?.upload.rate ?? 0,
    aggregated?.upload.dataBytes ?? 0,
  );

  const hasActivity =
    downloadView.operationsTotal > 0 ||
    uploadView.operationsTotal > 0 ||
    downloadView.bitRate > 0 ||
    uploadView.bitRate > 0;

  const displayValue = (value: number) =>
    payoutTotals === null ? (isPayoutLoading ? "Loading…" : "Unavailable") : formatCurrency(value);

  return (
    <section className="panel">
      <PanelHeader
        title="Actual Performance"
        subtitle={<PanelSubtitle windowStart={aggregated?.startTime} windowEnd={aggregated?.endTime} selectedNodes={selectedNodes} />}
        onRefresh={handleRefresh}
        isRefreshing={isLoading}
      />

      {error ? <p className="panel__error">{error}</p> : null}

      <div className="panel__body">
        {isLoading && !hasActivity ? (
          <p className="panel__status">Loading transfer performance…</p>
        ) : null}

        {!isLoading && !hasActivity ? (
          <p className="panel__empty">No transfer activity observed in the last hour.</p>
        ) : null}

        <div className="performance-grid">
          <article className="performance-cell performance-cell--top">
            <p className="performance-label">Download Success</p>
            <p
              className="performance-value"
              style={{ color: resolveSuccessColor(downloadView.successRate) }}
            >
              {downloadView.successRate.toFixed(2)}%
            </p>
            <p className="performance-subvalue">
              {downloadView.operationsSuccess} / {downloadView.operationsTotal}
            </p>
            <p className="performance-data-value">
              Data: {formatSizeValue(downloadView.sizeValue)} {downloadView.sizeUnit}
            </p>
          </article>
          <article className="performance-cell performance-cell--top">
            <p className="performance-label">Upload Success</p>
            <p
              className="performance-value"
              style={{ color: resolveSuccessColor(uploadView.successRate) }}
            >
              {uploadView.successRate.toFixed(2)}%
            </p>
            <p className="performance-subvalue">
              {uploadView.operationsSuccess} / {uploadView.operationsTotal}
            </p>
            <p className="performance-data-value">
              Data: {formatSizeValue(uploadView.sizeValue)} {uploadView.sizeUnit}
            </p>
          </article>
          <article className="performance-cell">
            <p className="performance-label">Download Speed</p>
            <p className="performance-value">
              {formatRateValue(downloadView.rateValue)} {downloadView.rateUnit}
            </p>
          </article>
          <article className="performance-cell">
            <p className="performance-label">Upload Speed</p>
            <p className="performance-value">
              {formatRateValue(uploadView.rateValue)} {uploadView.rateUnit}
            </p>
          </article>
        </div>
        <div className="panel__footer">
          {/* payout summary is a focusable interactive element that shows a tooltip on hover/focus */}
          <div
            className="payout-summary"
            tabIndex={0}
            aria-describedby="payout-tooltip"
            onMouseEnter={() => setTooltipVisible(true)}
            onMouseLeave={() => { setTooltipVisible(false); setTooltipPos(null); }}
            onMouseMove={(e: React.MouseEvent<HTMLElement>) => { setTooltipVisible(true); setTooltipPos({ x: e.clientX + 12, y: e.clientY + 12 }); }}
            onFocus={(e) => { const r = (e.currentTarget as HTMLElement).getBoundingClientRect(); setTooltipVisible(true); setTooltipPos({ x: Math.round(r.left + r.width / 2), y: Math.round(r.bottom + 8) }); }}
            onBlur={() => setTooltipVisible(false)}
          >
            <span>Pay: <strong>{displayValue((payoutTotals?.disk ?? 0) + (payoutTotals?.download ?? 0) + (payoutTotals?.repair ?? 0))}</strong></span>
            <span>Held: <strong>{displayValue(payoutTotals?.held ?? 0)}</strong></span>
            <span>Est: <strong>{displayValue(payoutTotals?.estimated ?? 0)}</strong></span>
          </div>

          {typeof document !== "undefined" && tooltipVisible && (
            createPortal(
              <PayoutTooltip
                tooltipPos={tooltipPos}
                tooltipRef={tooltipRef}
                payoutTotals={payoutTotals}
                displayValue={displayValue}
              />,
              document.body,
            )
          )}
        </div>
      </div>
    </section>
  );
};

export default ActualPerformancePanel;
