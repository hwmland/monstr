import type { FC } from "react";
import { useMemo } from "react";
import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis } from "recharts";

import SubpanelHeader from "../../SubpanelHeader";
import Legend from "../../Legend";
import HashstoreTooltip, { makeCountFormatter } from "./HashstoreTooltip";
import { formatAxisDate, HASHSTORE_COLORS } from "../../../utils/hashstore";
import { formatSizeValue, pickSizeUnit } from "../../../utils/units";
import type { HashstoreCompactionBucket, HashstoreSeriesResponse } from "../../../types";

interface Props {
  data: HashstoreSeriesResponse | null;
}

const HashstoreDiagnosticsPanel: FC<Props> = ({ data }) => {

  const chartData = useMemo(() => {
    if (!data?.buckets) return [];
    return data.buckets
      .filter((b) => b.eventCount > 0)
      .map((b: HashstoreCompactionBucket) => ({
        bucketStart: b.bucketStart,
        numSet: b.numSet,
        numTrash: b.numTrash,
        numTtl: b.numTtl,
        avgSet: b.avgSet,
        numLogs: b.numLogs,
        lenLogs: b.lenLogs,
        numSlots: b.numSlots,
        tableSize: b.tableSize,
        tableLoad: b.tableLoad,
        freeRequired: b.freeRequired,
      }));
  }, [data]);

  const tableSizeUnit = useMemo(() => {
    if (chartData.length === 0) return { unit: "MB" as const, factor: 1024 ** 2 };
    const maxBytes = Math.max(...chartData.map((d) => d.tableSize));
    return pickSizeUnit(maxBytes);
  }, [chartData]);

  const avgSizeUnit = useMemo(() => {
    if (chartData.length === 0) return { unit: "KB" as const, factor: 1024 };
    const maxBytes = Math.max(...chartData.map((d) => d.avgSet));
    return pickSizeUnit(maxBytes);
  }, [chartData]);

  if (chartData.length === 0) {
    return (
      <div className="subpanel">
        <SubpanelHeader title="Diagnostics" />
        <div className="panel__empty">No diagnostics data available</div>
      </div>
    );
  }

  return (
    <div className="subpanel">
      <SubpanelHeader title="Diagnostics" />
        <div className="hashstore-diagnostics-grid">
          {/* Piece Counts */}
          <div>
            <div className="hashstore-chart-title">Piece Counts</div>
            <ResponsiveContainer width="100%" height={160}>
              <ComposedChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-grid)" />
                <XAxis dataKey="bucketStart" tickFormatter={formatAxisDate} tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={(v: number) => v >= 1_000_000 ? `${(v / 1_000_000).toFixed(1)}M` : v >= 1_000 ? `${(v / 1_000).toFixed(0)}K` : String(v)} />
                <RechartsTooltip content={<HashstoreTooltip formatValue={makeCountFormatter()} />} />
                <Line type="monotone" dataKey="numSet" stroke={HASHSTORE_COLORS.set} name="Set" dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="numTrash" stroke={HASHSTORE_COLORS.trash} name="Trash" dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="numTtl" stroke={HASHSTORE_COLORS.ttl} name="TTL" dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          {/* Avg Piece Size + Table Size */}
          <div>
            <div className="hashstore-chart-title">Infrastructure</div>
            <ResponsiveContainer width="100%" height={160}>
              <ComposedChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-grid)" />
                <XAxis dataKey="bucketStart" tickFormatter={formatAxisDate} tick={{ fontSize: 10 }} />
                <YAxis
                  yAxisId="size"
                  tickFormatter={(v: number) => formatSizeValue(v)}
                  label={{ value: tableSizeUnit.unit, angle: -90, position: "insideLeft", style: { fontSize: 10 } }}
                  tick={{ fontSize: 10 }}
                />
                <YAxis
                  yAxisId="avg"
                  orientation="right"
                  tickFormatter={(v: number) => formatSizeValue(v)}
                  label={{ value: avgSizeUnit.unit, angle: 90, position: "insideRight", style: { fontSize: 10 } }}
                  tick={{ fontSize: 10 }}
                />
                <RechartsTooltip
                  content={<HashstoreTooltip formatValue={(value, name) => {
                    if (name === "Table Size") return `${formatSizeValue(value)} ${tableSizeUnit.unit}`;
                    if (name === "Avg Piece") return `${formatSizeValue(value)} ${avgSizeUnit.unit}`;
                    if (name === "Free Required") return `${formatSizeValue(value)} ${tableSizeUnit.unit}`;
                    if (name === "Load") return `${(value * 100).toFixed(1)}%`;
                    return String(value);
                  }} />}
                />
                <Line type="monotone" dataKey={(d: any) => d.tableSize / tableSizeUnit.factor} yAxisId="size" stroke={HASHSTORE_COLORS.load} name="Table Size" dot={false} strokeWidth={2} isAnimationActive={false} />
                <Line type="monotone" dataKey={(d: any) => d.freeRequired / tableSizeUnit.factor} yAxisId="size" stroke={HASHSTORE_COLORS.freeRequired} name="Free Required" dot={false} strokeWidth={1.5} strokeDasharray="4 2" isAnimationActive={false} />
                <Line type="monotone" dataKey={(d: any) => d.avgSet / avgSizeUnit.factor} yAxisId="avg" stroke={HASHSTORE_COLORS.passes} name="Avg Piece" dot={false} strokeWidth={2} isAnimationActive={false} />
                <Line type="monotone" dataKey="tableLoad" yAxisId="avg" stroke={HASHSTORE_COLORS.reclaimable} name="Load" dot={false} strokeWidth={1.5} strokeDasharray="4 2" isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
        <Legend items={[
          { label: "Set", color: HASHSTORE_COLORS.set },
          { label: "Trash", color: HASHSTORE_COLORS.trash },
          { label: "TTL", color: HASHSTORE_COLORS.ttl },
          { label: "Table Size", color: HASHSTORE_COLORS.load },
          { label: "Free Required", color: HASHSTORE_COLORS.freeRequired },
          { label: "Avg Piece", color: HASHSTORE_COLORS.passes },
          { label: "Load %", color: HASHSTORE_COLORS.reclaimable },
        ]} />
    </div>
  );
};

export default HashstoreDiagnosticsPanel;
