import ActualPerformancePanel from "../components/ActualPerformancePanel";
import NodesPanel from "../components/NodesPanel";
import ReputationsPanel from "../components/ReputationsPanel";
import SatelliteTrafficPanel from "../components/SatelliteTrafficPanel";
import DataSizeDistributionPanel from "../components/DataSizeDistributionPanel";
import HourlyTrafficPanel from "../components/HourlyTrafficPanel";
import useTransfersActual from "../hooks/useActualPerformancePanel";
import usePanelVisibilityStore from "../store/usePanelVisibility";

const HomePage = () => {
  const { isVisible } = usePanelVisibilityStore();
  const showSatelliteTraffic = isVisible("satelliteTraffic");
  const showActualPerformance = isVisible("actualPerformance");
  const showHourlyTraffic = isVisible("hourlyTraffic");
  const shouldLoadTransfers = showSatelliteTraffic || showActualPerformance;
  const shouldRenderTransfers = showSatelliteTraffic || showActualPerformance || showHourlyTraffic;

  const { data, aggregated, isLoading, error, refresh, selectedNodes } = useTransfersActual({
    enabled: shouldLoadTransfers,
  });

  return (
    <div className="page">
      <NodesPanel />
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

          {isVisible("dataDistribution") ? (
            <DataSizeDistributionPanel selectedNodes={selectedNodes} />
          ) : null}
        </>
      ) : null}
      {isVisible("reputations") ? <ReputationsPanel /> : null}
    </div>
  );
};

export default HomePage;
