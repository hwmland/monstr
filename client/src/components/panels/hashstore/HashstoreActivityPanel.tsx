import type { FC } from "react";
import { useMemo, useState } from "react";
import { Bar, CartesianGrid, ComposedChart, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis } from "recharts";

import SubpanelHeader from "../../SubpanelHeader";
import PanelControls from "../../PanelControls";
import PanelControlsButton from "../../PanelControlsButton";
import Legend from "../../Legend";
import HashstoreTooltip, { makeSizeFormatter, makeCountFormatter } from "./HashstoreTooltip";
import { formatAxisDate, HASHSTORE_COLORS } from "../../../utils/hashstore";
import { formatSizeValue, pickSizeUnit } from "../../../utils/units";
import type { HashstoreCompactionBucket, HashstoreSeriesResponse } from "../../../types";

type Mode = "bytes" | "records";

interface Props {
  data: HashstoreSeriesResponse | null;
}

const HashstoreActivityPanel: FC<Props> = ({ data }) => {
  const [mode, setMode] = useState<Mode>("bytes");

  const chartData = useMemo(() => {
    if (!data?.buckets) return [];
    return data.buckets
      .filter((b) => b.eventCount > 0)
      .map((b: HashstoreCompactionBucket) => ({
        bucketStart: b.bucketStart,
        bytesRewritten: b.bytesRewritten,
        bytesTrashed: b.bytesTrashed,
        bytesExpired: b.bytesExpired,
        bytesRestored: b.bytesRestored,
        bytesReclaimed: b.bytesReclaimed,
        recordsRewritten: b.recordsRewritten,
        recordsTrashed: b.recordsTrashed,
        recordsExpired: b.recordsExpired,
        recordsRestored: b.recordsRestored,
        logsReclaimed: b.logsReclaimed,
      }));
  }, [data]);

  const sizeUnit = useMemo(() => {
    if (chartData.length === 0) return { unit: "GB" as const, factor: 1024 ** 3 };
    const maxBytes = Math.max(...chartData.map((d) => d.bytesRewritten + d.bytesTrashed + d.bytesExpired + d.bytesReclaimed));
    return pickSizeUnit(maxBytes);
  }, [chartData]);

  if (chartData.length === 0) {
    return (
      <div className="subpanel">
        <SubpanelHeader title="Activity" />
        <div className="panel__empty">No activity data available</div>
      </div>
    );
  }

  return (
    <div className="subpanel">
      <SubpanelHeader
        title="Activity"
        controls={
          <PanelControls
            ariaLabel="Activity mode"
            storageKey="monstr.panel.hashstoreActivity.mode"
            buttons={[
              <PanelControlsButton key="bytes" active={mode === "bytes"} content="Bytes" onClick={() => setMode("bytes")} />,
              <PanelControlsButton key="records" active={mode === "records"} content="Records" onClick={() => setMode("records")} />,
            ]}
          />
        }
      />
        <ResponsiveContainer width="100%" height={220}>
          <ComposedChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-grid)" />
            <XAxis dataKey="bucketStart" tickFormatter={formatAxisDate} tick={{ fontSize: 11 }} />
            <YAxis
              tickFormatter={(v: number) => mode === "bytes" ? formatSizeValue(v) : String(v)}
              label={mode === "bytes" ? { value: sizeUnit.unit, angle: -90, position: "insideLeft", style: { fontSize: 11 } } : undefined}
              tick={{ fontSize: 11 }}
            />
            <RechartsTooltip
              content={<HashstoreTooltip formatValue={mode === "bytes" ? makeSizeFormatter(sizeUnit.unit, 1) : makeCountFormatter()} />}
            />
            {mode === "bytes" ? (
              <>
                <Bar dataKey={(d: any) => d.bytesRewritten / sizeUnit.factor} fill={HASHSTORE_COLORS.rewritten} name="Rewritten" stackId="a" isAnimationActive={false} />
                <Bar dataKey={(d: any) => d.bytesTrashed / sizeUnit.factor} fill={HASHSTORE_COLORS.trashed} name="Trashed" stackId="a" isAnimationActive={false} />
                <Bar dataKey={(d: any) => d.bytesExpired / sizeUnit.factor} fill={HASHSTORE_COLORS.expired} name="Expired" stackId="a" isAnimationActive={false} />
                <Bar dataKey={(d: any) => d.bytesRestored / sizeUnit.factor} fill={HASHSTORE_COLORS.restored} name="Restored" stackId="b" isAnimationActive={false} />
                <Bar dataKey={(d: any) => d.bytesReclaimed / sizeUnit.factor} fill={HASHSTORE_COLORS.reclaimed} name="Reclaimed" stackId="b" isAnimationActive={false} />
              </>
            ) : (
              <>
                <Bar dataKey="recordsRewritten" fill={HASHSTORE_COLORS.rewritten} name="Rewritten" stackId="a" isAnimationActive={false} />
                <Bar dataKey="recordsTrashed" fill={HASHSTORE_COLORS.trashed} name="Trashed" stackId="a" isAnimationActive={false} />
                <Bar dataKey="recordsExpired" fill={HASHSTORE_COLORS.expired} name="Expired" stackId="a" isAnimationActive={false} />
                <Bar dataKey="recordsRestored" fill={HASHSTORE_COLORS.restored} name="Restored" stackId="b" isAnimationActive={false} />
                <Bar dataKey="logsReclaimed" fill={HASHSTORE_COLORS.reclaimed} name="Reclaimed" stackId="b" isAnimationActive={false} />
              </>
            )}
          </ComposedChart>
        </ResponsiveContainer>
        <Legend items={[
          { label: "Rewritten", color: HASHSTORE_COLORS.rewritten },
          { label: "Trashed", color: HASHSTORE_COLORS.trashed },
          { label: "Expired", color: HASHSTORE_COLORS.expired },
          { label: "Restored", color: HASHSTORE_COLORS.restored },
          { label: "Reclaimed", color: HASHSTORE_COLORS.reclaimed },
        ]} />
    </div>
  );
};

export default HashstoreActivityPanel;
