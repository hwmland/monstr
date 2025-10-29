import type { FC } from "react";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import useNodes from "../hooks/useNodes";
import usePanelVisibilityStore from "../store/usePanelVisibility";
import useSelectedNodesStore from "../store/useSelectedNodes";

const NodesPanel: FC = () => {
  const { nodes, isLoading, error, refresh } = useNodes();
  const { panels, togglePanel } = usePanelVisibilityStore();
  const [isPanelPickerOpen, setPanelPickerOpen] = useState(false);
  const pickerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!isPanelPickerOpen) {
      return;
    }

    const handleClickOutside = (event: MouseEvent) => {
      if (!pickerRef.current) {
        return;
      }
      if (event.target instanceof Node && pickerRef.current.contains(event.target)) {
        return;
      }
      setPanelPickerOpen(false);
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isPanelPickerOpen]);
  const { toggleNode, isSelected } = useSelectedNodesStore();

  const availableNodeNames = nodes.map((node) => node.name);
  const displayNodes = [{ name: "All" }, ...nodes];

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
          <button
            className="button button--ghost"
            type="button"
            onClick={() => setPanelPickerOpen((value) => !value)}
          >
            Panels
          </button>
          <button className="button" type="button" onClick={() => refresh()} disabled={isLoading}>
            {isLoading ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </header>

      {isPanelPickerOpen
        ? createPortal(
            <div
              className="panel-picker-overlay"
              onMouseDown={() => setPanelPickerOpen(false)}
              role="dialog"
              aria-modal="true"
            >
              <div className="panel-picker" ref={pickerRef} onMouseDown={(e) => e.stopPropagation()}>
                <label className="panel-picker__item">
                  <input
                    type="checkbox"
                    checked={panels.satelliteTraffic ?? true}
                    onChange={() => togglePanel("satelliteTraffic")}
                  />
                  <span>Satellite Traffic</span>
                </label>
                <label className="panel-picker__item">
                  <input
                    type="checkbox"
                    checked={panels.actualPerformance ?? true}
                    onChange={() => togglePanel("actualPerformance")}
                  />
                  <span>Actual Performance</span>
                </label>
                <label className="panel-picker__item">
                  <input
                    type="checkbox"
                    checked={panels.dataDistribution ?? true}
                    onChange={() => togglePanel("dataDistribution")}
                  />
                  <span>Data Size Distribution</span>
                </label>
                <label className="panel-picker__item">
                  <input
                    type="checkbox"
                    checked={panels.reputations ?? true}
                    onChange={() => togglePanel("reputations")}
                  />
                  <span>Reputations</span>
                </label>
              </div>
            </div>,
            document.body,
          )
        : null}

      {error ? <p className="panel__error">{error}</p> : null}

      <div className="panel__body">
        {isLoading && nodes.length === 0 ? <p className="panel__status">Loading nodes…</p> : null}
        <div className="nodes-grid">
          {displayNodes.map((node) => {
            const selected = isSelected(node.name);
            return (
              <article
                key={node.name}
                className={`node-card${selected ? " node-card--selected" : ""}`}
                onClick={() => handleSelection(node.name)}
                role="button"
                tabIndex={0}
                aria-pressed={selected}
                onKeyDown={(event) => {
                  if (event.key === " " || event.key === "Enter") {
                    event.preventDefault();
                    handleSelection(node.name);
                  }
                }}
              >
                <span className="node-card__name">{node.name}</span>
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
