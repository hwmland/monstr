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

interface MetricView {
  operationsTotal: number;
  operationsSuccess: number;
  successRate: number;
  rateMbps: number;
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
  const rateMbps = (bytesRate * 8) / 1_000_000;

  return { operationsTotal: total, operationsSuccess: success, successRate, rateMbps };
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
    downloadView.rateMbps > 0 ||
    uploadView.rateMbps > 0;

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
            <p className="performance-value">{downloadView.rateMbps.toFixed(2)} Mbps</p>
          </article>
          <article className="performance-cell">
            <p className="performance-label">Upload Speed</p>
            <p className="performance-value">{uploadView.rateMbps.toFixed(2)} Mbps</p>
          </article>
        </div>
      </div>
    </section>
  );
};

export default ActualPerformancePanel;
