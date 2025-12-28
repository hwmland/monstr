import type { DashAuditEntry, DashSatellite } from "../types";
import NodeId from "./NodeId";
import { FaExclamationTriangle, FaCheckCircle } from "react-icons/fa";

interface SatelliteComponentProps {
  satellite: DashSatellite;
  audit?: DashAuditEntry;
}

const formatScore = (score: number | null) => (score === null ? "N/A" : `${(score * 100).toFixed(2)}%`);

const scoreColor = (score: number | null) => {
  if (score === null) return "var(--color-text-muted)";
  if (score < 0.96) return "#f87171";
  if (score < 0.99) return "#fbbf24";
  return "var(--color-success)";
};

const SatelliteComponent = ({ satellite, audit }: SatelliteComponentProps) => {
  const globalScore = audit ? Math.min(audit.suspensionScore ?? 0, audit.auditScore ?? 0, audit.onlineScore ?? 0) : 0;
  const suspensionScore = audit?.suspensionScore ?? null;
  const onlineScore = audit?.onlineScore ?? null;
  const auditScore = audit?.auditScore ?? null;
  const iconColor = scoreColor(globalScore);
  const Icon = globalScore !== null && globalScore >= 0.99 ? FaCheckCircle : FaExclamationTriangle;

  return (
    <div className="dash-sat-card">
      <div className="dash-sat-card__title" style={{ alignItems: "center", gap: "0.45rem", flexDirection: "row", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", flex: 1 }}>
          <Icon style={{ color: iconColor, fontSize: "0.7rem" }} />
          <div className="dash-sat-card__name" style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {satellite.url}
          </div>
        </div>
        <NodeId id={satellite.id} />
      </div>
      <div className="dash-sat-inline">
        <div className="dash-sat-inline__col">
          <span className="dash-sat-inline__label">Suspension</span>
          <span className="dash-sat-inline__value" style={{ color: scoreColor(suspensionScore) }}>
            {formatScore(suspensionScore)}
          </span>
        </div>
        <div className="dash-sat-inline__col">
          <span className="dash-sat-inline__label">Audit</span>
          <span className="dash-sat-inline__value" style={{ color: scoreColor(auditScore) }}>
            {formatScore(auditScore)}
          </span>
        </div>
        <div className="dash-sat-inline__col">
          <span className="dash-sat-inline__label">Online</span>
          <span className="dash-sat-inline__value" style={{ color: scoreColor(onlineScore) }}>
            {formatScore(onlineScore)}
          </span>
        </div>
      </div>
    </div>
  );
};

export default SatelliteComponent;
