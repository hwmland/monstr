import type { FC } from "react";
import { useEffect, useMemo, useState } from "react";
import usePanelVisibilityStore from "../../store/usePanelVisibility";
import { fetchIntervalTransfers } from "../../services/apiClient";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Cell, ReferenceLine } from "recharts";
import { formatSizeValue, pickSizeUnit, pickRateUnit, formatRateValue } from "../../utils/units";
import PanelSubtitle from "../PanelSubtitle";
import PanelHeader from "../PanelHeader";
import PanelControls from "../PanelControls";
import PanelControlsButton from "../PanelControlsButton";
import PanelControlsCombo from "../PanelControlsCombo";
import { use24hTime } from "../../utils/time";
import Legend from "../Legend";

type Mode = "size" | "count" | "speed";
type Range = "5m" | "1h" | "6h" | "30h" | "8d" | "30d" | "90d";

const RANGE_MAP: Record<Range, { intervalLength: string; numberOfIntervals: number }> = {
  "5m": { intervalLength: "10s", numberOfIntervals: 30 },
  "1h": { intervalLength: "2m", numberOfIntervals: 30 },
  "6h": { intervalLength: "10m", numberOfIntervals: 36 },
  "30h": { intervalLength: "1h", numberOfIntervals: 30 },
  "8d": { intervalLength: "6h", numberOfIntervals: 32 },
  "30d": { intervalLength: "1d", numberOfIntervals: 30 },
  "90d": { intervalLength: "3d", numberOfIntervals: 30 },
};

const LONG_RANGE_OPTIONS: Array<{ value: Range; label: string }> = [
  { value: "8d", label: "8d" },
  { value: "30d", label: "30d" },
  { value: "90d", label: "90d" },
];

interface AccumulatedTrafficPanelProps {
  selectedNodes: string[];
}

const LONG_RANGE_SET = new Set<Range>(["8d", "30d", "90d"]);

const formatDayMonth = (date: Date) => {
  const day = String(date.getDate()).padStart(2, "0");
  const month = String(date.getMonth() + 1).padStart(2, "0");
  return `${day}/${month}`;
};

const formatAxisLabel = (value: string, range: Range, use24h: boolean) => {
  try {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }
    if (LONG_RANGE_SET.has(range)) {
      return formatDayMonth(date);
    }
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: !use24h } as const);
  } catch {
    return value;
  }
};

const formatTooltipLabel = (value: string, range: Range, use24h: boolean) => {
  try {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }
    if (range === "8d") {
      const dayMonth = formatDayMonth(date);
      const time = date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: !use24h } as const);
      return `${dayMonth} ${time}`;
    }
    if (range === "30d" || range === "90d") {
      return formatDayMonth(date);
    }
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: !use24h } as const);
  } catch {
    return value;
  }
};

const AccumulatedTrafficTooltip: FC<{
  active?: boolean;
  payload?: unknown[];
  label?: string;
  mode: Mode;
  displayUnit: string;
  displayFactor: number;
  use24h: boolean;
  range: Range;
}> = ({ active, payload, label, mode, displayUnit, displayFactor, use24h, range }) => {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  const entries = payload as Array<{ name?: string; value?: number; color?: string; dataKey?: string }>;

  const formatValue = (value: number) => {
    if (!Number.isFinite(value)) {
      return "0";
    }
    if (mode === "size") {
      return `${formatSizeValue(value / (displayFactor || 1))} ${displayUnit}`;
    }
    if (mode === "speed") {
      return `${formatRateValue(value / (displayFactor || 1))} ${displayUnit}`;
    }
    return `${Math.round(value)} ops`;
  };

  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__label">
        {label ? `At ${formatTooltipLabel(label, range, use24h)}` : "Bucket"}
      </div>
      {entries.map((entry) => {
        const key = entry.dataKey ?? entry.name ?? "Series";
        const numeric = Number(entry.value ?? 0);
        return (
          <div key={String(key)} className="chart-tooltip__row">
            <span style={{ color: entry.color ?? "var(--color-text)" }}>{String(key)}:</span>
            <span>{formatValue(numeric)}</span>
          </div>
        );
      })}
    </div>
  );
};

const AccumulatedTrafficPanel: FC<AccumulatedTrafficPanelProps> = ({ selectedNodes }) => {
  const { isVisible } = usePanelVisibilityStore();
  const show = isVisible("accumulatedTraffic");
  if (!show) return null;
  const [mode, setMode] = useState<Mode>("speed");
  const [range, setRange] = useState<Range>("1h");
  const [layout, setLayout] = useState<'stacked' | 'grouped'>('stacked');
  const [data, setData] = useState<any[] | null>(null);
  const [startTime, setStartTime] = useState<string | null>(null);
  const [endTime, setEndTime] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hoverValue, setHoverValue] = useState<number | null>(null);
  const [hoverLabel, setHoverLabel] = useState<string | null>(null);
  const [hoverSeries, setHoverSeries] = useState<'dl' | 'ul' | null>(null);
  const [chartWidth, setChartWidth] = useState<number | null>(null);
  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const nodes = selectedNodes.includes("All") ? [] : selectedNodes;
      const mapping = RANGE_MAP[range];
      const res = await fetchIntervalTransfers(nodes, mapping.intervalLength, mapping.numberOfIntervals);
      setStartTime(res.startTime ?? null);
      setEndTime(res.endTime ?? null);
      setData(Array.isArray(res.buckets) ? res.buckets : []);
    } catch (err: any) {
      setError(err?.message ?? String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const refreshIntervalMs = range === "5m"
      ? 10_000
      : LONG_RANGE_SET.has(range)
        ? 300_000
        : 60_000;
    const id = setInterval(load, refreshIntervalMs);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedNodes, mode, range]);

  // track effective 24h/12h preference and update when settings change
  const [system24, setSystem24] = useState<boolean>(() => use24hTime());
  useEffect(() => {
    const handler = () => setSystem24(use24hTime());
    window.addEventListener('pref_time_24h_changed', handler as EventListener);
    return () => window.removeEventListener('pref_time_24h_changed', handler as EventListener);
  }, []);

  // Prepare data for stacked bar chart: group by bucketStart label
  const chartData = useMemo(() => {
    if (!data) return [];
    return data.map((b: any) => {
      // store parseable timestamp so the tickFormatter can reformat on each render
      const label = String(b.bucketStart);
      if (mode === "size") {
        const dl = (b.sizeDlSuccNor ?? 0) + (b.sizeDlSuccRep ?? 0);
        const ul = (b.sizeUlSuccNor ?? 0) + (b.sizeUlSuccRep ?? 0);
        return { label, dl, ul };
      }
      if (mode === "speed") {
        // compute bits per second from successful bytes and bucket length
        try {
          const bs = new Date(b.bucketStart);
          const be = new Date(b.bucketEnd);
          const seconds = Math.max(1, Math.floor((be.getTime() - bs.getTime()) / 1000));
          const dlBytes = (b.sizeDlSuccNor ?? 0) + (b.sizeDlSuccRep ?? 0);
          const ulBytes = (b.sizeUlSuccNor ?? 0) + (b.sizeUlSuccRep ?? 0);
          const dlBps = (dlBytes * 8) / seconds;
          const ulBps = (ulBytes * 8) / seconds;
          return { label, dl: dlBps, ul: ulBps };
        } catch {
          return { label, dl: 0, ul: 0 };
        }
      }
      const dl = (b.countDlSuccNor ?? 0) + (b.countDlSuccRep ?? 0);
      const ul = (b.countUlSuccNor ?? 0) + (b.countUlSuccRep ?? 0);
      return { label, dl, ul };
    });
  }, [data, mode]);

  // When in size mode, pick a common unit (based on the largest value across dl/ul)
  const { displayUnit, displayFactor } = useMemo(() => {
    if (mode === "size") {
      const maxBytes = (chartData || []).reduce((acc: number, row: any) => Math.max(acc, Number(row.dl || 0), Number(row.ul || 0)), 0);
      const unitInfo = pickSizeUnit(maxBytes || 0);
      return { displayUnit: unitInfo.unit, displayFactor: unitInfo.factor };
    }
    if (mode === "speed") {
      const maxBits = (chartData || []).reduce((acc: number, row: any) => Math.max(acc, Number(row.dl || 0), Number(row.ul || 0)), 0);
      const unitInfo = pickRateUnit(maxBits || 0);
      return { displayUnit: unitInfo.unit, displayFactor: unitInfo.factor };
    }
    return { displayUnit: "ops", displayFactor: 1 };
  }, [chartData, mode]);

  const formatHoverValue = (val: number) => {
    if (!Number.isFinite(val)) return String(val);
    if (mode === 'size') return `${formatSizeValue(Number(val) / (displayFactor || 1))} ${displayUnit}`;
    if (mode === 'speed') return `${formatRateValue(Number(val) / (displayFactor || 1))} ${displayUnit}`;
    return String(val);
  };

  const buildHoverFromPayload = (item: any) => {
    if (!item) return { value: null, label: null };
    const val = Number(item?.value ?? item?.payload?.value ?? item?.payload?.dl ?? item?.payload?.ul ?? 0);
    const seriesName = item?.name ?? item?.dataKey ?? (item?.payload && (item.payload.seriesName ?? item.payload.name)) ?? '';
    const formatted = formatHoverValue(val);
    return { value: Number.isFinite(val) ? val : null, label: seriesName ? `${seriesName}: ${formatted}` : formatted };
  };

  const buildHoverFromStack = (index: number | null) => {
    if (index == null || !chartData || !chartData[index]) return { value: null, label: null };
    const row = chartData[index] as any;
    const val = (Number(row.dl || 0) + Number(row.ul || 0));
    const formatted = formatHoverValue(val);
    return { value: Number.isFinite(val) ? val : null, label: `Total: ${formatted}` };
  };

  const computeHoverFromEvent = (e: any) => {
    try {
      if (layout === 'grouped' && e && Array.isArray(e.activePayload) && e.activePayload.length) {
        const targetKey = hoverSeries ?? e.activePayload[0]?.dataKey ?? null;
        const item = targetKey ? e.activePayload.find((entry: any) => entry?.dataKey === targetKey) ?? e.activePayload[0] : e.activePayload[0];
        return buildHoverFromPayload(item);
      }
      if (typeof e?.activeTooltipIndex === 'number') {
        return buildHoverFromStack(e.activeTooltipIndex);
      }
    } catch {
      // fallthrough to null
    }
    return { value: null, label: null };
  };

  useEffect(() => {
    if (layout !== 'grouped') {
      setHoverSeries(null);
    }
  }, [layout]);

  const bucketCount = chartData.length;

  const groupedBarMetrics = useMemo(() => {
    if (layout !== 'grouped' || !chartWidth || bucketCount === 0) {
      return { barSize: 8, barGap: 6 };
    }

    const marginRight = 12; // mirrors chart margin.right
    const effectiveWidth = Math.max(0, chartWidth - marginRight);
    const categoryWidth = effectiveWidth / bucketCount;
    const safeCategory = Number.isFinite(categoryWidth) ? categoryWidth : 0;
    const rawBar = (safeCategory * 0.7) / 2;
    const maxBar = Math.max(2, (safeCategory - 2) / 2);
    let barWidth = Math.round(rawBar);
    barWidth = Math.max(2, Math.min(40, barWidth));
    barWidth = Math.min(barWidth, Math.floor(maxBar));
    const gapRaw = safeCategory - barWidth * 2;
    const barGap = Math.max(2, Math.min(32, Math.round(Number.isFinite(gapRaw) ? gapRaw : 6)));

    return { barSize: barWidth, barGap };
  }, [layout, chartWidth, bucketCount]);

  const barSizingProps = layout === 'stacked'
    ? { stackId: 'a' as const }
    : { barSize: groupedBarMetrics.barSize, maxBarSize: groupedBarMetrics.barSize };

  const highlightIndex = useMemo(() => {
    if (range !== "30h" || !chartData || chartData.length < 25) return -1;
    // 24th bar from the right
    return chartData.length - 25;
  }, [chartData, range]);

  return (
    <section className="panel">
      <PanelHeader
        title="Accumulated Traffic"
        subtitle={<PanelSubtitle windowStart={startTime} windowEnd={endTime} selectedNodes={selectedNodes} />}
        onRefresh={load}
        isRefreshing={loading}
        controls={(
          <>
            <PanelControls
              ariaLabel="Layout"
              buttons={[
                <PanelControlsButton key="stack" active={layout === "stacked"} onClick={() => setLayout("stacked")} content="Stack" />,
                <PanelControlsButton key="group" active={layout === "grouped"} onClick={() => setLayout("grouped")} content="Grp" />,
              ]}
            />
            <PanelControls
              ariaLabel="Display mode"
              buttons={[
                <PanelControlsButton key="speed" active={mode === "speed"} onClick={() => setMode("speed")} content="Speed" />,
                <PanelControlsButton key="size" active={mode === "size"} onClick={() => setMode("size")} content="Size" />,
                <PanelControlsButton key="count" active={mode === "count"} onClick={() => setMode("count")} content="Count" />,
              ]}
            />
            <PanelControls
              ariaLabel="Time range"
              buttons={[
                <PanelControlsButton key="5m" active={range === "5m"} onClick={() => setRange("5m")} content="5m" />,
                <PanelControlsButton key="1h" active={range === "1h"} onClick={() => setRange("1h")} content="1h" />,
                <PanelControlsButton key="6h" active={range === "6h"} onClick={() => setRange("6h")} content="6h" />,
                <PanelControlsButton key="30h" active={range === "30h"} onClick={() => setRange("30h")} content="30h" />,
                <PanelControlsCombo key="long-range" options={LONG_RANGE_OPTIONS} activeValue={range} defaultValue="90d" onSelect={(value) => setRange(value as Range)}
                />,
              ]}
            />
          </>
        )}
      />

      <div className="panel__body">
        {error ? <p className="panel__error">{error}</p> : null}
        {!data || data.length === 0 ? (
          <p className="panel__empty">No transfer data for the selected window.</p>
        ) : (
          <>
            <div style={{ width: '100%', height: 320 }}>
              <ResponsiveContainer
                width="100%"
                height="100%"
                onResize={(width: number) => {
                  if (!Number.isFinite(width) || width <= 0) return;
                  setChartWidth((prev) => (prev === width ? prev : width));
                }}
              >
                <BarChart
                  data={chartData}
                  margin={{ top: 8, right: 12, left: 0, bottom: 4 }}
                  barGap={groupedBarMetrics.barGap}
                  onMouseMove={(e: any) => {
                    const result = computeHoverFromEvent(e);
                    setHoverValue(result.value);
                    setHoverLabel(result.label);
                  }}
                  onMouseLeave={() => {
                    setHoverSeries(null);
                    setHoverValue(null);
                    setHoverLabel(null);
                  }}
                >
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis
                  dataKey="label"
                  tick={{ fill: "var(--color-text-muted)", fontSize: 14 }}
                  tickFormatter={(v: any) => formatAxisLabel(String(v), range, system24)}
                  interval={'preserveStartEnd'}
                  angle={-45}
                  textAnchor="end"
                  height={56}
                />
                <YAxis tickFormatter={(v: number | string) => {
                  if (mode === 'size') return formatSizeValue(Number(v) / (displayFactor || 1));
                  if (mode === 'speed') return formatRateValue(Number(v) / (displayFactor || 1));
                  return String(v);
                }} label={{ value: mode === 'size' ? displayUnit : (mode === 'speed' ? displayUnit : 'ops'), angle: -90, position: 'insideLeft', fill: 'var(--color-text-muted)' }} />
                <Tooltip
                  content={(
                    <AccumulatedTrafficTooltip
                      mode={mode}
                      displayUnit={displayUnit}
                      displayFactor={displayFactor}
                      use24h={system24}
                      range={range}
                    />
                  )}
                  cursor={{ fill: "rgba(148, 163, 184, 0.05)" }}
                />
                <Bar
                  dataKey="dl"
                  {...barSizingProps}
                  fill="#10784A"
                  name="Download"
                  isAnimationActive={false}
                  onMouseMove={() => setHoverSeries((prev) => (prev === 'dl' ? prev : 'dl'))}
                  onMouseLeave={() => setHoverSeries((prev) => (prev === 'dl' ? null : prev))}
                >
                  {chartData.map((_: any, i: number) => (
                    <Cell key={`dl-${i}`} stroke={i === highlightIndex ? '#ef4444' : undefined} strokeWidth={i === highlightIndex ? 2 : undefined} />
                  ))}
                </Bar>
                <Bar
                  dataKey="ul"
                  {...barSizingProps}
                  fill="#34D399"
                  name="Upload"
                  isAnimationActive={false}
                  onMouseMove={() => setHoverSeries((prev) => (prev === 'ul' ? prev : 'ul'))}
                  onMouseLeave={() => setHoverSeries((prev) => (prev === 'ul' ? null : prev))}
                >
                  {chartData.map((_: any, i: number) => (
                    <Cell key={`ul-${i}`} stroke={i === highlightIndex ? '#ef4444' : undefined} strokeWidth={i === highlightIndex ? 2 : undefined} />
                  ))}
                </Bar>
                {layout === 'grouped' ? <></> : null}
                {hoverValue != null ? (
                  <ReferenceLine y={hoverValue} stroke="#9ca3af" strokeWidth={1} ifOverflow="extendDomain" label={hoverLabel ? { value: hoverLabel, position: 'insideBottomLeft', fill: '#ffffff' } : undefined} />
                ) : null}
                </BarChart>
              </ResponsiveContainer>
            </div>
            <Legend items={[{ label: 'Download', color: '#10784A' }, { label: 'Upload', color: '#34D399' }]} />
            </>
        )}
      </div>
    </section>
  );
};

export default AccumulatedTrafficPanel;
