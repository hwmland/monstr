import type { FC } from "react";
import { useEffect, useMemo, useState } from "react";
import usePanelVisibilityStore from "../store/usePanelVisibility";
import { fetchIntervalTransfers } from "../services/apiClient";
import { formatWindowTime } from "../utils/time";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatSizeValue, pickSizeUnit, pickRateUnit, formatRateValue } from "../utils/units";
import Legend from "./Legend";

type Mode = "size" | "count" | "speed";
type Range = "5m" | "1h" | "6h" | "25h";

const RANGE_MAP: Record<Range, { intervalLength: string; numberOfIntervals: number }> = {
  "5m": { intervalLength: "10s", numberOfIntervals: 30 },
  "1h": { intervalLength: "2m", numberOfIntervals: 30 },
  "6h": { intervalLength: "10m", numberOfIntervals: 36 },
  "25h": { intervalLength: "1h", numberOfIntervals: 25 },
};

interface AccumulatedTrafficPanelProps {
  selectedNodes: string[];
}

const AccumulatedTrafficPanel: FC<AccumulatedTrafficPanelProps> = ({ selectedNodes }) => {
  const { isVisible } = usePanelVisibilityStore();
  const show = isVisible("accumulatedTraffic");
  if (!show) return null;
  const [mode, setMode] = useState<Mode>("size");
  const [range, setRange] = useState<Range>("1h");
  const [data, setData] = useState<any[] | null>(null);
  const [startTime, setStartTime] = useState<string | null>(null);
  const [endTime, setEndTime] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    const refreshIntervalMs = range === "5m" ? 10_000 : 60_000;
    const id = setInterval(load, refreshIntervalMs);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedNodes, mode, range]);

  const windowStart = formatWindowTime(startTime ? String(startTime) : null);
  const windowEnd = formatWindowTime(endTime ? String(endTime) : null);
  const nodesLabel = selectedNodes.length === 0 || selectedNodes.includes("All") ? "All nodes" : `Nodes: ${selectedNodes.join(", ")}`;

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

  return (
    <section className="panel">
      <header className="panel__header">
        <div>
          <h2 className="panel__title">Accumulated Traffic</h2>
          <p className="panel__subtitle">Window: {windowStart} – {windowEnd} • {nodesLabel}</p>
        </div>
        <div className="panel__actions panel__actions--stacked">
          <button className="button" type="button" onClick={load} disabled={loading}>{loading ? "Loading…" : "Refresh"}</button>
          <div className="panel-controls">
            <div className="panel-controls__left">
              <div className="button-group button-group--micro">
                <button type="button" className={`button button--micro${mode === "size" ? " button--micro-active" : ""}`} onClick={() => setMode("size")}>Size</button>
                <button type="button" className={`button button--micro${mode === "speed" ? " button--micro-active" : ""}`} onClick={() => setMode("speed")}>Speed</button>
                <button type="button" className={`button button--micro${mode === "count" ? " button--micro-active" : ""}`} onClick={() => setMode("count")}>Count</button>
              </div>
            </div>
            <div className="panel-controls__right">
              <div className="button-group button-group--micro">
                <button type="button" className={`button button--micro${range === "5m" ? " button--micro-active" : ""}`} onClick={() => setRange("5m")}>5m</button>
                <button type="button" className={`button button--micro${range === "1h" ? " button--micro-active" : ""}`} onClick={() => setRange("1h")}>1h</button>
                <button type="button" className={`button button--micro${range === "6h" ? " button--micro-active" : ""}`} onClick={() => setRange("6h")}>6h</button>
                <button type="button" className={`button button--micro${range === "25h" ? " button--micro-active" : ""}`} onClick={() => setRange("25h")}>25h</button>
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="panel__body">
        {error ? <p className="panel__error">{error}</p> : null}
        {!data || data.length === 0 ? (
          <p className="panel__empty">No transfer data for the selected window.</p>
        ) : (
          <>
            <div style={{ width: '100%', height: 320 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis
                  dataKey="label"
                  tick={{ fill: "var(--color-text-muted)", fontSize: 12 }}
                  tickFormatter={(v: any) => {
                    try {
                      const d = new Date(String(v));
                      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                    } catch {
                      return String(v);
                    }
                  }}
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
                <Tooltip formatter={(v: number | string) => {
                  if (mode === 'size') return `${formatSizeValue(Number(v) / (displayFactor || 1))} ${displayUnit}`;
                  if (mode === 'speed') return `${formatRateValue(Number(v) / (displayFactor || 1))} ${displayUnit}`;
                  return String(v);
                }} />
                <Bar dataKey="dl" stackId="a" fill="#10784A" name="Download" isAnimationActive={false} />
                <Bar dataKey="ul" stackId="a" fill="#34D399" name="Upload" isAnimationActive={false} />
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
