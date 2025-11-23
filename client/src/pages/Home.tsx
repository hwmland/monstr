import ActualPerformancePanel from "../components/panels/ActualPerformancePanel";
import LongTermPanel from "../components/panels/LongTermPanel";
import NodesPanel from "../components/panels/NodesPanel";
import ReputationsPanel from "../components/panels/ReputationsPanel";
import SatelliteTrafficPanel from "../components/panels/SatelliteTrafficPanel";
import DataSizeDistributionPanel from "../components/panels/DataSizeDistributionPanel";
import HourlyTrafficPanel from "../components/panels/HourlyTrafficPanel";
import AccumulatedTrafficPanel from "../components/panels/AccumulatedTrafficPanel";
import useTransfersActual from "../hooks/useActualPerformancePanel";
import usePanelVisibilityStore from "../store/usePanelVisibility";

const HomePage = () => {
  const { isVisible } = usePanelVisibilityStore();
  const showSatelliteTraffic = isVisible("satelliteTraffic");
  const showActualPerformance = isVisible("actualPerformance");
  const showHourlyTraffic = isVisible("hourlyTraffic");
  const showDataSizeDistribution = isVisible("dataDistribution");
  const showAccumulatedTraffic = isVisible("accumulatedTraffic");
  const showLongTerm = isVisible("longTerm");
  const shouldLoadTransfers = showSatelliteTraffic || showActualPerformance;
  const shouldRenderTransfers = showSatelliteTraffic || showActualPerformance || showHourlyTraffic;

  const { data, aggregated, isLoading, error, refresh, selectedNodes } = useTransfersActual({
    enabled: shouldLoadTransfers,
  });

  return (
    <div className="page">
      <NodesPanel />
      {showLongTerm ? <LongTermPanel /> : null}
      {shouldRenderTransfers ? (
        <>
          <div className="transfer-panels">
            {showSatelliteTraffic ? (
              <SatelliteTrafficPanel
                data={data}
                isLoading={isLoading}
                error={error}
                refresh={refresh}
                selectedNodes={selectedNodes}
              />
            ) : null}
            {showHourlyTraffic ? <HourlyTrafficPanel /> : null}

            {showActualPerformance ? (
              <ActualPerformancePanel
                aggregated={aggregated}
                isLoading={isLoading}
                error={error}
                refresh={refresh}
                selectedNodes={selectedNodes}
              />
            ) : null}
          </div>
        </>
      ) : null}

      {(showDataSizeDistribution || showAccumulatedTraffic) ? (
        <div className="distribution-panels">
          {showDataSizeDistribution ? <DataSizeDistributionPanel selectedNodes={selectedNodes} /> : null}
          {showAccumulatedTraffic ? <AccumulatedTrafficPanel selectedNodes={selectedNodes} /> : null}
        </div>
      ) : null}
      {isVisible("reputations") ? <ReputationsPanel /> : null}
    </div>
  );
};

export default HomePage;
