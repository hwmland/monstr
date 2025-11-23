import { FC, useCallback, useEffect, useMemo, useState } from "react";

import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { fetchPayoutPaystubs } from "../services/apiClient";
import useSelectedNodesStore from "../store/useSelectedNodes";
import type { PaystubRecord } from "../types";
import PanelSubtitle from "./PanelSubtitle";
import { formatSizeValue, pickSizeUnit } from "../utils/units";
import type { SizeUnit } from "../utils/units";

type Mode = "financial" | "data";
type FinancialView = "monthly" | "accumulate";
type FinancialGrouping = "total" | "kind";
type DataSeriesMode = "details" | "totals";

const UsageTooltip: FC<{
  active?: boolean;
  payload?: unknown[];
  label?: string;
  labelMap: Record<string, string>;
  formatValue: (value: number) => string;
  valueFormatters?: Record<string, (value: number) => string>;
}> = ({ active, payload, label, labelMap, formatValue, valueFormatters }) => {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  const entries = payload as Array<{ name?: string; value?: number; color?: string; dataKey?: string }>;

  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__label">{label}</div>
      {entries.map((entry) => {
        const key = entry.dataKey ?? entry.name ?? "entry";
        const displayName = labelMap[String(key)] ?? String(key);
        const numericValue = Number(entry.value ?? 0);
        const formatter = valueFormatters?.[String(key)] ?? formatValue;
        return (
          <div key={String(key)} className="chart-tooltip__row">
            <span style={{ color: entry.color ?? "var(--color-text)" }}>{displayName}:</span>
            <span>{formatter(numericValue)}</span>
          </div>
        );
      })}
    </div>
  );
};

const formatAmount = (value: number) =>
  Number.isFinite(value)
    ? value.toLocaleString(undefined, {
        style: "currency",
        currency: "USD",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })
    : "$0.00";

const formatDateTime = (value: string) => {
  if (!value) {
    return "—";
  }

  const direct = new Date(value);
  if (!Number.isNaN(direct.getTime())) {
    return direct.toLocaleString();
  }

  const withZ = new Date(`${value}Z`);
  if (!Number.isNaN(withZ.getTime())) {
    return withZ.toLocaleString();
  }

  return value;
};

const LongTermTooltip: FC<{ active?: boolean; payload?: unknown[]; label?: string }> = ({ active, payload, label }) => {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  const entries = payload as Array<{ name?: string; value?: number; color?: string; dataKey?: string }>;

  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__label">{label}</div>
      {entries.map((entry) => {
        const key = entry.dataKey ?? entry.name ?? "entry";
        return (
          <div key={String(key)} className="chart-tooltip__row">
            <span style={{ color: entry.color ?? "var(--color-text)" }}>{entry.name ?? key}:</span>
            <span>{formatAmount(Number(entry.value ?? 0))}</span>
          </div>
        );
      })}
    </div>
  );
};

interface ChartPoint {
  period: string;
  owed: number;
  held: number;
  distributed: number;
  disk: number;
  download: number;
  repair: number;
  downloadTotal: number;
  total: number;
}

interface UsageChartPoint {
  period: string;
  diskUsage: number;
}

interface UsageChartPointDetails extends UsageChartPoint {
  downloadNormal: number;
  downloadRepair: number;
  uploadNormal: number;
  uploadRepair: number;
}

interface UsageChartPointTotals extends UsageChartPoint {
  download: number;
  upload: number;
  diskEfficiency: number;
}

type UsagePoint = UsageChartPointDetails | UsageChartPointTotals;

interface RawUsagePoint {
  period: string;
  downloadNormalBytes: number;
  downloadRepairBytes: number;
  uploadNormalBytes: number;
  uploadRepairBytes: number;
  diskUsageBytes: number;
}

type DiskUsageUnit = SizeUnit;

const LongTermPanel: FC = () => {
  const selectedNodes = useSelectedNodesStore((state) => state.selected);
  const [mode, setMode] = useState<Mode>("financial");
  const [financialView, setFinancialView] = useState<FinancialView>("monthly");
  const [financialGrouping, setFinancialGrouping] = useState<FinancialGrouping>("kind");
  const [dataSeriesMode, setDataSeriesMode] = useState<DataSeriesMode>("details");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [periods, setPeriods] = useState<Record<string, PaystubRecord[]>>({});
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const requestNodes = useMemo(() => {
    if (selectedNodes.length === 0 || selectedNodes.includes("All")) {
      return [] as string[];
    }
    return [...selectedNodes.filter((name) => name !== "All")].sort();
  }, [selectedNodes]);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const payload = await fetchPayoutPaystubs(requestNodes);
      setPeriods(payload.periods ?? {});
      setLastUpdated(new Date().toISOString());
    } catch (err) {
      console.warn("Failed to load paystub history", err);
      setError("Failed to load paystub history. Please try again.");
      setPeriods({});
    } finally {
      setIsLoading(false);
    }
  }, [requestNodes]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const chartData: ChartPoint[] = useMemo(() => {
    return Object.entries(periods)
      .map(([period, records]) => {
        const totals = records.reduce(
          (acc, record) => {
            acc.owed += record.owed ?? 0;
            acc.held += record.held ?? 0;
            acc.distributed += record.distributed ?? 0;
            acc.disk += record.compAtRest ?? 0;
            acc.download += record.compGet ?? 0;
            acc.repair += (record.compGetRepair ?? 0) + (record.compGetAudit ?? 0);
            return acc;
          },
          { owed: 0, held: 0, distributed: 0, disk: 0, download: 0, repair: 0 },
        );
        const downloadTotal = totals.download + totals.repair;
        return { period, ...totals, downloadTotal, total: totals.disk + downloadTotal } satisfies ChartPoint;
      })
      .sort((a, b) => a.period.localeCompare(b.period));
  }, [periods]);

  const financialChartData = useMemo(() => {
    if (financialView === "monthly") {
      return chartData;
    }

    let runningOwed = 0;
    let runningHeld = 0;
    let runningDistributed = 0;
    let runningDisk = 0;
    let runningDownload = 0;
    let runningRepair = 0;
    let runningDownloadTotal = 0;

    return chartData.map((point) => {
      runningOwed += point.owed;
      runningHeld += point.held;
      runningDistributed += point.distributed;
      runningDisk += point.disk;
      runningDownload += point.download;
      runningRepair += point.repair;
      runningDownloadTotal += point.downloadTotal;
      const runningTotal = runningDisk + runningDownloadTotal;

      return {
        period: point.period,
        owed: runningOwed,
        held: runningHeld,
        distributed: runningDistributed,
        disk: runningDisk,
        download: runningDownload,
        repair: runningRepair,
        downloadTotal: runningDownloadTotal,
        total: runningTotal,
      } satisfies ChartPoint;
    });
  }, [chartData, financialView]);

  const aggregateTotals = useMemo(
    () =>
      chartData.reduce(
        (acc, point) => {
          acc.owed += point.owed;
          acc.held += point.held;
          acc.distributed += point.distributed;
          acc.disk += point.disk;
          acc.download += point.download;
          acc.repair += point.repair;
          acc.downloadTotal += point.downloadTotal;
          acc.total += point.total;
          return acc;
        },
        { owed: 0, held: 0, distributed: 0, disk: 0, download: 0, repair: 0, downloadTotal: 0, total: 0 },
      ),
    [chartData],
  );

  const rawUsage = useMemo<RawUsagePoint[]>(() => {
    return Object.entries(periods)
      .map(([period, records]) => {
        const totals = records.reduce(
          (acc, record) => {
            acc.downloadNormalBytes += record.usageGet ?? 0;
            acc.downloadRepairBytes += (record.usageGetRepair ?? 0) + (record.usageGetAudit ?? 0);
            acc.uploadNormalBytes += record.usagePut ?? 0;
            acc.uploadRepairBytes += record.usagePutRepair ?? 0;
            acc.diskUsageBytes += record.usageAtRest ?? 0;
            return acc;
          },
          {
            downloadNormalBytes: 0,
            downloadRepairBytes: 0,
            uploadNormalBytes: 0,
            uploadRepairBytes: 0,
            diskUsageBytes: 0,
          },
        );

        return {
          period,
          downloadNormalBytes: totals.downloadNormalBytes,
          downloadRepairBytes: totals.downloadRepairBytes,
          uploadNormalBytes: totals.uploadNormalBytes,
          uploadRepairBytes: totals.uploadRepairBytes,
          diskUsageBytes: totals.diskUsageBytes,
        } satisfies RawUsagePoint;
      })
      .sort((a, b) => a.period.localeCompare(b.period));
  }, [periods]);

  const diskUnitInfo = useMemo(() => {
    const maxDisk = rawUsage.reduce((acc, item) => Math.max(acc, item.diskUsageBytes), 0);
    return pickSizeUnit(maxDisk);
  }, [rawUsage]);

  const transferUnitInfo = useMemo(() => {
    const maxTransfer = rawUsage.reduce((acc, item) => {
      if (dataSeriesMode === "totals") {
        const downloadTotal = item.downloadNormalBytes + item.downloadRepairBytes;
        const uploadTotal = item.uploadNormalBytes + item.uploadRepairBytes;
        return Math.max(acc, downloadTotal, uploadTotal);
      }
      return Math.max(
        acc,
        item.downloadNormalBytes,
        item.downloadRepairBytes,
        item.uploadNormalBytes,
        item.uploadRepairBytes,
      );
    }, 0);

    return pickSizeUnit(maxTransfer);
  }, [rawUsage, dataSeriesMode]);

  const usageChartData = useMemo<UsagePoint[]>(() => {
    return rawUsage.map((item): UsagePoint => {
      const diskUsage = item.diskUsageBytes / diskUnitInfo.factor;

      if (dataSeriesMode === "totals") {
        const downloadTotalBytes = item.downloadNormalBytes + item.downloadRepairBytes;
        const uploadTotalBytes = item.uploadNormalBytes + item.uploadRepairBytes;
        const diskEfficiency = item.diskUsageBytes > 0 ? (downloadTotalBytes / item.diskUsageBytes) * 100 : 0;

        return {
          period: item.period,
          download: downloadTotalBytes / transferUnitInfo.factor,
          upload: uploadTotalBytes / transferUnitInfo.factor,
          diskUsage,
          diskEfficiency,
        } satisfies UsageChartPointTotals;
      }

      return {
        period: item.period,
        downloadNormal: item.downloadNormalBytes / transferUnitInfo.factor,
        downloadRepair: item.downloadRepairBytes / transferUnitInfo.factor,
        uploadNormal: item.uploadNormalBytes / transferUnitInfo.factor,
        uploadRepair: item.uploadRepairBytes / transferUnitInfo.factor,
        diskUsage,
      } satisfies UsageChartPointDetails;
    });
  }, [rawUsage, diskUnitInfo.factor, transferUnitInfo.factor, dataSeriesMode]);

  const diskUsageUnit = diskUnitInfo.unit as DiskUsageUnit;
  const transferUnit = transferUnitInfo.unit;
  const diskUsageDisplayUnit = `${diskUsageUnit}m` as const;
  const transferDisplayUnit = transferUnit;

  const formatTransferVolume = (value: number) =>
    Number.isFinite(value)
      ? `${formatSizeValue(value)} ${transferDisplayUnit}`
      : `${formatSizeValue(0)} ${transferDisplayUnit}`;

  const renderFinancialView = () => {
    if (error) {
      return <p className="panel__error">{error}</p>;
    }

    if (isLoading && chartData.length === 0) {
      return <p className="panel__status">Loading paystub history…</p>;
    }

    if (!isLoading && chartData.length === 0) {
      return <p className="panel__empty">No paystub history available for the selected nodes.</p>;
    }

    const summaryRows = financialGrouping === "total"
      ? [
          { label: "Total Owed", value: aggregateTotals.owed },
          { label: "Total Held", value: aggregateTotals.held },
          { label: "Total Distributed", value: aggregateTotals.distributed },
        ]
      : [
          { label: "Total Disk", value: aggregateTotals.disk },
          { label: "Total Download", value: aggregateTotals.download },
          { label: "Total Repair", value: aggregateTotals.repair },
        ];

    return (
      <>
        <div className="longterm-summary">
          {summaryRows.map((row) => (
            <div key={row.label} className="longterm-summary__item">
              <span className="longterm-summary__label">{row.label}</span>
              <span className="longterm-summary__value">{formatAmount(row.value)}</span>
            </div>
          ))}
          <div className="longterm-summary__controls">
            <div className="longterm-summary__item longterm-summary__item--controls">
              <span className="longterm-summary__label">Grouping Mode</span>
              <div className="button-group button-group--micro">
                <button type="button" className={`button button--micro${financialGrouping === "total" ? " button--micro-active" : ""}`} onClick={() => setFinancialGrouping("total")}>
                  Total
                </button>
                <button type="button" className={`button button--micro${financialGrouping === "kind" ? " button--micro-active" : ""}`} onClick={() => setFinancialGrouping("kind")}>
                  By Kind
                </button>
              </div>
            </div>
            <div className="longterm-summary__item longterm-summary__item--controls">
              <span className="longterm-summary__label">View Mode</span>
              <div className="button-group button-group--micro">
                <button type="button" className={`button button--micro${financialView === "monthly" ? " button--micro-active" : ""}`} onClick={() => setFinancialView("monthly")}>
                  Monthly
                </button>
                <button type="button" className={`button button--micro${financialView === "accumulate" ? " button--micro-active" : ""}`} onClick={() => setFinancialView("accumulate")}>
                  Accumulate
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="longterm-chart">
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={financialChartData} margin={{ top: 10, right: 24, left: 8, bottom: 12 }}>
              <CartesianGrid strokeDasharray="4 8" stroke="rgba(148, 163, 184, 0.25)" />
              <XAxis dataKey="period" stroke="var(--color-text-muted)" />
              <YAxis
                stroke="var(--color-text-muted)"
                tickFormatter={(value: number) => formatAmount(value)}
                width={80}
              />
              <Tooltip content={<LongTermTooltip />} />
              <Legend verticalAlign="top" height={32} />
              {financialGrouping === "total" ? (
                <>
                  <Line type="monotone" dataKey="owed" name="Owed" stroke="#38bdf8" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line type="monotone" dataKey="held" name="Held" stroke="#f59e0b" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line type="monotone" dataKey="distributed" name="Distributed" stroke="#4ade80" strokeWidth={2} dot={false} isAnimationActive={false} />
                </>
              ) : (
                <>
                  <Line type="monotone" dataKey="disk" name="Disk" stroke="#55f4f7" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line type="monotone" dataKey="download" name="Download" stroke="rgba(56, 189, 248, 0.85)" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line type="monotone" dataKey="repair" name="Repair" stroke="rgba(248, 113, 113, 0.85)" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line type="monotone" dataKey="downloadTotal" name="Total Download" stroke="#9d4edd" strokeWidth={2} dot={false} strokeDasharray="6 6" isAnimationActive={false} />
                </>
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </>
    );
  };

  const renderDataView = () => {
    if (error) {
      return <p className="panel__error">{error}</p>;
    }

    if (isLoading && usageChartData.length === 0) {
      return <p className="panel__status">Loading usage history…</p>;
    }

    if (!isLoading && usageChartData.length === 0) {
      return <p className="panel__empty">No usage history available for the selected nodes.</p>;
    }

    const isTotalsView = dataSeriesMode === "totals";
    const labelMap: Record<string, string> = isTotalsView
      ? {
          download: "Download",
          upload: "Upload",
          diskUsage: "Disk Usage",
          diskEfficiency: "Download Ratio %",
        }
      : {
          downloadNormal: "Download Normal",
          downloadRepair: "Download Repair",
          uploadNormal: "Upload Normal",
          uploadRepair: "Upload Repair",
          diskUsage: "Disk Usage",
        };

    const formatDiskUsage = (value: number) =>
      Number.isFinite(value)
        ? `${formatSizeValue(value)} ${diskUsageDisplayUnit}`
        : `${formatSizeValue(0)} ${diskUsageDisplayUnit}`;

    const formatPercentage = (value: number) =>
      Number.isFinite(value)
        ? `${(value >= 10 ? value.toFixed(1) : value.toFixed(2))} %`
        : "0 %";

    const tooltipFormatters: Record<string, (value: number) => string> = {
      diskUsage: formatDiskUsage,
      ...(isTotalsView ? { diskEfficiency: formatPercentage } : {}),
    };

    return (
      <>
        <div className="longterm-summary">
          <div className="longterm-summary__controls">
            <div className="longterm-summary__item longterm-summary__item--controls">
              <span className="longterm-summary__label">Series Mode</span>
              <div className="button-group button-group--micro">
                <button
                  type="button"
                  className={`button button--micro${dataSeriesMode === "details" ? " button--micro-active" : ""}`}
                  onClick={() => setDataSeriesMode("details")}
                >
                  Details
                </button>
                <button
                  type="button"
                  className={`button button--micro${dataSeriesMode === "totals" ? " button--micro-active" : ""}`}
                  onClick={() => setDataSeriesMode("totals")}
                >
                  Totals
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="longterm-chart">
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={usageChartData} margin={{ top: 10, right: 24, left: 8, bottom: 12 }}>
              <CartesianGrid strokeDasharray="4 8" stroke="rgba(148, 163, 184, 0.25)" />
              <XAxis dataKey="period" stroke="var(--color-text-muted)" />
              <YAxis
                yAxisId="left"
                stroke="var(--color-text-muted)"
                tickFormatter={(value: number) => formatTransferVolume(value)}
                width={90}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                stroke="#55f4f7"
                tick={{ fill: "#55f4f7" }}
                tickFormatter={(value: number) => formatDiskUsage(value)}
                width={100}
              />
              {isTotalsView ? (
                <YAxis yAxisId="percent" hide domain={[0, 100]} />
              ) : null}
              <Tooltip
                content={
                  <UsageTooltip
                    labelMap={labelMap}
                    formatValue={formatTransferVolume}
                    valueFormatters={tooltipFormatters}
                  />
                }
              />
              <Legend verticalAlign="top" height={32} />
              {isTotalsView ? (
                <>
                  <Line yAxisId="left" type="monotone" dataKey="download" name="Download" stroke="rgba(56, 189, 248, 0.85)" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line yAxisId="left" type="monotone" dataKey="upload" name="Upload" stroke="rgba(52, 211, 153, 0.85)" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line yAxisId="right" type="monotone" dataKey="diskUsage" name="Disk Usage" stroke="#55f4f7" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line yAxisId="percent" type="monotone" dataKey="diskEfficiency" name="Disk Usage %" stroke="#9d4edd" strokeWidth={2} strokeDasharray="6 6" dot={false} isAnimationActive={false} />
                </>
              ) : (
                <>
                  <Line yAxisId="left" type="monotone" dataKey="downloadNormal" name="Download Normal" stroke="rgba(56, 189, 248, 0.85)" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line yAxisId="left" type="monotone" dataKey="downloadRepair" name="Download Repair" stroke="rgba(248, 113, 113, 0.85)" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line yAxisId="left" type="monotone" dataKey="uploadNormal" name="Upload Normal" stroke="rgba(52, 211, 153, 0.85)" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line yAxisId="left" type="monotone" dataKey="uploadRepair" name="Upload Repair" stroke="rgba(249, 115, 22, 0.85)" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line yAxisId="right" type="monotone" dataKey="diskUsage" name="Disk Usage" stroke="#55f4f7" strokeWidth={2} dot={false} isAnimationActive={false} />
                </>
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </>
    );
  };

  return (
    <section className="panel">
      <header className="panel__header">
        <div>
          <h2 className="panel__title">Long-Term Overview</h2>
          <PanelSubtitle selectedNodes={selectedNodes}>
            Historical payout data grouped by billing period.
          </PanelSubtitle>
        </div>
        <div className="panel__actions panel__actions--stacked">
          <button className="button" type="button" onClick={() => refresh()} disabled={isLoading}>
            {isLoading ? "Loading…" : "Refresh"}
          </button>
          <div className="button-group button-group--micro">
            <button type="button" className={`button button--micro${mode === "financial" ? " button--micro-active" : ""}`} onClick={() => setMode("financial")}>
              Financial
            </button>
            <button type="button" className={`button button--micro${mode === "data" ? " button--micro-active" : ""}`} onClick={() => setMode("data")}>
              Data
            </button>
          </div>
        </div>
      </header>

      <div className="panel__body">
        {lastUpdated ? (
          <p className="panel__status">Last updated {formatDateTime(lastUpdated)}</p>
        ) : null}

        {mode === "financial" ? renderFinancialView() : renderDataView()}
      </div>
    </section>
  );
};

export default LongTermPanel;
