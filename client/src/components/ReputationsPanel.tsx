import type { FC } from "react";

import { COLOR_STATUS_GREEN, COLOR_STATUS_RED, COLOR_STATUS_YELLOW } from "../constants/colors";
import useReputationsPanel from "../hooks/useReputationsPanel";
import type { SatelliteReputation } from "../types";

const formatScore = (value: number) => `${(value * 100).toFixed(2)}%`;

const getScoreColor = (value: number) => {
  const percent = value * 100;
  if (percent < 96) {
    return COLOR_STATUS_RED;
  }
  if (percent < 99) {
    return COLOR_STATUS_YELLOW;
  }
  return COLOR_STATUS_GREEN;
};

const buildTooltip = (satellite: SatelliteReputation) => {
  const localTimestamp = new Date(satellite.timestamp).toLocaleString();
  return `${localTimestamp} • ${satellite.auditsSuccess} / ${satellite.auditsTotal} audits`;
};

const ReputationsPanel: FC = () => {
  const { reputations, isLoading, error, refresh, selectedNodes } = useReputationsPanel();

  const subtitle = selectedNodes.length === 0 ? "Showing all nodes" : `Selected nodes: ${selectedNodes.join(", ")}`;
  const hasRecords = reputations.some((item) => item.satellites.length > 0);

  return (
    <section className="panel">
      <header className="panel__header">
        <div>
          <h2 className="panel__title">Reputations</h2>
          <p className="panel__subtitle">{subtitle}</p>
        </div>
        <button className="button" type="button" onClick={() => refresh()} disabled={isLoading}>
          {isLoading ? "Loading…" : "Refresh"}
        </button>
      </header>

      {error ? <p className="panel__error">{error}</p> : null}

      <div className="panel__body">
        {isLoading && !hasRecords ? <p className="panel__status">Loading reputation metrics…</p> : null}
        {!isLoading && reputations.length === 0 ? (
          <p className="panel__empty">No reputation data available.</p>
        ) : null}

        <div className="reputations-grid">
          {reputations.map((entry) => (
            <article key={entry.node || "__unknown"} className="reputation-card">
              <header className="reputation-card__header">
                <h3 className="reputation-card__title">{entry.node || "Unknown node"}</h3>
              </header>
              {entry.satellites.length === 0 ? (
                <p className="reputation-card__empty">No satellite reputation records.</p>
              ) : (
                <table className="reputation-table">
                  <thead>
                    <tr>
                      <th scope="col">Satellite</th>
                      <th scope="col">Audit</th>
                      <th scope="col">Online</th>
                      <th scope="col">Suspension</th>
                    </tr>
                  </thead>
                  <tbody>
                    {entry.satellites.map((satellite) => (
                      <tr
                        key={`${entry.node}-${satellite.satelliteId}`}
                        title={buildTooltip(satellite)}
                      >
                        <th scope="row">
                          {satellite.satelliteName || satellite.satelliteId || "—"}
                        </th>
                        <td>
                          <strong style={{ color: getScoreColor(satellite.scoreAudit) }}>
                            {formatScore(satellite.scoreAudit)}
                          </strong>
                        </td>
                        <td>
                          <strong style={{ color: getScoreColor(satellite.scoreOnline) }}>
                            {formatScore(satellite.scoreOnline)}
                          </strong>
                        </td>
                        <td>
                          <strong style={{ color: getScoreColor(satellite.scoreSuspension) }}>
                            {formatScore(satellite.scoreSuspension)}
                          </strong>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </article>
          ))}
        </div>
      </div>
    </section>
  );
};

export default ReputationsPanel;
