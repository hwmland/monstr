import type { FC } from "react";

import Settings from "./Settings";

import useNodes from "../hooks/useNodes";
import useSelectedNodesStore from "../store/useSelectedNodes";

const NodesPanel: FC = () => {
  const { nodes, isLoading, error, refresh } = useNodes();
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
