import type { FC } from "react";
import { useEffect, useMemo, useState } from "react";
import usePanelVisibilityStore from "../store/usePanelVisibility";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { fetchDataDistribution } from "../services/apiClient";
import Legend from "./Legend";
import { formatSizeValue, pickSizeUnit } from "../utils/units";
import { formatWindowTime } from "../utils/time";

type Mode = "size" | "count" | "sizePercent" | "countPercent";

interface DataSizeDistributionPanelProps {
  selectedNodes: string[];
}

const CHART_HEIGHT = 270;

const DataSizeDistributionPanel: FC<DataSizeDistributionPanelProps> = ({ selectedNodes }) => {
  const { isVisible } = usePanelVisibilityStore();
  if (!isVisible("dataDistribution")) {
    return null;
  }
  const [mode, setMode] = useState<Mode>("size");
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchDataDistribution(selectedNodes);
      setData(res);
    } catch (err: any) {
      setError(err?.message ?? String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedNodes]);

  const windowStart = formatWindowTime(data?.startTime ?? null);
  const windowEnd = formatWindowTime(data?.endTime ?? null);
  const nodesLabel = selectedNodes.length === 0 ? "All nodes" : `Nodes: ${selectedNodes.join(", ")}`;

  const { downloadData, uploadData, downloadDataPct, uploadDataPct, sizeUnitDl, sizeUnitDlFactor, sizeUnitUl, sizeUnitUlFactor } = useMemo(() => {
    const items = Array.isArray(data?.distribution) ? data.distribution : [];
    // Desired ordering and labels for the size classes
    const SIZE_ORDER = ["1K", "4K", "16K", "64K", "256K", "1M", "BIG"];
    const SIZE_LABELS: Record<string, string> = {
      "1K": "< 1KB",
      "4K": "< 4KB",
      "16K": "< 16KB",
      "64K": "< 64KB",
      "256K": "< 256KB",
      "1M": "< 1MB",
      "BIG": "> 1MB",
    };

    // Sort items according to SIZE_ORDER; unknown classes go to the end in their original order
    const normalizedItems = items.slice();
    const orderIndex = (sc: string | undefined) => {
      if (!sc) return SIZE_ORDER.length + 1;
      const key = String(sc).toUpperCase();
      const idx = SIZE_ORDER.indexOf(key);
      return idx === -1 ? SIZE_ORDER.length + 1 : idx;
    };
    normalizedItems.sort((a: any, b: any) => orderIndex(a.sizeClass) - orderIndex(b.sizeClass));

    // build arrays for DL and UL with stacked series: normal-success, repair-success, normal-fail, repair-fail
  const dl = normalizedItems.map((it: any) => {
      const raw = String(it.sizeClass ?? "").toUpperCase();
      const label = SIZE_LABELS[raw] ?? it.sizeClass ?? String(raw);
      return {
        sizeClass: label,
        downloadNormalSuccess: it.countDlSuccNor ?? 0,
        downloadRepairSuccess: it.countDlSuccRep ?? 0,
        downloadNormalFail: it.countDlFailNor ?? 0,
        downloadRepairFail: it.countDlFailRep ?? 0,
        downloadNormalSize: it.sizeDlSuccNor ?? 0,
        downloadRepairSize: it.sizeDlSuccRep ?? 0,
        downloadNormalFailSize: it.sizeDlFailNor ?? 0,
        downloadRepairFailSize: it.sizeDlFailRep ?? 0,
      };
    });

    const ul = normalizedItems.map((it: any) => {
      const raw = String(it.sizeClass ?? "").toUpperCase();
      const label = SIZE_LABELS[raw] ?? it.sizeClass ?? String(raw);
      return {
        sizeClass: label,
        uploadNormalSuccess: it.countUlSuccNor ?? 0,
        uploadRepairSuccess: it.countUlSuccRep ?? 0,
        uploadNormalFail: it.countUlFailNor ?? 0,
        uploadRepairFail: it.countUlFailRep ?? 0,
        uploadNormalSize: it.sizeUlSuccNor ?? 0,
        uploadRepairSize: it.sizeUlSuccRep ?? 0,
        uploadNormalFailSize: it.sizeUlFailNor ?? 0,
        uploadRepairFailSize: it.sizeUlFailRep ?? 0,
      };
    });

    // Totals for percent modes
    const totalSizeDl = items.reduce((acc: number, it: any) => {
      return acc + (it.sizeDlSuccNor ?? 0) + (it.sizeDlSuccRep ?? 0) + (it.sizeDlFailNor ?? 0) + (it.sizeDlFailRep ?? 0);
    }, 0);
    const totalCountDl = items.reduce((acc: number, it: any) => {
      return acc + (it.countDlSuccNor ?? 0) + (it.countDlSuccRep ?? 0) + (it.countDlFailNor ?? 0) + (it.countDlFailRep ?? 0);
    }, 0);

    const totalSizeUl = items.reduce((acc: number, it: any) => {
      return acc + (it.sizeUlSuccNor ?? 0) + (it.sizeUlSuccRep ?? 0) + (it.sizeUlFailNor ?? 0) + (it.sizeUlFailRep ?? 0);
    }, 0);
    const totalCountUl = items.reduce((acc: number, it: any) => {
      return acc + (it.countUlSuccNor ?? 0) + (it.countUlSuccRep ?? 0) + (it.countUlFailNor ?? 0) + (it.countUlFailRep ?? 0);
    }, 0);

    // percent arrays (0-100)
    const dlPct = normalizedItems.map((it: any) => {
      const safeTotalSize = totalSizeDl || 1;
      const safeTotalCount = totalCountDl || 1;
      return {
        sizeClass: SIZE_LABELS[String(it.sizeClass ?? "").toUpperCase()] ?? it.sizeClass ?? String(it.sizeClass),
        downloadNormalSizePct: (it.sizeDlSuccNor ?? 0) / safeTotalSize * 100,
        downloadRepairSizePct: (it.sizeDlSuccRep ?? 0) / safeTotalSize * 100,
        downloadNormalFailSizePct: (it.sizeDlFailNor ?? 0) / safeTotalSize * 100,
        downloadRepairFailSizePct: (it.sizeDlFailRep ?? 0) / safeTotalSize * 100,
        downloadNormalSuccessPct: (it.countDlSuccNor ?? 0) / safeTotalCount * 100,
        downloadRepairSuccessPct: (it.countDlSuccRep ?? 0) / safeTotalCount * 100,
        downloadNormalFailPct: (it.countDlFailNor ?? 0) / safeTotalCount * 100,
        downloadRepairFailPct: (it.countDlFailRep ?? 0) / safeTotalCount * 100,
      };
    });

    const ulPct = normalizedItems.map((it: any) => {
      const safeTotalSize = totalSizeUl || 1;
      const safeTotalCount = totalCountUl || 1;
      return {
        sizeClass: SIZE_LABELS[String(it.sizeClass ?? "").toUpperCase()] ?? it.sizeClass ?? String(it.sizeClass),
        uploadNormalSizePct: (it.sizeUlSuccNor ?? 0) / safeTotalSize * 100,
        uploadRepairSizePct: (it.sizeUlSuccRep ?? 0) / safeTotalSize * 100,
        uploadNormalFailSizePct: (it.sizeUlFailNor ?? 0) / safeTotalSize * 100,
        uploadRepairFailSizePct: (it.sizeUlFailRep ?? 0) / safeTotalSize * 100,
        uploadNormalSuccessPct: (it.countUlSuccNor ?? 0) / safeTotalCount * 100,
        uploadRepairSuccessPct: (it.countUlSuccRep ?? 0) / safeTotalCount * 100,
        uploadNormalFailPct: (it.countUlFailNor ?? 0) / safeTotalCount * 100,
        uploadRepairFailPct: (it.countUlFailRep ?? 0) / safeTotalCount * 100,
      };
    });

    const maxBytesDl = items.reduce((acc: number, it: any) => {
      const total = (it.sizeDlSuccNor ?? 0) + (it.sizeDlSuccRep ?? 0) + (it.sizeDlFailNor ?? 0) + (it.sizeDlFailRep ?? 0);
      return Math.max(acc, total);
    }, 0);

    const maxBytesUl = items.reduce((acc: number, it: any) => {
      const total = (it.sizeUlSuccNor ?? 0) + (it.sizeUlSuccRep ?? 0) + (it.sizeUlFailNor ?? 0) + (it.sizeUlFailRep ?? 0);
      return Math.max(acc, total);
    }, 0);

    const unitDl = pickSizeUnit(maxBytesDl);
    const unitUl = pickSizeUnit(maxBytesUl);

    return {
      downloadData: dl,
      uploadData: ul,
      downloadDataPct: dlPct,
      uploadDataPct: ulPct,
      sizeUnitDl: unitDl.unit,
      sizeUnitDlFactor: unitDl.factor,
      sizeUnitUl: unitUl.unit,
      sizeUnitUlFactor: unitUl.factor,
    };
  }, [data, mode]);

  const isPercentMode = mode === 'sizePercent' || mode === 'countPercent';
  const chartDownload = isPercentMode ? downloadDataPct : downloadData;
  const chartUpload = isPercentMode ? uploadDataPct : uploadData;

  const renderTooltipPercent = (value: any, name?: string) => {
    const numeric = Number(value) || 0;
    const formattedValue = `${numeric.toFixed(2)} %`;
    const formattedName = legendFormatter(String(name ?? ""));
    return [formattedValue, formattedName];
  };

  const renderTooltipSize = (value: any, factor: number, unit: string, name?: string) => {
    const numeric = Number(value) || 0;
    const scaled = numeric / (factor || 1);
    const formattedValue = `${formatSizeValue(scaled)} ${unit}`;
    const formattedName = legendFormatter(String(name ?? ""));
    return [formattedValue, formattedName];
  };

  const renderTooltipCount = (value: any, name?: string) => {
    const formattedValue = `${Number(value).toFixed(0)} ops`;
    const formattedName = legendFormatter(String(name ?? ""));
    return [formattedValue, formattedName];
  };

  const legendFormatter = (value: string) => {
    // Normalize keys such as downloadNormalSize, uploadRepairFail, downloadNormalFailSize, downloadNormalSuccess, etc.
    const key = String(value || "");
    const isFail = /fail/i.test(key);
    const isRepair = /repair/i.test(key);
    const isNormal = /normal/i.test(key);

    if (isFail && isRepair) return "Fail - Repair";
    if (isFail && isNormal) return "Fail - Normal";
    if (isRepair) return "Repair";
    if (isNormal) return "Normal";
    // Fallback: return a cleaned version
    return key.replace(/(download|upload)/i, "").replace(/(Size|Success|Fail|Nor|Rep)/gi, match => {
      return match.toLowerCase() === 'nor' ? 'normal' : match;
    }).replace(/([A-Z])/g, ' $1').trim();
  };

  return (
    <section className="panel">
      <header className="panel__header">
        <div>
          <h2 className="panel__title">Data Size Distribution</h2>
          <p className="panel__subtitle">Window: {windowStart} – {windowEnd} • {nodesLabel}</p>
        </div>
        <div className="panel__actions panel__actions--stacked">
          <button className="button" type="button" onClick={load} disabled={loading}>{loading ? "Loading…" : "Refresh"}</button>
          <div className="button-group button-group--micro">
            <button type="button" className={`button button--micro${mode === "size" ? " button--micro-active" : ""}`} onClick={() => setMode("size")}>Size</button>
            <button type="button" className={`button button--micro${mode === "count" ? " button--micro-active" : ""}`} onClick={() => setMode("count")}>Count</button>
            <button type="button" className={`button button--micro${mode === "sizePercent" ? " button--micro-active" : ""}`} onClick={() => setMode("sizePercent")}>Size %</button>
            <button type="button" className={`button button--micro${mode === "countPercent" ? " button--micro-active" : ""}`} onClick={() => setMode("countPercent")}>Count %</button>
          </div>
        </div>
      </header>

      <div className="panel__body">
        {error ? <p className="panel__error">{error}</p> : null}

        <div style={{ display: "flex", gap: 12 }}>
          <div style={{ flex: 1 }}>
            <h3 style={{ marginBottom: 8 }}>Download</h3>
            <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
              <BarChart data={chartDownload} barGap={6} barCategoryGap="20%" margin={{ bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis dataKey="sizeClass" tick={{ fill: "var(--color-text-muted)", fontSize: 13 }} angle={-45} textAnchor="end" height={40} />
                <YAxis
                  width={60}
                  tick={{ fill: "var(--color-text-muted)", fontSize: 13 }}
                  tickFormatter={(v: any) => {
                    if (mode === 'size') return formatSizeValue(Number(v) / (sizeUnitDlFactor || 1));
                    if (mode === 'sizePercent' || mode === 'countPercent') return Number(v).toFixed(1);
                    return Number(v).toFixed(0);
                  }}
                  label={{ value: mode === 'size' ? sizeUnitDl : (mode === 'sizePercent' || mode === 'countPercent' ? '%' : 'ops'), angle: -90, position: 'insideLeft', fill: 'var(--color-text-muted)' }}
                />
                <Tooltip formatter={(v: any, name: string) => {
                  if (mode === 'size') return renderTooltipSize(v, sizeUnitDlFactor, sizeUnitDl, name);
                  if (mode === 'sizePercent' || mode === 'countPercent') return renderTooltipPercent(v, name);
                  return renderTooltipCount(v, name);
                }} cursor={{ fill: "rgba(148, 163, 184, 0.05)" }} />
                
                <Bar dataKey={mode === "size" ? "downloadNormalSize" : mode === "count" ? "downloadNormalSuccess" : mode === "sizePercent" ? "downloadNormalSizePct" : "downloadNormalSuccessPct"} stackId="dl" fill="#10784A" isAnimationActive={false} />
                <Bar dataKey={mode === "size" ? "downloadRepairSize" : mode === "count" ? "downloadRepairSuccess" : mode === "sizePercent" ? "downloadRepairSizePct" : "downloadRepairSuccessPct"} stackId="dl" fill="#34D399" isAnimationActive={false} />
                <Bar dataKey={mode === "size" ? "downloadNormalFailSize" : mode === "count" ? "downloadNormalFail" : mode === "sizePercent" ? "downloadNormalFailSizePct" : "downloadNormalFailPct"} stackId="dl" fill="#EF4444" isAnimationActive={false} />
                <Bar dataKey={mode === "size" ? "downloadRepairFailSize" : mode === "count" ? "downloadRepairFail" : mode === "sizePercent" ? "downloadRepairFailSizePct" : "downloadRepairFailPct"} stackId="dl" fill="#F97316" isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div style={{ flex: 1 }}>
            <h3 style={{ marginBottom: 8 }}>Upload</h3>
            <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
              <BarChart data={chartUpload} barGap={6} barCategoryGap="20%" margin={{ bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis dataKey="sizeClass" tick={{ fill: "var(--color-text-muted)", fontSize: 13 }} angle={-45} textAnchor="end" height={40} />
                <YAxis
                  width={60}
                  tick={{ fill: "var(--color-text-muted)", fontSize: 13 }}
                  tickFormatter={(v: any) => {
                    if (mode === 'size') return formatSizeValue(Number(v) / (sizeUnitUlFactor || 1));
                    if (mode === 'sizePercent' || mode === 'countPercent') return Number(v).toFixed(1);
                    return Number(v).toFixed(0);
                  }}
                  label={{ value: mode === 'size' ? sizeUnitUl : (mode === 'sizePercent' || mode === 'countPercent' ? '%' : 'ops'), angle: -90, position: 'insideLeft', fill: 'var(--color-text-muted)' }}
                />
                <Tooltip formatter={(v: any, name: string) => {
                  if (mode === 'size') return renderTooltipSize(v, sizeUnitUlFactor, sizeUnitUl, name);
                  if (mode === 'sizePercent' || mode === 'countPercent') return renderTooltipPercent(v, name);
                  return renderTooltipCount(v, name);
                }} cursor={{ fill: "rgba(148, 163, 184, 0.05)" }} />
                
                <Bar dataKey={mode === "size" ? "uploadNormalSize" : mode === "count" ? "uploadNormalSuccess" : mode === "sizePercent" ? "uploadNormalSizePct" : "uploadNormalSuccessPct"} stackId="ul" fill="#10784A" isAnimationActive={false} />
                <Bar dataKey={mode === "size" ? "uploadRepairSize" : mode === "count" ? "uploadRepairSuccess" : mode === "sizePercent" ? "uploadRepairSizePct" : "uploadRepairSuccessPct"} stackId="ul" fill="#34D399" isAnimationActive={false} />
                <Bar dataKey={mode === "size" ? "uploadNormalFailSize" : mode === "count" ? "uploadNormalFail" : mode === "sizePercent" ? "uploadNormalFailSizePct" : "uploadNormalFailPct"} stackId="ul" fill="#EF4444" isAnimationActive={false} />
                <Bar dataKey={mode === "size" ? "uploadRepairFailSize" : mode === "count" ? "uploadRepairFail" : mode === "sizePercent" ? "uploadRepairFailSizePct" : "uploadRepairFailPct"} stackId="ul" fill="#F97316" isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        {/* Shared legend placed under the charts */}
        <Legend items={[
          { label: 'Normal', color: '#10784A' },
          { label: 'Repair', color: '#34D399' },
          { label: 'Fail - Normal', color: '#EF4444' },
          { label: 'Fail - Repair', color: '#F97316' },
        ]} />
      </div>
    </section>
  );
};

export default DataSizeDistributionPanel;
