import type { FC } from "react";
import { useMemo } from "react";
import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis } from "recharts";

import SubpanelHeader from "../../SubpanelHeader";
import Legend from "../../Legend";
import HashstoreTooltip, { makeSizeFormatter } from "./HashstoreTooltip";
import { formatAxisDate, formatDuration, HASHSTORE_COLORS } from "../../../utils/hashstore";
import { formatSizeValue, pickSizeUnit } from "../../../utils/units";
import type { HashstoreCompactionBucket, HashstoreSeriesResponse } from "../../../types";

interface Props {
  data: HashstoreSeriesResponse | null;
}

const HashstoreCompactionPanel: FC<Props> = ({ data }) => {

  const chartData = useMemo(() => {
    if (!data?.buckets) return [];
    return data.buckets
      .filter((b) => b.eventCount > 0)
      .map((b: HashstoreCompactionBucket) => ({
        bucketStart: b.bucketStart,
        bytesRewritten: b.bytesRewritten,
        bytesReclaimed: b.bytesReclaimed,
        dataReclaimable: b.dataReclaimable,
        passes: b.passes,
        compactions: b.eventCount,
        durationMs: b.durationMs,
        avgDurationMs: b.passes > 0 ? b.durationMs / b.passes : 0,
        durationMaxMs: b.durationMaxMs,
        durationMedianMs: b.durationMedianMs,
      }));
  }, [data]);

  const sizeUnit = useMemo(() => {
    if (chartData.length === 0) return { unit: "GB" as const, factor: 1024 ** 3 };
    const maxBytes = Math.max(...chartData.map((d) => Math.max(d.bytesRewritten, d.bytesReclaimed, d.dataReclaimable)));
    return pickSizeUnit(maxBytes);
  }, [chartData]);

  if (chartData.length === 0) {
    return (
      <div className="subpanel">
        <SubpanelHeader title="Compaction Efficiency" />
        <div className="panel__empty">No compaction data available</div>
      </div>
    );
  }

  return (
    <div className="subpanel">
      <SubpanelHeader title="Compaction Efficiency" />
        <ResponsiveContainer width="100%" height={220}>
          <ComposedChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-grid)" />
            <XAxis dataKey="bucketStart" tickFormatter={formatAxisDate} tick={{ fontSize: 11 }} />
            <YAxis
              yAxisId="size"
              tickFormatter={(v: number) => formatSizeValue(v)}
              label={{ value: sizeUnit.unit, angle: -90, position: "insideLeft", style: { fontSize: 11 } }}
              tick={{ fontSize: 11 }}
            />
            <YAxis
              yAxisId="duration"
              orientation="right"
              tickFormatter={(v: number) => formatDuration(v)}
              label={{ value: "Duration", angle: 90, position: "insideRight", style: { fontSize: 11 } }}
              tick={{ fontSize: 11 }}
            />
            <RechartsTooltip
              content={<HashstoreTooltip formatValue={makeSizeFormatter(sizeUnit.unit, 1)} />}
            />
            <Bar dataKey={(d: any) => d.bytesRewritten / sizeUnit.factor} yAxisId="size" fill={HASHSTORE_COLORS.rewritten} name="Rewritten" isAnimationActive={false} />
            <Bar dataKey={(d: any) => d.bytesReclaimed / sizeUnit.factor} yAxisId="size" fill={HASHSTORE_COLORS.reclaimed} name="Reclaimed" isAnimationActive={false} />
            <Bar dataKey={(d: any) => d.dataReclaimable / sizeUnit.factor} yAxisId="size" fill={HASHSTORE_COLORS.reclaimable} name="Reclaimable" isAnimationActive={false} />
            <Line type="monotone" dataKey="durationMs" yAxisId="duration" stroke={HASHSTORE_COLORS.durationTotal} name="Total Duration" dot={false} strokeWidth={2} isAnimationActive={false} />
            <Line type="monotone" dataKey="durationMaxMs" yAxisId="duration" stroke={HASHSTORE_COLORS.durationMax} name="Max Duration" dot={false} strokeWidth={1.5} strokeDasharray="4 2" isAnimationActive={false} />
            <Line type="monotone" dataKey="avgDurationMs" yAxisId="duration" stroke={HASHSTORE_COLORS.duration} name="Avg Duration" dot={false} strokeWidth={1.5} isAnimationActive={false} />
            <Line type="monotone" dataKey="durationMedianMs" yAxisId="duration" stroke={HASHSTORE_COLORS.durationMedian} name="Median Duration" dot={false} strokeWidth={1.5} strokeDasharray="2 2" isAnimationActive={false} />
            <Line type="monotone" dataKey="passes" yAxisId="duration" stroke="none" name="Passes" dot={false} legendType="none" isAnimationActive={false} />
            <Line type="monotone" dataKey="compactions" yAxisId="duration" stroke="none" name="Compactions" dot={false} legendType="none" isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
        <Legend items={[
          { label: "Rewritten", color: HASHSTORE_COLORS.rewritten },
          { label: "Reclaimed", color: HASHSTORE_COLORS.reclaimed },
          { label: "Reclaimable", color: HASHSTORE_COLORS.reclaimable },
          { label: "Total Duration", color: HASHSTORE_COLORS.durationTotal },
          { label: "Max Duration", color: HASHSTORE_COLORS.durationMax },
          { label: "Avg Duration", color: HASHSTORE_COLORS.duration },
          { label: "Median Duration", color: HASHSTORE_COLORS.durationMedian },
        ]} />
    </div>
  );
};

export default HashstoreCompactionPanel;
