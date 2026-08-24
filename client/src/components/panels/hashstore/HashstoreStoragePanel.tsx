import type { FC } from "react";
import { useMemo, useState } from "react";
import { Area, CartesianGrid, ComposedChart, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis } from "recharts";

import SubpanelHeader from "../../SubpanelHeader";
import PanelControls from "../../PanelControls";
import PanelControlsButton from "../../PanelControlsButton";
import Legend from "../../Legend";
import HashstoreTooltip, { makeSizeFormatter, makePercentFormatter } from "./HashstoreTooltip";
import { formatAxisDate, HASHSTORE_COLORS } from "../../../utils/hashstore";
import { formatSizeValue, pickSizeUnit } from "../../../utils/units";
import type { HashstoreCompactionBucket, HashstoreSeriesResponse } from "../../../types";

type Mode = "bytes" | "percent";

interface Props {
  data: HashstoreSeriesResponse | null;
}

const HashstoreStoragePanel: FC<Props> = ({ data }) => {
  const [mode, setMode] = useState<Mode>("bytes");

  const chartData = useMemo(() => {
    if (!data?.buckets) return [];
    return data.buckets
      .filter((b) => b.eventCount > 0)
      .map((b: HashstoreCompactionBucket) => ({
        bucketStart: b.bucketStart,
        lenSet: b.lenSet,
        lenTrash: b.lenTrash,
        lenTtl: b.lenTtl,
        setPercent: b.setPercent,
        trashPercent: b.trashPercent,
        ttlPercent: b.ttlPercent,
      }));
  }, [data]);

  const sizeUnit = useMemo(() => {
    if (chartData.length === 0) return { unit: "GB" as const, factor: 1024 ** 3 };
    const maxBytes = Math.max(...chartData.map((d) => d.lenSet + d.lenTrash + d.lenTtl));
    return pickSizeUnit(maxBytes);
  }, [chartData]);

  const scaledData = useMemo(() => {
    if (mode === "percent") {
      return chartData.map((d) => ({
        bucketStart: d.bucketStart,
        set: d.setPercent,
        trash: d.trashPercent,
        ttl: d.ttlPercent,
      }));
    }
    return chartData.map((d) => ({
      bucketStart: d.bucketStart,
      set: d.lenSet / sizeUnit.factor,
      trash: d.lenTrash / sizeUnit.factor,
      ttl: d.lenTtl / sizeUnit.factor,
    }));
  }, [chartData, mode, sizeUnit]);

  const yLabel = mode === "percent" ? "%" : sizeUnit.unit;

  if (scaledData.length === 0) {
    return (
      <div className="subpanel">
        <SubpanelHeader title="Storage Composition" />
        <div className="panel__empty">No hashstore data available</div>
      </div>
    );
  }

  return (
    <div className="subpanel">
      <SubpanelHeader
        title="Storage Composition"
        controls={
          <PanelControls
            ariaLabel="Display mode"
            storageKey="monstr.panel.hashstoreStorage.mode"
            buttons={[
              <PanelControlsButton key="bytes" active={mode === "bytes"} content="Bytes" onClick={() => setMode("bytes")} />,
              <PanelControlsButton key="percent" active={mode === "percent"} content="%" onClick={() => setMode("percent")} />,
            ]}
          />
        }
      />
        <ResponsiveContainer width="100%" height={220}>
          <ComposedChart data={scaledData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-grid)" />
            <XAxis dataKey="bucketStart" tickFormatter={formatAxisDate} tick={{ fontSize: 11 }} />
            <YAxis
              tickFormatter={(v: number) => mode === "percent" ? `${v.toFixed(0)}%` : formatSizeValue(v)}
              label={{ value: yLabel, angle: -90, position: "insideLeft", style: { fontSize: 11 } }}
              tick={{ fontSize: 11 }}
            />
            <RechartsTooltip
              content={<HashstoreTooltip formatValue={mode === "percent" ? makePercentFormatter() : makeSizeFormatter(sizeUnit.unit, 1)} />}
            />
            <Area type="monotone" dataKey="set" stackId="1" fill={HASHSTORE_COLORS.set} stroke={HASHSTORE_COLORS.set} name="Set" isAnimationActive={false} />
            <Area type="monotone" dataKey="trash" stackId="1" fill={HASHSTORE_COLORS.trash} stroke={HASHSTORE_COLORS.trash} name="Trash" isAnimationActive={false} />
            <Area type="monotone" dataKey="ttl" stackId="1" fill={HASHSTORE_COLORS.ttl} stroke={HASHSTORE_COLORS.ttl} name="TTL" isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
        <Legend items={[
          { label: "Set", color: HASHSTORE_COLORS.set },
          { label: "Trash", color: HASHSTORE_COLORS.trash },
          { label: "TTL", color: HASHSTORE_COLORS.ttl },
        ]} />
    </div>
  );
};

export default HashstoreStoragePanel;
