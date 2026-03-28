import type { FC } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Area,
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";

import { fetchSatelliteUsage } from "../../services/apiClient";
import createRequestDeduper from "../../utils/requestDeduper";
import { COLOR_DOWNLOAD, COLOR_DOWNLOAD_FILL, COLOR_DOWNLOAD_REPAIR, COLOR_DL_AUDIT, COLOR_UPLOAD, COLOR_UPLOAD_FILL, COLOR_UPLOAD_REPAIR } from "../../constants/colors";
import usePanelVisibilityStore from "../../store/usePanelVisibility";
import { formatSizeValue, pickSizeUnit } from "../../utils/units";
import type { SatelliteUsageRecord } from "../../types";
import PanelHeader from "../PanelHeader";
import PanelSubtitle from "../PanelSubtitle";
import PanelControls, { getStoredSelection } from "../PanelControls";
import PanelControlsButton from "../PanelControlsButton";
import PanelControlsCheckbox from "../PanelControlsCheckbox";

interface BandwidthUsagePanelProps {
  selectedNodes: string[];
}

type PeriodMode = "month" | "30d" | "90d" | "1y";
type StackMode = "stack" | "grp";

const PERIOD_MODE_VALUES = ["month", "30d", "90d", "1y"] as const satisfies readonly PeriodMode[];
const STACK_MODE_VALUES = ["stack", "grp"] as const satisfies readonly StackMode[];
const BOOLEAN_OPTIONS = ["true", "false"] as const;

const PERIOD_LABELS: Record<PeriodMode, string> = {
  month: "Current month",
  "30d": "30d",
  "90d": "90d",
  "1y": "1y",
};

/** Number of raw daily periods to consolidate into one chart bucket. */
const BUCKET_SIZE: Record<PeriodMode, number> = {
  month: 1,
  "30d": 1,
  "90d": 3,
  "1y": 12,
};

const BY_KIND_KEY = "monstr.panel.BandwidthUsage.byKind";
const STACK_KEY = "monstr.panel.BandwidthUsage.stack";

interface RawPeriodData {
  ulUsage: number;
  ulRepair: number;
  dlUsage: number;
  dlRepair: number;
  dlAudit: number;
}

interface BandwidthChartPoint {
  label: string;
  period: string;
  // Per-period bar data (scaled to barUnit):
  upload: number;
  download: number;
  ulUsage: number;
  ulRepair: number;
  dlUsage: number;
  dlRepair: number;
  dlAudit: number;
  // Accumulated area data (scaled to accUnit):
  accUpload: number;
  accDownload: number;
}

const formatAxisLabel = (value: string): string => {
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleDateString([], { month: "short", day: "numeric" });
  } catch {
    return value;
  }
};

const BandwidthTooltip: FC<{
  active?: boolean;
  payload?: unknown[];
  label?: string;
  barUnit: string;
  accUnit: string;
  byKind: boolean;
}> = ({ active, payload, label, barUnit, accUnit, byKind }) => {
  if (!active || !payload || payload.length === 0) return null;

  const ACC_KEYS = new Set(["accUpload", "accDownload"]);

  const entries = payload as Array<{
    name?: string;
    value?: number;
    color?: string;
    dataKey?: string;
  }>;

  // Filter out zero-value entries for cleaner tooltips
  const visible = entries.filter((e) => Number(e.value ?? 0) !== 0);
  if (visible.length === 0 && !byKind) return null;

  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__label">{label}</div>
      {visible.map((entry) => {
        const key = String(entry.dataKey ?? entry.name ?? "");
        const value = Number(entry.value ?? 0);
        const unit = ACC_KEYS.has(key) ? accUnit : barUnit;
        const color = entry.color ?? "var(--color-text)";
        return (
          <div key={key} className="chart-tooltip__row">
            <span style={{ color }}>{entry.name ?? key}:</span>
            <span>{formatSizeValue(value)}&nbsp;{unit}</span>
          </div>
        );
      })}
    </div>
  );
};

const BandwidthUsagePanel: FC<BandwidthUsagePanelProps> = ({ selectedNodes }) => {
  const { isVisible } = usePanelVisibilityStore();
  const visible = isVisible("bandwidthUsage");

  const [periodMode, setPeriodMode] = useState<PeriodMode>(() =>
    getStoredSelection<PeriodMode>("monstr.panel.BandwidthUsage.period", PERIOD_MODE_VALUES, "30d"),
  );
  const [byKind, setByKind] = useState<boolean>(() =>
    getStoredSelection(BY_KIND_KEY, BOOLEAN_OPTIONS, "false") === "true",
  );
  const [stackMode, setStackMode] = useState<StackMode>(() =>
    getStoredSelection<StackMode>(STACK_KEY, STACK_MODE_VALUES, "stack"),
  );

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rawPeriods, setRawPeriods] = useState<Record<string, SatelliteUsageRecord[]>>({});
  const deduperRef = useRef(createRequestDeduper());

  const requestNodes = useMemo(() => {
    if (selectedNodes.length === 0 || selectedNodes.includes("All")) return [] as string[];
    return [...selectedNodes.filter((n) => n !== "All")].sort();
  }, [selectedNodes]);

  /** Number of calendar days to request from the backend for the current mode. */
  const numberOfPeriods = useMemo(() => {
    if (periodMode === "month") {
      // Request enough to cover from the start of the current month to today.
      // Add a small buffer so the start-of-month boundary is always included.
      const now = new Date();
      return now.getDate() + 2;
    }
    if (periodMode === "30d") return 30;
    if (periodMode === "90d") return 90;
    return 365; // "1y"
  }, [periodMode]);

  const refresh = useCallback(async () => {
    if (!visible) return;
    setIsLoading(true);
    setError(null);
    const deduper = deduperRef.current;
    if (deduper.isDuplicate([...requestNodes, `p:${periodMode}`], 1000)) {
      setIsLoading(false);
      return;
    }
    try {
      const response = await fetchSatelliteUsage(requestNodes, numberOfPeriods);
      setRawPeriods(response.periods);
    } catch (err) {
      console.warn("Failed to load satellite usage data", err);
      setError("Failed to load bandwidth data. Please try again.");
      setRawPeriods({});
    } finally {
      setIsLoading(false);
    }
  }, [visible, requestNodes, periodMode, numberOfPeriods]);

  useEffect(() => {
    if (!visible) return undefined;
    void refresh();
  }, [refresh, visible]);

  useEffect(() => {
    if (!visible) return undefined;
    const id = window.setInterval(() => {
      void refresh();
    }, 600_000);
    return () => window.clearInterval(id);
  }, [refresh, visible]);

  /** Aggregate all node + satellite records into a single value per period. */
  const aggregatedPeriods = useMemo<Record<string, RawPeriodData>>(() => {
    const result: Record<string, RawPeriodData> = {};
    for (const [period, records] of Object.entries(rawPeriods)) {
      let ulUsage = 0;
      let ulRepair = 0;
      let dlUsage = 0;
      let dlRepair = 0;
      let dlAudit = 0;
      for (const rec of records) {
        ulUsage += rec.ulUsage;
        ulRepair += rec.ulRepair;
        dlUsage += rec.dlUsage;
        dlRepair += rec.dlRepair;
        dlAudit += rec.dlAudit;
      }
      result[period] = { ulUsage, ulRepair, dlUsage, dlRepair, dlAudit };
    }
    return result;
  }, [rawPeriods]);

  const sortedPeriods = useMemo(() => Object.keys(aggregatedPeriods).sort(), [aggregatedPeriods]);

  /** For "month" mode filter to only the current-month periods. */
  const filteredPeriods = useMemo(() => {
    if (periodMode !== "month") return sortedPeriods;
    const now = new Date();
    const prefix = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
    return sortedPeriods.filter((p) => p.startsWith(prefix));
  }, [sortedPeriods, periodMode]);

  /** Group filtered periods into display buckets (3-day for 90d, 12-day for 1y). */
  const buckets = useMemo<string[][]>(() => {
    const size = BUCKET_SIZE[periodMode];
    if (size === 1) return filteredPeriods.map((p) => [p]);
    const result: string[][] = [];
    for (let i = 0; i < filteredPeriods.length; i += size) {
      result.push(filteredPeriods.slice(i, i + size));
    }
    return result;
  }, [filteredPeriods, periodMode]);

  /** Build scaled chart data and select appropriate units for each Y-axis. */
  const { chartData, barUnit, accUnit } = useMemo((): {
    chartData: BandwidthChartPoint[];
    barUnit: string;
    accUnit: string;
  } => {
    if (buckets.length === 0) return { chartData: [], barUnit: "B", accUnit: "B" };

    // Sum raw bytes per bucket (unscaled).
    const rawBuckets = buckets.map((bucket) => {
      let ulUsage = 0;
      let ulRepair = 0;
      let dlUsage = 0;
      let dlRepair = 0;
      let dlAudit = 0;
      for (const period of bucket) {
        const d = aggregatedPeriods[period];
        if (d) {
          ulUsage += d.ulUsage;
          ulRepair += d.ulRepair;
          dlUsage += d.dlUsage;
          dlRepair += d.dlRepair;
          dlAudit += d.dlAudit;
        }
      }
      const upload = ulUsage + ulRepair;
      const download = dlUsage + dlRepair + dlAudit;
      return { period: bucket[0], ulUsage, ulRepair, dlUsage, dlRepair, dlAudit, upload, download };
    });

    // Pick bar unit from the largest single-bucket value across all series.
    let maxBar = 0;
    for (const b of rawBuckets) {
      for (const v of [b.upload, b.download, b.ulUsage, b.ulRepair, b.dlUsage, b.dlRepair, b.dlAudit]) {
        if (v > maxBar) maxBar = v;
      }
    }
    const barUnitInfo = pickSizeUnit(maxBar || 1);
    const barFactor = barUnitInfo.factor;

    // Compute running accumulated sums.
    let runUpload = 0;
    let runDownload = 0;
    const withAcc = rawBuckets.map((b) => {
      runUpload += b.upload;
      runDownload += b.download;
      return { ...b, accUpload: runUpload, accDownload: runDownload };
    });

    // Pick acc unit from the final (largest) accumulated value.
    const maxAcc = Math.max(
      withAcc.length > 0 ? withAcc[withAcc.length - 1].accUpload : 0,
      withAcc.length > 0 ? withAcc[withAcc.length - 1].accDownload : 0,
    );
    const accUnitInfo = pickSizeUnit(maxAcc || 1);
    const accFactor = accUnitInfo.factor;

    const data: BandwidthChartPoint[] = withAcc.map((b) => ({
      label: formatAxisLabel(b.period),
      period: b.period,
      upload: b.upload / barFactor,
      download: b.download / barFactor,
      ulUsage: b.ulUsage / barFactor,
      ulRepair: b.ulRepair / barFactor,
      dlUsage: b.dlUsage / barFactor,
      dlRepair: b.dlRepair / barFactor,
      dlAudit: b.dlAudit / barFactor,
      accUpload: b.accUpload / accFactor,
      accDownload: b.accDownload / accFactor,
    }));

    return { chartData: data, barUnit: barUnitInfo.unit, accUnit: accUnitInfo.unit };
  }, [buckets, aggregatedPeriods]);

  /** Totals (over the filtered/displayed periods) and month-end predictions. */
  const { totalUpload, totalDownload, predictUpload, predictDownload } = useMemo(() => {
    // Totals over all displayed periods.
    let totalUpload = 0;
    let totalDownload = 0;
    for (const period of filteredPeriods) {
      const d = aggregatedPeriods[period];
      if (d) {
        totalUpload += d.ulUsage + d.ulRepair;
        totalDownload += d.dlUsage + d.dlRepair + d.dlAudit;
      }
    }

    // Month-end prediction using current-month daily data, excluding today.
    const now = new Date();
    const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
    const currentMonthPrefix = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
    const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();

    const monthEntries = Object.entries(aggregatedPeriods).filter(([p]) => p.startsWith(currentMonthPrefix));
    const excludeToday = monthEntries.filter(([p]) => p !== todayStr);
    // Fall back to all current-month data (including today) when today is the only entry.
    const usedEntries = excludeToday.length > 0 ? excludeToday : monthEntries;

    const periodCount = usedEntries.length;
    let sumU = 0;
    let sumD = 0;
    for (const [, d] of usedEntries) {
      sumU += d.ulUsage + d.ulRepair;
      sumD += d.dlUsage + d.dlRepair + d.dlAudit;
    }

    const predictUpload = periodCount > 0 ? (sumU / periodCount) * daysInMonth : 0;
    const predictDownload = periodCount > 0 ? (sumD / periodCount) * daysInMonth : 0;

    return { totalUpload, totalDownload, predictUpload, predictDownload };
  }, [filteredPeriods, aggregatedPeriods]);

  const totalAll = totalUpload + totalDownload;
  const predictAll = predictUpload + predictDownload;

  const formatTotal = (bytes: number): string => {
    const unitInfo = pickSizeUnit(Math.max(bytes, 1));
    return `${formatSizeValue(bytes / unitInfo.factor)} ${unitInfo.unit}`;
  };

  const handleByKindChange = (value: boolean) => {
    setByKind(value);
    try {
      localStorage.setItem(BY_KIND_KEY, value ? "true" : "false");
    } catch {
      // ignore
    }
  };

  const handleRefresh = () => {
    void refresh();
  };

  if (!visible) return null;

  const hasData = chartData.length > 0;

  return (
    <section className="panel">
      <PanelHeader
        title="Bandwidth Usage"
        subtitle={
          <PanelSubtitle selectedNodes={selectedNodes}>{PERIOD_LABELS[periodMode]}</PanelSubtitle>
        }
        onRefresh={handleRefresh}
        isRefreshing={isLoading}
        refreshLabels={{ idle: "Refresh", active: "Loading..." }}
        controls={
          <>
            <PanelControls
              ariaLabel="Bandwidth toggles"
              buttons={[
                <PanelControlsCheckbox
                  key="by-kind"
                  label="By Kind"
                  checked={byKind}
                  onChange={handleByKindChange}
                  ariaLabel="Toggle detailed kind view"
                />,
              ]}
            />
            <PanelControls
              ariaLabel="Bandwidth stack mode"
              storageKey={STACK_KEY}
              buttons={[
                <PanelControlsButton
                  key="stack"
                  type="button"
                  active={stackMode === "stack"}
                  onClick={() => setStackMode("stack")}
                  content="Stack"
                />,
                <PanelControlsButton
                  key="grp"
                  type="button"
                  active={stackMode === "grp"}
                  onClick={() => setStackMode("grp")}
                  content="Grp"
                />,
              ]}
            />
            <PanelControls
              ariaLabel="Bandwidth period"
              storageKey="monstr.panel.BandwidthUsage.period"
              buttons={PERIOD_MODE_VALUES.map((key) => (
                <PanelControlsButton
                  key={key}
                  type="button"
                  active={periodMode === key}
                  onClick={() => setPeriodMode(key)}
                  content={PERIOD_LABELS[key]}
                />
              ))}
            />
          </>
        }
      />

      <div className="panel__body">
        {error ? <p className="panel__error">{error}</p> : null}
        {!hasData && isLoading ? <p className="panel__status">Loading bandwidth data…</p> : null}
        {!hasData && !isLoading ? (
          <p className="panel__empty">No bandwidth data for the selected period.</p>
        ) : null}

        {hasData ? (
          <>
            {/* Totals + predictions summary */}
            <div className="longterm-summary">
              <div className="longterm-summary__item">
                <span className="longterm-summary__label">Upload</span>
                <span className="longterm-summary__value">{formatTotal(totalUpload)}</span>
              </div>
              <div className="longterm-summary__item">
                <span className="longterm-summary__label">Download</span>
                <span className="longterm-summary__value">{formatTotal(totalDownload)}</span>
              </div>
              <div className="longterm-summary__item" style={{ borderColor: "rgba(148, 163, 184, 0.4)" }}>
                <span className="longterm-summary__label">Total</span>
                <span className="longterm-summary__value">{formatTotal(totalAll)}</span>
              </div>
              <div className="longterm-summary__item">
                <span className="longterm-summary__label">Est.&nbsp;Upload&nbsp;/ Month</span>
                <span className="longterm-summary__value">{formatTotal(predictUpload)}</span>
              </div>
              <div className="longterm-summary__item">
                <span className="longterm-summary__label">Est.&nbsp;Download&nbsp;/ Month</span>
                <span className="longterm-summary__value">{formatTotal(predictDownload)}</span>
              </div>
              <div className="longterm-summary__item" style={{ borderColor: "rgba(148, 163, 184, 0.4)" }}>
                <span className="longterm-summary__label">Est.&nbsp;Total&nbsp;/ Month</span>
                <span className="longterm-summary__value">{formatTotal(predictAll)}</span>
              </div>
            </div>

            {/* Chart */}
            <div style={{ width: "100%", height: 360 }}>
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData} margin={{ top: 8, right: 60, bottom: 4, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                  <XAxis
                    dataKey="label"
                    tick={{ fill: "var(--color-text-muted)", fontSize: 12 }}
                  />
                  <YAxis
                    yAxisId="bars"
                    tickFormatter={(v: number) => formatSizeValue(v)}
                    tick={{ fill: "var(--color-text-muted)", fontSize: 12 }}
                    label={{
                      value: barUnit,
                      angle: -90,
                      position: "insideLeft",
                      fill: "var(--color-text-muted)",
                      offset: 10,
                    }}
                  />
                  <YAxis
                    yAxisId="acc"
                    orientation="right"
                    tickFormatter={(v: number) => formatSizeValue(v)}
                    tick={{ fill: "var(--color-text-muted)", fontSize: 12 }}
                    label={{
                      value: accUnit,
                      angle: 90,
                      position: "insideRight",
                      fill: "var(--color-text-muted)",
                      offset: 10,
                    }}
                  />
                  <RechartsTooltip
                    content={
                      <BandwidthTooltip barUnit={barUnit} accUnit={accUnit} byKind={byKind} />
                    }
                  />
                  <Legend />

                  {/*
                    Bars: upload series rendered BEFORE download series so that
                    when stacked, download sits visually on top of upload.
                  */}
                  {byKind ? (
                    <>
                      <Bar
                        yAxisId="bars"
                        dataKey="ulUsage"
                        name="UL Usage"
                        stackId={stackMode === "stack" ? "bw" : "ul"}
                        fill={COLOR_UPLOAD}
                        isAnimationActive={false}
                      />
                      <Bar
                        yAxisId="bars"
                        dataKey="ulRepair"
                        name="UL Repair"
                        stackId={stackMode === "stack" ? "bw" : "ul"}
                        fill={COLOR_UPLOAD_REPAIR}
                        isAnimationActive={false}
                      />
                      <Bar
                        yAxisId="bars"
                        dataKey="dlUsage"
                        name="DL Usage"
                        stackId={stackMode === "stack" ? "bw" : "dl"}
                        fill={COLOR_DOWNLOAD}
                        isAnimationActive={false}
                      />
                      <Bar
                        yAxisId="bars"
                        dataKey="dlRepair"
                        name="DL Repair"
                        stackId={stackMode === "stack" ? "bw" : "dl"}
                        fill={COLOR_DOWNLOAD_REPAIR}
                        isAnimationActive={false}
                      />
                      <Bar
                        yAxisId="bars"
                        dataKey="dlAudit"
                        name="DL Audit"
                        stackId={stackMode === "stack" ? "bw" : "dl"}
                        fill={COLOR_DL_AUDIT}
                        isAnimationActive={false}
                      />
                    </>
                  ) : (
                    <>
                      <Bar
                        yAxisId="bars"
                        dataKey="upload"
                        name="Upload"
                        stackId={stackMode === "stack" ? "bw" : undefined}
                        fill={COLOR_UPLOAD}
                        isAnimationActive={false}
                      />
                      <Bar
                        yAxisId="bars"
                        dataKey="download"
                        name="Download"
                        stackId={stackMode === "stack" ? "bw" : undefined}
                        fill={COLOR_DOWNLOAD}
                        isAnimationActive={false}
                      />
                    </>
                  )}

                  {/* Accumulated totals as filled areas on the right Y-axis */}
                  <Area
                    yAxisId="acc"
                    type="monotone"
                    dataKey="accUpload"
                    name="Acc. Upload"
                    stackId={stackMode === "stack" ? "acc" : undefined}
                    stroke={COLOR_UPLOAD}
                    fill={COLOR_UPLOAD_FILL}
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                  <Area
                    yAxisId="acc"
                    type="monotone"
                    dataKey="accDownload"
                    name="Acc. Download"
                    stackId={stackMode === "stack" ? "acc" : undefined}
                    stroke={COLOR_DOWNLOAD}
                    fill={COLOR_DOWNLOAD_FILL}
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </>
        ) : null}
      </div>
    </section>
  );
};

export default BandwidthUsagePanel;
