import type { FC } from "react";

import { COLOR_STATUS_GREEN, COLOR_STATUS_RED, COLOR_STATUS_YELLOW } from "../constants/colors";
import type { TransferActualAggregated } from "../types";

const formatWindowTime = (value: string | null | undefined): string => {
  if (!value) {
    return "—";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "—";
  }

  return parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
};

type RateUnit = "bps" | "Kbps" | "Mbps";

const RATE_UNITS: Array<{ unit: RateUnit; factor: number }> = [
  { unit: "bps", factor: 1 },
  { unit: "Kbps", factor: 1_000 },
  { unit: "Mbps", factor: 1_000_000 },
];

const pickRatePresentation = (bitRate: number): { value: number; unit: RateUnit } => {
  const safeRate = Number.isFinite(bitRate) && bitRate > 0 ? bitRate : 0;

  for (const candidate of RATE_UNITS) {
    const candidateValue = safeRate / candidate.factor;
    if (candidateValue >= 1 && candidateValue < 1_000) {
      return { value: candidateValue, unit: candidate.unit };
    }
  }

  const largestUnit = RATE_UNITS[RATE_UNITS.length - 1];
  if (safeRate >= largestUnit.factor) {
    return { value: safeRate / largestUnit.factor, unit: largestUnit.unit };
  }

  return { value: safeRate, unit: RATE_UNITS[0].unit };
};

const formatRateValue = (value: number): string => {
  if (value === 0) {
    return "0.00";
  }
  if (value >= 100) {
    return value.toFixed(1);
  }
  return value.toFixed(2);
};

interface MetricView {
  operationsTotal: number;
  operationsSuccess: number;
  successRate: number;
  bitRate: number;
  rateValue: number;
  rateUnit: RateUnit;
}

const buildMetricView = (
  operationsTotal: number,
  operationsSuccess: number,
  rateBytesPerSecond: number,
): MetricView => {
  const total = Number.isFinite(operationsTotal) ? operationsTotal : 0;
  const success = Number.isFinite(operationsSuccess) ? operationsSuccess : 0;
  const bytesRate = Number.isFinite(rateBytesPerSecond) ? rateBytesPerSecond : 0;

  const successRate = total > 0 ? (success / total) * 100 : 0;
  const bitRate = bytesRate * 8;
  const { value: rateValue, unit: rateUnit } = pickRatePresentation(bitRate);

  return {
    operationsTotal: total,
    operationsSuccess: success,
    successRate,
    bitRate,
    rateValue,
    rateUnit,
  };
};

const resolveSuccessColor = (percent: number): string => {
  if (percent < 80) {
    return COLOR_STATUS_RED;
  }
  if (percent >= 90) {
    return COLOR_STATUS_GREEN;
  }
  return COLOR_STATUS_YELLOW;
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
  const windowStart = formatWindowTime(aggregated?.startTime ?? null);
  const windowEnd = formatWindowTime(aggregated?.endTime ?? null);
  const nodesLabel = selectedNodes.length === 0
    ? "All nodes"
    : `Nodes: ${selectedNodes.join(", ")}`;

  const downloadView = buildMetricView(
    aggregated?.download.operationsTotal ?? 0,
    aggregated?.download.operationsSuccess ?? 0,
    aggregated?.download.rate ?? 0,
  );

  const uploadView = buildMetricView(
    aggregated?.upload.operationsTotal ?? 0,
    aggregated?.upload.operationsSuccess ?? 0,
    aggregated?.upload.rate ?? 0,
  );

  const hasActivity =
    downloadView.operationsTotal > 0 ||
    uploadView.operationsTotal > 0 ||
    downloadView.bitRate > 0 ||
    uploadView.bitRate > 0;

  return (
    <section className="panel">
      <header className="panel__header">
        <div>
          <h2 className="panel__title">Actual Performance</h2>
          <p className="panel__subtitle">
            Window: {windowStart} – {windowEnd} • {nodesLabel}
          </p>
        </div>
        <button className="button" type="button" onClick={() => refresh()} disabled={isLoading}>
          {isLoading ? "Loading…" : "Refresh"}
        </button>
      </header>

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
      </div>
    </section>
  );
};

export default ActualPerformancePanel;
