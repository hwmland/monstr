import type { FC } from "react";

import PanelHeader from "../../PanelHeader";
import PanelSubtitle from "../../PanelSubtitle";
import HashstoreFilterBar from "./HashstoreFilterBar";
import HashstoreStoragePanel from "./HashstoreStoragePanel";
import HashstoreCompactionPanel from "./HashstoreCompactionPanel";
import HashstoreHealthPanel from "./HashstoreHealthPanel";
import HashstoreActivityPanel from "./HashstoreActivityPanel";
import HashstoreDiagnosticsPanel from "./HashstoreDiagnosticsPanel";
import useHashstoreSeries from "../../../hooks/useHashstoreSeries";
import useSelectedNodesStore from "../../../store/useSelectedNodes";
import usePanelVisibilityStore from "../../../store/usePanelVisibility";

const HashstorePanel: FC = () => {
  const { isVisible } = usePanelVisibilityStore();
  const showStorage = isVisible("hashstoreStorage");
  const showCompaction = isVisible("hashstoreCompaction");
  const showHealth = isVisible("hashstoreHealth");
  const showActivity = isVisible("hashstoreActivity");
  const showDiagnostics = isVisible("hashstoreDiagnostics");

  const anyVisible = showStorage || showCompaction || showHealth || showActivity || showDiagnostics;

  const { data, isLoading, error, refresh } = useHashstoreSeries({
    refreshIntervalMs: 300_000,
    enabled: anyVisible,
  });
  const selected = useSelectedNodesStore((s) => s.selected);

  if (!anyVisible) return null;

  return (
    <section className="panel hashstore-panel">
      <PanelHeader
        title="Hashstore"
        subtitle={<PanelSubtitle windowStart={data?.startTime} windowEnd={data?.endTime} selectedNodes={selected} />}
        onRefresh={refresh}
        isRefreshing={isLoading}
        controls={<HashstoreFilterBar />}
      />
      {error ? (
        <div className="panel__error">{error}</div>
      ) : (
        <div className="hashstore-subpanels">
          {showStorage ? <HashstoreStoragePanel data={data} /> : null}
          {showCompaction ? <HashstoreCompactionPanel data={data} /> : null}
          {showHealth ? <HashstoreHealthPanel data={data} /> : null}
          {showActivity ? <HashstoreActivityPanel data={data} /> : null}
          {showDiagnostics ? <HashstoreDiagnosticsPanel data={data} /> : null}
        </div>
      )}
    </section>
  );
};

export default HashstorePanel;
