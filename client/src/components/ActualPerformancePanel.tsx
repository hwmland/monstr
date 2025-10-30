import type { FC } from "react";

import { resolveSuccessColor } from "../utils/colors";
import type { TransferActualAggregated } from "../types";
import { formatWindowTime } from "../utils/time";
import {
  formatRateValue,
  formatSizeValue,
  pickRatePresentation,
  pickSizePresentation,
} from "../utils/units";
import type { RateUnit, SizeUnit } from "../utils/units";

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
      </div>
    </section>
  );
};

export default ActualPerformancePanel;
