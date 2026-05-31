import type { FC } from "react";
import { useMemo } from "react";
import PanelControls from "../../PanelControls";
import PanelControlsCombo from "../../PanelControlsCombo";
import useHashstoreFiltersStore from "../../../store/useHashstoreFilters";
import { SATELLITE_ID_TO_NAME } from "../../../constants/satellites";
import type { HashstoreTimeRange } from "../../../types";

const TIME_RANGE_OPTIONS: { value: string; label: string }[] = [
  { value: "30d", label: "30 days" },
  { value: "90d", label: "90 days" },
  { value: "1y", label: "1 year" },
  { value: "5y", label: "5 years" },
];

const STORE_OPTIONS: { value: string; label: string }[] = [
  { value: "__all__", label: "All stores" },
  { value: "s0", label: "s0" },
  { value: "s1", label: "s1" },
];

const HashstoreFilterBar: FC = () => {
  const timeRange = useHashstoreFiltersStore((s) => s.timeRange);
  const satelliteId = useHashstoreFiltersStore((s) => s.satelliteId);
  const store = useHashstoreFiltersStore((s) => s.store);
  const setTimeRange = useHashstoreFiltersStore((s) => s.setTimeRange);
  const setSatelliteId = useHashstoreFiltersStore((s) => s.setSatelliteId);
  const setStore = useHashstoreFiltersStore((s) => s.setStore);

  const satelliteOptions = useMemo(() => {
    const opts: { value: string; label: string }[] = [{ value: "__all__", label: "All satellites" }];
    for (const [id, name] of Object.entries(SATELLITE_ID_TO_NAME)) {
      opts.push({ value: id, label: name });
    }
    return opts;
  }, []);

  return (
    <PanelControls
      ariaLabel="Hashstore filters"
      buttons={[
        <PanelControlsCombo
          key="satellite"
          options={satelliteOptions}
          activeValue={satelliteId ?? "__all__"}
          onSelect={(v) => setSatelliteId(v === "__all__" ? null : v)}
          ariaLabel="Satellite filter"
        />,
        <PanelControlsCombo
          key="store"
          options={STORE_OPTIONS}
          activeValue={store ?? "__all__"}
          onSelect={(v) => setStore(v === "__all__" ? null : v)}
          ariaLabel="Store filter"
        />,
        <PanelControlsCombo
          key="timeRange"
          options={TIME_RANGE_OPTIONS}
          activeValue={timeRange}
          onSelect={(v) => setTimeRange(v as HashstoreTimeRange)}
          ariaLabel="Time range"
        />,
      ]}
    />
  );
};

export default HashstoreFilterBar;
