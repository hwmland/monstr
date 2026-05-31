import type { FC } from "react";
import { useMemo, useState } from "react";
import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis } from "recharts";

import SubpanelHeader from "../../SubpanelHeader";
import PanelControls from "../../PanelControls";
import PanelControlsButton from "../../PanelControlsButton";
import Legend from "../../Legend";
import HashstoreTooltip, { makeSizeFormatter, makeCountFormatter } from "./HashstoreTooltip";
import { formatAxisDate, HASHSTORE_COLORS } from "../../../utils/hashstore";
import { formatSizeValue, pickSizeUnit } from "../../../utils/units";
import type { HashstoreCompactionBucket, HashstoreSeriesResponse } from "../../../types";

type TrashMode = "records" | "bytes";

interface Props {
  data: HashstoreSeriesResponse | null;
}

const HashstoreHealthPanel: FC<Props> = ({ data }) => {
  const [trashMode, setTrashMode] = useState<TrashMode>("records");

  const chartData = useMemo(() => {
    if (!data?.buckets) return [];
    return data.buckets
      .filter((b) => b.eventCount > 0)
      .map((b: HashstoreCompactionBucket) => ({
        bucketStart: b.bucketStart,
        tableLoad: b.tableLoad,
        dataReclaimable: b.dataReclaimable,
        recordsTrashed: b.recordsTrashed,
        bytesTrashed: b.bytesTrashed,
        recordsExpired: b.recordsExpired,
        bytesExpired: b.bytesExpired,
        recordsRestored: b.recordsRestored,
        bytesRestored: b.bytesRestored,
      }));
  }, [data]);

  const reclaimUnit = useMemo(() => {
    if (chartData.length === 0) return { unit: "GB" as const, factor: 1024 ** 3 };
    const maxBytes = Math.max(...chartData.map((d) => d.dataReclaimable));
    return pickSizeUnit(maxBytes);
  }, [chartData]);

  const trashSizeUnit = useMemo(() => {
    if (trashMode !== "bytes" || chartData.length === 0) return { unit: "MB" as const, factor: 1024 ** 2 };
    const maxBytes = Math.max(...chartData.map((d) => Math.max(d.bytesTrashed, d.bytesExpired, d.bytesRestored)));
    return pickSizeUnit(maxBytes);
  }, [chartData, trashMode]);

  if (chartData.length === 0) {
    return (
      <div className="subpanel">
        <SubpanelHeader title="Health" />
        <div className="panel__empty">No health data available</div>
      </div>
    );
  }

  return (
    <div className="subpanel">
      <SubpanelHeader
        title="Health"
        controls={
          <PanelControls
            ariaLabel="Trash chart mode"
            storageKey="monstr.panel.hashstoreHealth.trashMode"
            buttons={[
              <PanelControlsButton key="records" active={trashMode === "records"} content="Records" onClick={() => setTrashMode("records")} />,
              <PanelControlsButton key="bytes" active={trashMode === "bytes"} content="Bytes" onClick={() => setTrashMode("bytes")} />,
            ]}
          />
        }
      />
        <div className="hashstore-health-grid">
          {/* Load Factor */}
          <div>
            <div className="hashstore-chart-title">Load Factor</div>
            <ResponsiveContainer width="100%" height={150}>
              <ComposedChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-grid)" />
                <XAxis dataKey="bucketStart" tickFormatter={formatAxisDate} tick={{ fontSize: 10 }} />
                <YAxis domain={[0, 1]} tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} tick={{ fontSize: 10 }} />
                <RechartsTooltip content={<HashstoreTooltip formatValue={(v) => `${(v * 100).toFixed(1)}%`} />} />
                <Line type="monotone" dataKey="tableLoad" stroke={HASHSTORE_COLORS.load} name="Load" dot={false} strokeWidth={2} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          {/* Reclaimable */}
          <div>
            <div className="hashstore-chart-title">Reclaimable</div>
            <ResponsiveContainer width="100%" height={150}>
              <ComposedChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-grid)" />
                <XAxis dataKey="bucketStart" tickFormatter={formatAxisDate} tick={{ fontSize: 10 }} />
                <YAxis
                  tickFormatter={(v: number) => formatSizeValue(v)}
                  label={{ value: reclaimUnit.unit, angle: -90, position: "insideLeft", style: { fontSize: 10 } }}
                  tick={{ fontSize: 10 }}
                />
                <RechartsTooltip content={<HashstoreTooltip formatValue={makeSizeFormatter(reclaimUnit.unit, 1)} />} />
                <Line type="monotone" dataKey={(d: any) => d.dataReclaimable / reclaimUnit.factor} stroke={HASHSTORE_COLORS.reclaimable} name="Reclaimable" dot={false} strokeWidth={2} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          {/* Trash Rate */}
          <div>
            <div className="hashstore-chart-title">Trash Rate ({trashMode})</div>
            <ResponsiveContainer width="100%" height={150}>
              <ComposedChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-grid)" />
                <XAxis dataKey="bucketStart" tickFormatter={formatAxisDate} tick={{ fontSize: 10 }} />
                <YAxis
                  tick={{ fontSize: 10 }}
                  tickFormatter={(v: number) => trashMode === "bytes" ? formatSizeValue(v) : String(v)}
                  label={trashMode === "bytes" ? { value: trashSizeUnit.unit, angle: -90, position: "insideLeft", style: { fontSize: 10 } } : undefined}
                />
                <RechartsTooltip content={<HashstoreTooltip formatValue={trashMode === "bytes" ? makeSizeFormatter(trashSizeUnit.unit, 1) : makeCountFormatter()} />} />
                {trashMode === "records" ? (
                  <>
                    <Line type="monotone" dataKey="recordsTrashed" stroke={HASHSTORE_COLORS.trashed} name="Trashed" dot={false} isAnimationActive={false} />
                    <Line type="monotone" dataKey="recordsExpired" stroke={HASHSTORE_COLORS.expired} name="Expired" dot={false} isAnimationActive={false} />
                    <Line type="monotone" dataKey="recordsRestored" stroke={HASHSTORE_COLORS.restored} name="Restored" dot={false} isAnimationActive={false} />
                  </>
                ) : (
                  <>
                    <Line type="monotone" dataKey={(d: any) => d.bytesTrashed / trashSizeUnit.factor} stroke={HASHSTORE_COLORS.trashed} name="Trashed" dot={false} isAnimationActive={false} />
                    <Line type="monotone" dataKey={(d: any) => d.bytesExpired / trashSizeUnit.factor} stroke={HASHSTORE_COLORS.expired} name="Expired" dot={false} isAnimationActive={false} />
                    <Line type="monotone" dataKey={(d: any) => d.bytesRestored / trashSizeUnit.factor} stroke={HASHSTORE_COLORS.restored} name="Restored" dot={false} isAnimationActive={false} />
                  </>
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
        <Legend items={[
          { label: "Load", color: HASHSTORE_COLORS.load },
          { label: "Reclaimable", color: HASHSTORE_COLORS.reclaimable },
          { label: "Trashed", color: HASHSTORE_COLORS.trashed },
          { label: "Expired", color: HASHSTORE_COLORS.expired },
          { label: "Restored", color: HASHSTORE_COLORS.restored },
        ]} />
    </div>
  );
};

export default HashstoreHealthPanel;
