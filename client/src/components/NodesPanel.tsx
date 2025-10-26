import type { FC } from "react";

import useNodes from "../hooks/useNodes";

const NodesPanel: FC = () => {
  const { nodes, isLoading, error, refresh } = useNodes();

  const displayNodes = [{ name: "All" }, ...nodes];

  return (
    <section className="panel panel--top">
      <header className="panel__header">
        <div>
          <h2 className="panel__title">Monitor STORJ Nodes by hwm.land</h2>
          <p className="panel__subtitle">Connected storagenodes available for monitoring.</p>
        </div>
        <button className="button" type="button" onClick={() => refresh()} disabled={isLoading}>
          {isLoading ? "Refreshing…" : "Refresh"}
        </button>
      </header>

      {error ? <p className="panel__error">{error}</p> : null}

      <div className="panel__body">
        {isLoading && nodes.length === 0 ? <p className="panel__status">Loading nodes…</p> : null}
        <div className="nodes-grid">
          {displayNodes.length === 1 && !isLoading ? (
            <p className="panel__empty">No nodes configured.</p>
          ) : (
            displayNodes.map((node) => (
              <article key={node.name} className="node-card">
                <h3 className="node-card__name">{node.name}</h3>
              </article>
            ))
          )}
        </div>
      </div>
    </section>
  );
};

export default NodesPanel;
