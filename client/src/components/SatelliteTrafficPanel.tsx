import type { FC } from "react";
import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { TransferActualData } from "../types";
import { formatWindowTime } from "../utils/time";
import { formatSizeValue, pickSizeUnit } from "../utils/units";

type SatelliteTrafficMode = "size" | "count";

interface SatelliteTrafficPanelProps {
  data: TransferActualData | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => void;
  selectedNodes: string[];
}

interface TrafficChartDatum {
  key: string;
  satellite: string;
  downloadNormal: number;
  downloadRepair: number;
  uploadNormal: number;
  uploadRepair: number;
}

interface LabelRendererProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  index?: number;
}

const SatelliteTrafficPanel: FC<SatelliteTrafficPanelProps> = ({
  data,
  isLoading,
  error,
  refresh,
  selectedNodes,
}) => {
  const [mode, setMode] = useState<SatelliteTrafficMode>("size");
  const windowStart = formatWindowTime(data?.startTime ?? null);
  const windowEnd = formatWindowTime(data?.endTime ?? null);
  const nodesLabel = selectedNodes.length === 0 ? "All nodes" : `Nodes: ${selectedNodes.join(", ")}`;

  const { chartData, sizeUnit } = useMemo(() => {
    const satellites = data?.satellites ?? [];
    const aggregateTotals = satellites.map((satellite) => {
      const downloadBytes = satellite.download.normal.dataBytes + satellite.download.repair.dataBytes;
      const uploadBytes = satellite.upload.normal.dataBytes + satellite.upload.repair.dataBytes;
      return downloadBytes + uploadBytes;
    });

    const maxBytes = aggregateTotals.length > 0 ? Math.max(...aggregateTotals) : 0;
  const { factor: sizeFactor, unit } = pickSizeUnit(maxBytes);

    const chartDataMapped = satellites.map((satellite, index) => {
      const satelliteName = satellite.satelliteName || satellite.satelliteId || `Satellite ${index + 1}`;

      const toValue = (type: "download" | "upload", category: "normal" | "repair") => {
        const metrics = satellite[type][category];
        if (mode === "size") {
          return metrics.dataBytes / sizeFactor;
        }
        return metrics.operationsSuccess;
      };

      return {
        key: satellite.satelliteId || String(index),
        satellite: satelliteName,
        downloadNormal: toValue("download", "normal"),
        downloadRepair: toValue("download", "repair"),
        uploadNormal: toValue("upload", "normal"),
        uploadRepair: toValue("upload", "repair"),
      } satisfies TrafficChartDatum;
    });

    return { chartData: chartDataMapped, sizeUnit: unit };
  }, [data?.satellites, mode]);

  const downloadsEmpty = chartData.every(
    (item) => item.downloadNormal + item.downloadRepair === 0,
  );
  const uploadsEmpty = chartData.every((item) => item.uploadNormal + item.uploadRepair === 0);
  const hasAnyData = chartData.length > 0 && !(downloadsEmpty && uploadsEmpty);

  const yAxisLabel = mode === "size" ? sizeUnit : "Success";
  const formatValue = (value: number) => {
    if (mode === "size") {
      return formatSizeValue(value);
    }
    return value.toFixed(0);
  };
  const renderStackLabel = (props: LabelRendererProps, text: "DL" | "UL") => {
    const { x = 0, y = 0, width = 0, index = 0 } = props;
    const datum = chartData[index];
    if (!datum) {
      return null;
    }

    const totalValue =
      text === "DL"
        ? datum.downloadNormal + datum.downloadRepair
        : datum.uploadNormal + datum.uploadRepair;
    if (totalValue <= 0) {
      return null;
    }

    const centerX = x + width / 2;
    const labelY = y - 8;

    return (
      <text
        x={centerX}
        y={labelY}
        textAnchor="middle"
        fontSize={12}
        fontWeight={600}
        fill="var(--color-text)"
      >
        {text}
      </text>
    );
  };

  const renderDownloadLabel = (props: LabelRendererProps) => renderStackLabel(props, "DL");
  const renderUploadLabel = (props: LabelRendererProps) => renderStackLabel(props, "UL");

  return (
    <section className="panel">
      <header className="panel__header">
        <div>
          <h2 className="panel__title">Satellite Traffic</h2>
          <p className="panel__subtitle">
            Window: {windowStart} – {windowEnd} • {nodesLabel}
          </p>
        </div>
        <div className="panel__actions panel__actions--stacked">
          <button className="button" type="button" onClick={() => refresh()} disabled={isLoading}>
            {isLoading ? "Loading…" : "Refresh"}
          </button>
          <div className="button-group button-group--micro">
            <button
              type="button"
              className={`button button--micro${mode === "size" ? " button--micro-active" : ""}`}
              onClick={() => setMode("size")}
            >
              Size
            </button>
            <button
              type="button"
              className={`button button--micro${mode === "count" ? " button--micro-active" : ""}`}
              onClick={() => setMode("count")}
            >
              Count
            </button>
          </div>
        </div>
      </header>

      {error ? <p className="panel__error">{error}</p> : null}

      <div className="panel__body">
        {isLoading && chartData.length === 0 ? (
          <p className="panel__status">Loading satellite traffic…</p>
        ) : null}

        {!isLoading && chartData.length === 0 ? (
          <p className="panel__empty">No satellite transfer activity recorded.</p>
        ) : null}

        {chartData.length > 0 ? (
          <div className="traffic-chart">
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={chartData} barGap={8} barCategoryGap="20%">
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis dataKey="satellite" height={62} tick={{ fill: "var(--color-text-muted)", fontSize: 12 }} />
                <YAxis
                  tickFormatter={(value: number) => formatValue(value)}
                  width={60}
                  tick={{ fill: "var(--color-text-muted)", fontSize: 12 }}
                  label={{ value: yAxisLabel, angle: -90, position: "insideLeft", fill: "var(--color-text-muted)" }}
                />
                <Tooltip
                  cursor={{ fill: "rgba(148, 163, 184, 0.1)" }}
                  formatter={(value: number | string, name: string) => {
                    const labelMap: Record<string, string> = {
                      downloadNormal: "Download Normal",
                      downloadRepair: "Download Repair",
                      uploadNormal: "Upload Normal",
                      uploadRepair: "Upload Repair",
                    };
                    const numericValueRaw = typeof value === "number" ? value : Number(value);
                    const numericValue = Number.isFinite(numericValueRaw) ? numericValueRaw : 0;
                    const formatted = mode === "size"
                      ? `${formatSizeValue(numericValue)} ${sizeUnit}`
                      : `${numericValue.toFixed(0)} ops`;
                    return [formatted, labelMap[name] ?? name];
                  }}
                  labelFormatter={(label: string) => `Satellite: ${label}`}
                />
                <Legend
                  formatter={(value: string) => {
                    const legendMap: Record<string, string> = {
                      downloadNormal: "Download Normal",
                      downloadRepair: "Download Repair",
                      uploadNormal: "Upload Normal",
                      uploadRepair: "Upload Repair",
                    };
                    return legendMap[value] ?? value;
                  }}
                />
                <Bar
                  dataKey="downloadNormal"
                  stackId="download"
                  fill="rgba(56, 189, 248, 0.85)"
                  isAnimationActive={false}
                />
                <Bar
                  dataKey="downloadRepair"
                  stackId="download"
                  fill="rgba(248, 113, 113, 0.85)"
                  isAnimationActive={false}
                >
                  <LabelList position="top" content={renderDownloadLabel} />
                </Bar>
                <Bar
                  dataKey="uploadNormal"
                  stackId="upload"
                  fill="rgba(52, 211, 153, 0.85)"
                  isAnimationActive={false}
                />
                <Bar
                  dataKey="uploadRepair"
                  stackId="upload"
                  fill="rgba(249, 115, 22, 0.85)"
                  isAnimationActive={false}
                >
                  <LabelList position="top" content={renderUploadLabel} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : null}

        {chartData.length > 0 && !hasAnyData ? (
          <p className="panel__empty">All values are zero for the selected window.</p>
        ) : null}
      </div>
    </section>
  );
};

export default SatelliteTrafficPanel;
