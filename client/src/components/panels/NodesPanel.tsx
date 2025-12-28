import { useEffect, useState, type FC, type MouseEvent } from "react";
import { createPortal } from "react-dom";
import { FaExclamationTriangle } from "react-icons/fa";

import Settings from "../Settings";

import useNodes from "../../hooks/useNodes";
import useSelectedNodesStore from "../../store/useSelectedNodes";
import { SATELLITE_ID_TO_NAME } from "../../constants/satellites";
import { fetchIp24Status } from "../../services/apiClient";
import type { IP24StatusEntry, NodeInfo } from "../../types";

type DisplayNode = NodeInfo & { isAggregate?: boolean };

type VettingEntry = {
  id: string;
  label: string;
  isVetted: boolean;
  value: string | null;
};

const VETTING_DATE_FORMATTER = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

const sanitizeForId = (value: string): string =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "node";

const formatVettingDate = (value: string): string => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return VETTING_DATE_FORMATTER.format(parsed);
};

const getVettingEntries = (vetting?: Record<string, string | null>): VettingEntry[] => {
  if (!vetting) {
    return [];
  }

  return Object.entries(vetting)
    .filter(([satelliteId]) => Boolean(satelliteId))
    .map(([satelliteId, timestamp]) => {
      const label = SATELLITE_ID_TO_NAME[satelliteId] ?? satelliteId;
      if (!timestamp) {
        return { id: satelliteId, label, isVetted: false, value: null };
      }

      return {
        id: satelliteId,
        label,
        isVetted: true,
        value: formatVettingDate(timestamp),
      };
    })
    .sort((a, b) => a.label.localeCompare(b.label));
};

const AUTO_REFRESH_INTERVAL_MS = 10 * 60 * 1000;

const NodesPanel: FC = () => {
  const { nodes, isLoading, error, refresh } = useNodes();
  const { toggleNode, isSelected } = useSelectedNodesStore();
  const [suppressedTooltipNode, setSuppressedTooltipNode] = useState<string | null>(null);
  const [tooltipAnchor, setTooltipAnchor] = useState<DOMRect | null>(null);
  const [activeTooltipId, setActiveTooltipId] = useState<string | null>(null);
  const [ip24Level, setIp24Level] = useState<"none" | "warn" | "error">("none");
  const [ip24Message, setIp24Message] = useState<string>("");
  const [ip24Entries, setIp24Entries] = useState<Array<{ ip: string; entry: IP24StatusEntry }>>([]);
  const [ip24TooltipAnchor, setIp24TooltipAnchor] = useState<DOMRect | null>(null);
  const [ip24TooltipVisible, setIp24TooltipVisible] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }
    const timer = window.setInterval(() => {
      void refresh();
    }, AUTO_REFRESH_INTERVAL_MS);
    return () => {
      window.clearInterval(timer);
    };
  }, [refresh]);

  useEffect(() => {
    let isMounted = true;

    const computeStatus = (entries: IP24StatusEntry[]) => {
      if (!entries.length) {
        setIp24Level("none");
        setIp24Message("");
        return;
      }
      const hasError = entries.some((entry) => entry.valid === false);
      const hasWarn = entries.some((entry) => entry.instances !== null && entry.instances !== entry.expectedInstances);
      if (hasError) {
        setIp24Level("error");
        setIp24Message("IP24 check failed for one or more IPs");
      } else if (hasWarn) {
        setIp24Level("warn");
        setIp24Message("IP24 expected vs actual instances differ");
      } else {
        setIp24Level("none");
        setIp24Message("");
      }
    };

    const fetchIp24 = async () => {
      try {
        const data = await fetchIp24Status();
        if (!isMounted) return;
        const entries = data
          ? Object.entries(data).map(([ip, entry]) => ({ ip, entry }))
          : [];
        setIp24Entries(entries);
        computeStatus(entries.map((item) => item.entry));
      } catch (err) {
        if (!isMounted) return;
        setIp24Level("error");
        setIp24Message("IP24 check failed to fetch");
        setIp24Entries([]);
      }
    };

    void fetchIp24();
    const timer = window.setInterval(() => {
      void fetchIp24();
    }, AUTO_REFRESH_INTERVAL_MS);

    return () => {
      isMounted = false;
      window.clearInterval(timer);
    };
  }, []);

  const availableNodeNames = nodes.map((node) => node.name);
  const displayNodes: DisplayNode[] = [
    { name: "All", path: "", isAggregate: true },
    ...nodes.map((node) => ({ ...node, isAggregate: false })),
  ];

  const handleSelection = (name: string) => {
    toggleNode(name, availableNodeNames);
  };

  return (
    <section className="panel panel--top">
      <header className="panel__header">
        <div>
          <h2 className="panel__title">Monitor STORJ Nodes by hwm.land</h2>
          <p className="panel__subtitle">Connected storagenodes available for monitoring.</p>
        </div>
        <div className="panel__actions">
          {ip24Level !== "none" ? (
            <span
              className={`nodes-ip24-indicator nodes-ip24-indicator--${ip24Level}`}
              aria-label={ip24Message || "IP24 status"}
              tabIndex={0}
              onMouseEnter={(event) => {
                const rect = event.currentTarget.getBoundingClientRect();
                setIp24TooltipAnchor(rect);
                setIp24TooltipVisible(true);
              }}
              onMouseLeave={() => {
                setIp24TooltipVisible(false);
                setIp24TooltipAnchor(null);
              }}
              onFocus={(event) => {
                const rect = event.currentTarget.getBoundingClientRect();
                setIp24TooltipAnchor(rect);
                setIp24TooltipVisible(true);
              }}
              onBlur={() => {
                setIp24TooltipVisible(false);
                setIp24TooltipAnchor(null);
              }}
            >
              <FaExclamationTriangle aria-hidden="true" />
            </span>
          ) : null}
          {ip24TooltipVisible && ip24TooltipAnchor
            ? createPortal(
                <div
                  className="nodes-ip24-tooltip"
                  role="note"
                  style={{
                    position: "fixed",
                    top: `${ip24TooltipAnchor.bottom + 8}px`,
                    left: `${ip24TooltipAnchor.left + ip24TooltipAnchor.width / 2}px`,
                    transform: "translate(-50%, 0)",
                  }}
                >
                  <div className="nodes-ip24-tooltip__title">IP24 status</div>
                  {ip24Entries.length === 0 ? (
                    <p className="nodes-ip24-tooltip__empty">No IP24 entries</p>
                  ) : (
                    <table className="nodes-ip24-tooltip__table">
                      <thead>
                        <tr>
                          <th>IP</th>
                          <th>Expected</th>
                          <th>Instances</th>
                        </tr>
                      </thead>
                      <tbody>
                        {ip24Entries.map(({ ip, entry }) => {
                          const isError = entry.valid === false;
                          const isWarn = entry.instances !== null && entry.instances !== entry.expectedInstances;
                          const rowClass = [
                            "nodes-ip24-row",
                            isError ? "nodes-ip24-row--error" : "",
                            !isError && isWarn ? "nodes-ip24-row--warn" : "",
                          ]
                            .filter(Boolean)
                            .join(" ");

                          return (
                            <tr key={ip} className={rowClass}>
                              <td>{ip}</td>
                              <td>{entry.expectedInstances}</td>
                              <td>{entry.valid === false ? "obsolete" : entry.instances ?? "—"}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  )}
                </div>,
                document.body,
              )
            : null}
          <Settings />
          <button className="button" type="button" onClick={() => refresh()} disabled={isLoading}>
            {isLoading ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </header>

      {/* Settings panel picker is rendered by the Settings component */}

      {error ? <p className="panel__error">{error}</p> : null}

      <div className="panel__body">
        {isLoading && nodes.length === 0 ? <p className="panel__status">Loading nodes…</p> : null}
        <div className="nodes-grid">
          {displayNodes.map((node) => {
            const selected = isSelected(node.name);
            const vettingEntries = node.isAggregate ? [] : getVettingEntries(node.vetting);
            const hasVetting = vettingEntries.length > 0;
            const hasUnvetted = vettingEntries.some((entry) => !entry.isVetted);
            const showVettingBar = hasVetting && hasUnvetted;
            const tooltipHidden = suppressedTooltipNode === node.name;
            const tooltipId = hasVetting ? `node-vetting-${sanitizeForId(node.name)}` : undefined;
            const cardClass = [
              "node-card",
              selected ? "node-card--selected" : "",
              hasVetting ? "node-card--has-vetting" : "",
            ]
              .filter(Boolean)
              .join(" ");

            const handleClick = (event: MouseEvent<HTMLElement>) => {
              handleSelection(node.name);
              if (event.detail > 0) {
                (event.currentTarget as HTMLElement).blur();
                setSuppressedTooltipNode(node.name);
                setActiveTooltipId(null);
              }
            };

            const handleMouseEnter = (event: MouseEvent<HTMLElement>) => {
              if (!hasVetting || tooltipHidden) {
                return;
              }
              const rect = event.currentTarget.getBoundingClientRect();
              setTooltipAnchor(rect);
              setActiveTooltipId(tooltipId ?? null);
            };

            return (
              <article
                key={node.name}
                className={cardClass}
                onClick={handleClick}
                onMouseEnter={handleMouseEnter}
                role="button"
                tabIndex={0}
                aria-pressed={selected}
                aria-describedby={tooltipId}
                onFocus={() => {
                  setSuppressedTooltipNode((prev) => (prev === node.name ? null : prev));
                  setTooltipAnchor(null);
                  setActiveTooltipId(null);
                }}
                onMouseLeave={() => {
                  setSuppressedTooltipNode((prev) => (prev === node.name ? null : prev));
                  setTooltipAnchor(null);
                  setActiveTooltipId(null);
                }}
                onKeyDown={(event) => {
                  if (event.key === " " || event.key === "Enter") {
                    event.preventDefault();
                    handleSelection(node.name);
                    setTooltipAnchor(null);
                    setActiveTooltipId(null);
                  }
                }}
              >
                <div className="node-card__label">
                  <span className="node-card__name">{node.name}</span>
                  {showVettingBar ? (
                    <div className="node-card__vetting-bar" aria-hidden="true">
                      {vettingEntries.map((entry) => (
                        <span
                          key={`${entry.id}-segment`}
                          className={`node-card__vetting-bar-segment${
                            entry.isVetted
                              ? " node-card__vetting-bar-segment--ok"
                              : " node-card__vetting-bar-segment--pending"
                          }`}
                          title={`${entry.label}: ${entry.isVetted ? "Vetted" : "Not vetted"}`}
                        />
                      ))}
                    </div>
                  ) : null}
                </div>
                {hasVetting && tooltipId === activeTooltipId && tooltipAnchor
                  ? createPortal(
                      <div
                        className="node-card__vetting-tooltip"
                        id={tooltipId}
                        role="note"
                        style={{
                          position: "fixed",
                          top: `${tooltipAnchor.bottom + 8}px`,
                          left: `${tooltipAnchor.left + tooltipAnchor.width / 2}px`,
                          transform: "translate(-50%, 0)",
                        }}
                      >
                        <p className="node-card__vetting-title">Vetting status</p>
                        <ul className="node-card__vetting-list">
                          {vettingEntries.map((entry) => (
                            <li key={entry.id} className="node-card__vetting-row">
                              <span className="node-card__vetting-satellite">{entry.label}</span>
                              <span
                                className={`node-card__vetting-status${
                                  entry.isVetted && entry.value
                                    ? ""
                                    : " node-card__vetting-status--pending"
                                }`}
                              >
                                {entry.isVetted && entry.value ? entry.value : "Not vetted"}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>,
                      document.body,
                    )
                  : null}
              </article>
            );
          })}
        </div>
        {nodes.length === 0 && !isLoading ? (
          <p className="panel__empty">No nodes configured.</p>
        ) : null}
      </div>
    </section>
  );
};

export default NodesPanel;
