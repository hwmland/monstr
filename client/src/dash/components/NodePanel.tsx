import { useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ComposedChart,
  Cell,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { pickSizePresentation, pickSizeUnit, formatSizeValue } from "../../utils/units";
import useDashNodeDetails from "../hooks/useDashNodeDetails";
import NodeId from "./NodeId";
import SatelliteComponent from "./SatelliteComponent";
import type { DashNodeDetails } from "../types";

interface NodePanelProps {
  nodeName: string;
  refreshToken: number;
}

const formatBytesShort = (bytes: number): string => {
  const { value, unit } = pickSizePresentation(bytes);
  return `${formatSizeValue(value)} ${unit}`;
};

const formatBytesTooltip = (bytes: number): string => {
  const { value, unit } = pickSizePresentation(bytes);
  return `${formatSizeValue(value)} ${unit}`;
};

const StatusBlock = ({ details }: { details: DashNodeDetails }) => {
  const status = details.status;
  const stats = details.statistics;
  const lastPingMinutes = status.lastPinged ? Math.floor((Date.now() - Date.parse(status.lastPinged)) / 60000) : null;
  const isOnline = lastPingMinutes !== null && lastPingMinutes < 120;
  const quicOk = status.quicStatus === "OK";

  return (
    <div className="dash-status-box">
      <div className="dash-status-box__row dash-status-box__row--head">
        <span>Status</span>
        <span>QUIC</span>
        <span>Uptime</span>
        <span>Version</span>
        <span>From</span>
      </div>
      <div className="dash-status-box__row">
        <span className={isOnline ? "dash-status--ok" : "dash-status--warn"}>{isOnline ? "Online" : "Offline"}</span>
        <span className={quicOk ? "dash-status--ok" : "dash-status--warn"}>{status.quicStatus}</span>
        <span>{status.startedAt ? formatDurationFrom(status.startedAt) : "N/A"}</span>
        <span title={`Minimal allowed version: ${status.allowedVersion}`}>{status.version}</span>
        <span>{stats.earliestJoinedAt ? new Date(stats.earliestJoinedAt).toLocaleDateString() : "N/A"}</span>
      </div>
    </div>
  );
};

const formatDurationFrom = (isoDate: string): string => {
  const timestamp = Date.parse(isoDate);
  if (Number.isNaN(timestamp)) return "N/A";
  const diffMs = Date.now() - timestamp;
  const totalMinutes = Math.max(0, Math.floor(diffMs / 60000));
  const days = Math.floor(totalMinutes / (60 * 24));
  const hours = Math.floor((totalMinutes % (60 * 24)) / 60);
  const minutes = totalMinutes % 60;
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
};

const NodePanel = ({ nodeName, refreshToken }: NodePanelProps) => {
  const { details, isLoading, error } = useDashNodeDetails(nodeName, refreshToken);

  const [expandedChart, setExpandedChart] = useState<"bandwidth" | "storage" | null>(null);

  const status = details?.status;
  const stats = details?.statistics;

  const diskSpace = status?.diskSpace;
  const storageDaily = stats?.storageDaily ?? [];
  const bandwidthDaily = stats?.bandwidthDaily ?? [];

  const storageUnit = pickSizeUnit(storageDaily.reduce((max, item) => Math.max(max, item.atRestTotalBytes), 0) || 1);
  const storageSeries = storageDaily.map((item) => ({
    label: new Date(item.intervalStart).getDate(),
    value: item.atRestTotalBytes / storageUnit.factor,
    intervalStart: item.intervalStart,
    raw: item,
  }));

  const bandwidthMax = bandwidthDaily.reduce((max, item) => {
    const total = item.egress.repair + item.egress.audit + item.egress.usage + item.ingress.repair + item.ingress.usage;
    return Math.max(max, total);
  }, 0);
  const bandwidthUnit = pickSizeUnit(bandwidthMax || 1);
  const bandwidthStackedSeries = bandwidthDaily.map((item) => {
    const egress = item.egress.repair + item.egress.audit + item.egress.usage;
    const ingress = item.ingress.repair + item.ingress.usage;
    return {
      label: new Date(item.intervalStart).getDate(),
      egress: egress / bandwidthUnit.factor,
      ingress: ingress / bandwidthUnit.factor,
      total: (egress + ingress) / bandwidthUnit.factor,
      intervalStart: item.intervalStart,
      raw: item,
    };
  });
  const bandwidthMaxTotal = bandwidthStackedSeries.reduce((max, item) => Math.max(max, item.total), 0);
  const bandwidthMaxEgress = bandwidthStackedSeries.reduce((max, item) => Math.max(max, item.egress), 0);
  const bandwidthMaxIngress = bandwidthStackedSeries.reduce((max, item) => Math.max(max, item.ingress), 0);
  const bandwidthMaxOverall = Math.max(bandwidthMaxTotal, bandwidthMaxEgress, bandwidthMaxIngress);

  const renderBandwidthTooltip = ({ active, payload }: { active?: boolean; payload?: any[] }) => {
    if (!active || !payload || !payload.length) return null;
    const { raw } = payload[0].payload as { raw: typeof bandwidthDaily[number] };
    const tableValueStyle = { fontWeight: 700, padding: "0 1em" } as const;
    return (
      <div
        style={{
          backgroundColor: "rgba(30, 41, 59, 0.96)",
          border: "3px solid rgba(205, 218, 237, 0.7)",
          borderRadius: "12px",
          padding: "0.35em 0.75em",
          color: "var(--color-text)",
          boxShadow: "0 12px 28px rgba(8, 15, 35, 0.45)",
        }}
      >
        <table style={{ borderSpacing: "0 0.3em", fontSize: "1em", color: "var(--color-text)", tableLayout: "fixed", borderCollapse: "separate", textAlign: "right", whiteSpace: "nowrap" }}>
          <thead>
            <tr>
              <th></th>
              <th style={{ padding: "0.1em 1em", color: "var(--color-text-muted)" }}>Egress</th>
              <th style={{ padding: "0.1em 1em", color: "var(--color-text-muted)" }}>Ingress</th>
            </tr>
          </thead>
          <tbody>
            <tr style={{ backgroundColor: "rgba(51, 65, 85, 0.96)" }}>
              <td style={{ textAlign: "left", paddingLeft: "1em" }}>Usage</td>
              <td style={tableValueStyle}>{formatBytesTooltip(raw.egress.usage)}</td>
              <td style={tableValueStyle}>{formatBytesTooltip(raw.ingress.usage)}</td>
            </tr>
            <tr style={{ backgroundColor: "rgba(51, 65, 85, 0.96)" }}>
              <td style={{ textAlign: "left", paddingLeft: "1em" }}>Repair</td>
              <td style={tableValueStyle}>{formatBytesTooltip(raw.egress.repair)}</td>
              <td style={tableValueStyle}>{formatBytesTooltip(raw.ingress.repair)}</td>
            </tr>
            <tr style={{ backgroundColor: "rgba(51, 65, 85, 0.96)" }}>
              <td style={{ textAlign: "left", paddingLeft: "1em" }}>Audit</td>
              <td style={tableValueStyle}>{formatBytesTooltip(raw.egress.audit)}</td>
              <td style={tableValueStyle}></td>
            </tr>
          </tbody>
        </table>
        <p style={{ fontSize: "0.7em", padding: "0 0.6em", margin: "0.3em 0", color: "var(--color-text-muted)" }}>{`Day ${new Date(raw.intervalStart).toLocaleDateString()}`}</p>
      </div>
    );
  };

  const renderStorageTooltip = ({ active, payload }: { active?: boolean; payload?: any[] }) => {
    if (!active || !payload || !payload.length) return null;
    const { raw } = payload[0].payload as { raw: typeof storageDaily[number] };
    return (
      <div
        style={{
          backgroundColor: "rgba(30, 41, 59, 0.96)",
          border: "3px solid rgba(205, 218, 237, 0.7)",
          borderRadius: "12px",
          padding: "0.35em 0.75em",
          color: "var(--color-text)",
          boxShadow: "0 12px 28px rgba(8, 15, 35, 0.45)",
        }}
      >
        <p style={{ margin: 0, fontWeight: 700 }}>{formatBytesTooltip(raw.atRestTotalBytes)}</p>
        <p style={{ fontSize: "0.7em", padding: "0 0.1em", margin: "0.3em 0 0", color: "var(--color-text-muted)" }}>
          {`Day ${new Date(raw.intervalStart).toLocaleDateString()}`}
        </p>
      </div>
    );
  };

  const renderDiskTooltip = ({ active, payload }: { active?: boolean; payload?: any[] }) => {
    if (!active || !payload || !payload.length) return null;
    const first = payload[0];
    const name = (first && (first.name ?? first.payload?.label)) || "";
    const value = first?.value ?? 0;
    return (
      <div
        style={{
          backgroundColor: "rgba(30, 41, 59, 0.96)",
          border: "3px solid rgba(205, 218, 237, 0.7)",
          borderRadius: "12px",
          padding: "0.35em 0.75em",
          color: "var(--color-text)",
          boxShadow: "0 12px 28px rgba(8, 15, 35, 0.45)",
        }}
      >
        <p style={{ margin: 0, fontWeight: 700 }}>{`${name}: ${formatBytesTooltip(value)}`}</p>
      </div>
    );
  };

  const diskSpaceBreakdown = diskSpace
    ? [
        { key: "used", label: "Used", value: diskSpace.used, color: "#0059D0" },
        { key: "free", label: "Free", value: Math.max(0, diskSpace.available - (diskSpace.used + diskSpace.trash + diskSpace.overused)), color: "#D6D6D6" },
        { key: "trash", label: "Trash", value: diskSpace.trash, color: "#8A2BE2" },
        { key: "over", label: "Overused", value: diskSpace.overused, color: "#2582FF" },
      ]
    : [];

  const diskTotalDisplay = diskSpace ? formatBytesShort(diskSpace.available) : "N/A";
  const diskTotalValue = diskSpace?.available ?? 0;

  const toggleExpanded = (chart: "bandwidth" | "storage") => {
    setExpandedChart((current) => (current === chart ? null : chart));
  };

  const cardVisibilityClass = (card: "bandwidth" | "storage" | "disk") =>
    expandedChart && expandedChart !== card ? " dash-node-mini--hidden" : "";

  const chartCardClass = (chart: "bandwidth" | "storage") =>
    `dash-node-mini dash-node-mini--expandable${expandedChart === chart ? " dash-node-mini--expanded" : ""}${cardVisibilityClass(chart)}`;

  const handleKeyToggle = (chart: "bandwidth" | "storage") => (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      toggleExpanded(chart);
    }
  };

  const renderBandwidthCard = () => (
    <div
      className={chartCardClass("bandwidth")}
      role="button"
      tabIndex={0}
      onClick={() => toggleExpanded("bandwidth")}
      onKeyDown={handleKeyToggle("bandwidth")}
    >
      <span className="dash-node-mini__label">Bandwidth this month</span>
      <span className="dash-node-mini__value">{formatBytesShort(stats?.bandwidthSummary ?? 0)}</span>
      <div className="dash-mini-chart">
        {bandwidthStackedSeries.length === 0 ? (
          <p className="panel__status">No bandwidth history available.</p>
        ) : (
          <ResponsiveContainer height="100%">
            <ComposedChart data={bandwidthStackedSeries} margin={{ top: 2, right: 1, left: 2, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="label" tickMargin={8} />
              <YAxis
                width={40}
                allowDecimals={false}
                tickFormatter={(v: number) => `${Math.round(Number(v))}`}
                domain={[0, bandwidthMaxOverall ? bandwidthMaxOverall * 1.05 : "auto"]}
                label={{ value: bandwidthUnit.unit, angle: -90, position: "insideLeft" }}
              />
              <Tooltip content={renderBandwidthTooltip} wrapperStyle={{ zIndex: 50 }} />
              <Area type="monotone" dataKey="ingress" stroke="none" fill="#ffc52f" isAnimationActive={false} name="Ingress" />
              <Area type="monotone" dataKey="egress" stroke="none" fill="#00CE7D" isAnimationActive={false} name="Egress" />
              <Line type="monotone" dataKey="total" stroke="#2582FF" dot={false} isAnimationActive={false} name="Total" connectNulls />
              {bandwidthMaxTotal > 0 ? <ReferenceLine y={bandwidthMaxTotal} stroke="#2582FF" strokeDasharray="5 2" /> : null}
              {bandwidthMaxEgress > 0 ? <ReferenceLine y={bandwidthMaxEgress} stroke="#00CE7D" strokeDasharray="5 2" /> : null}
              {bandwidthMaxIngress > 0 ? <ReferenceLine y={bandwidthMaxIngress} stroke="#ffc52f" strokeDasharray="5 2" /> : null}
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );

  const renderStorageCard = () => (
    <div
      className={chartCardClass("storage")}
      role="button"
      tabIndex={0}
      onClick={() => toggleExpanded("storage")}
      onKeyDown={handleKeyToggle("storage")}
    >
      <span className="dash-node-mini__label">Avg Disk Usage this month</span>
      <span className="dash-node-mini__value">{formatBytesShort(stats?.averageUsageBytes ?? 0)}</span>
      <div className="dash-mini-chart">
        {storageSeries.length === 0 ? (
          <p className="panel__status">No storage history available.</p>
        ) : (
          <ResponsiveContainer height="100%">
            <AreaChart data={storageSeries} margin={{ top: 2, right: 1, left: 2, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="label" tickMargin={8} />
              <YAxis
                width={40}
                allowDecimals={false}
                tickFormatter={(v: number) => `${Math.round(Number(v))}`}
                label={{ value: storageUnit.unit, angle: -90, position: "insideLeft" }}
              />
              <Tooltip content={renderStorageTooltip} wrapperStyle={{ zIndex: 50 }} />
              <Area type="monotone" dataKey="value" stroke="#3b82f6" fill="#2563eb" isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );

  const renderDiskCard = () => (
    <div className={`dash-node-mini${cardVisibilityClass("disk")}`}>
      <span className="dash-node-mini__label">Total Disk Space {diskTotalDisplay}</span>
      {diskSpace ? (
        <>
          <div className="dash-mini-chart dash-mini-chart--pie">
            <ResponsiveContainer width="90%" height={170}>
              <PieChart>
                <Pie
                  data={diskSpaceBreakdown}
                  dataKey="value"
                  nameKey="label"
                  cx="50%"
                  cy="50%"
                  innerRadius="45%"
                  outerRadius="95%"
                  paddingAngle={0}
                  isAnimationActive={false}
                  labelLine={false}
                >
                  {diskSpaceBreakdown.map((entry) => (
                    <Cell key={entry.key} fill={entry.color} />
                  ))}
                </Pie>
                <text x="50%" y="50%" textAnchor="middle" dominantBaseline="middle" fill="#e2e8f0" fontSize={14} fontWeight={600}>
                  {diskTotalDisplay}
                </text>
                <Tooltip content={renderDiskTooltip} wrapperStyle={{ zIndex: 50 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="dash-node-mini__legend" role="table" aria-label="Disk space breakdown">
            {diskSpaceBreakdown.map((entry) => {
              const ratio = diskTotalValue > 0 ? entry.value / diskTotalValue : 0;
              const percent = `${Math.round(ratio * 100)}%`;
              return (
                <div key={entry.key} className="dash-node-mini__legend-row" role="row">
                  <div className="dash-node-mini__legend-segment" role="cell">
                    <span className="dash-node-mini__swatch" style={{ backgroundColor: entry.color }} aria-hidden />
                    <span className="dash-node-mini__legend-label">{entry.label}</span>
                  </div>
                  <span className="dash-node-mini__legend-percent" role="cell">{percent}</span>
                  <strong className="dash-node-mini__legend-value" role="cell">{formatBytesShort(entry.value)}</strong>
                </div>
              );
            })}
          </div>
        </>
      ) : (
        <p className="panel__status">Disk space info unavailable.</p>
      )}
    </div>
  );

  return (
    <section className="panel dash-node-card">
      <header className="dash-node-card__header">
        <div className="dash-node-card__titlewrap">
          <h3 className="dash-node-card__title">{nodeName}</h3>
        </div>
        {status?.nodeID ? <NodeId id={status.nodeID} /> : null}
      </header>

      {error ? <p className="panel__error">{error}</p> : null}
      {isLoading && !details ? <p className="panel__status">Loading…</p> : null}

      {details ? (
        <div className="dash-node-card__body">
          <StatusBlock details={details} />

          <div className="dash-node-trio">
            {renderBandwidthCard()}
            {renderStorageCard()}
            {renderDiskCard()}
          </div>

          <div className="dash-sat-grid dash-sat-grid--tight">
            {status?.satellites && status.satellites.length > 0 ? (
              status.satellites.map((sat) => {
                const audit = stats?.audits?.find((entry) => entry.satelliteName === sat.url);
                return <SatelliteComponent key={sat.id} satellite={sat} audit={audit} />;
              })
            ) : (
              <p className="panel__status">No satellites reported.</p>
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
};

export default NodePanel;
