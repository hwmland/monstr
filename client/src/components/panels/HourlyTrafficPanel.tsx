import type { FC } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import usePanelVisibilityStore from "../../store/usePanelVisibility";
import { fetchIntervalTransfers } from "../../services/apiClient";
import createRequestDeduper from "../../utils/requestDeduper";
import useSelectedNodesStore from "../../store/useSelectedNodes";
import PanelSubtitle from "../PanelSubtitle";
import PanelHeader from "../PanelHeader";
import PanelControls, { getStoredSelection } from "../PanelControls";
import PanelControlsButton from "../PanelControlsButton";
import { pickRatePresentation, formatRateValue, formatSizeValue, pickSizePresentation } from "../../utils/units";
import { use24hTime } from "../../utils/time";
import { COLOR_STATUS_GREEN, COLOR_STATUS_YELLOW, COLOR_STATUS_RED } from "../../constants/colors";

interface HourlyBucket {
  bucketStart: string; // ISO
  bucketEnd: string; // ISO
  sizeDlSuccNor: number;
  sizeUlSuccNor: number;
  sizeDlFailNor: number;
  sizeUlFailNor: number;
  sizeDlSuccRep: number;
  sizeUlSuccRep: number;
  sizeDlFailRep: number;
  sizeUlFailRep: number;
  countDlSuccNor: number;
  countUlSuccNor: number;
  countDlFailNor: number;
  countUlFailNor: number;
  countDlSuccRep: number;
  countUlSuccRep: number;
  countDlFailRep: number;
  countUlFailRep: number;
}

type Mode = "speed" | "size";
const MODE_VALUES = ["speed", "size"] as const satisfies readonly Mode[];

const HourlyTrafficPanel: FC = () => {
  const { isVisible } = usePanelVisibilityStore();
  const show = isVisible("hourlyTraffic");
  if (!show) return null;

  const { selected: selectedNodes } = useSelectedNodesStore();
  const [data, setData] = useState<HourlyBucket[] | null>(null);
  const [startTime, setStartTime] = useState<string | null>(null);
  const [endTime, setEndTime] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const deduperRef = useRef(createRequestDeduper());
  const [mode, setMode] = useState<Mode>(() =>
    getStoredSelection<Mode>("monstr.panel.HourlyTraffic.mode", MODE_VALUES, "speed"),
  );

  const load = async () => {
    const deduper = deduperRef.current;
    const requestNodes = selectedNodes.includes("All") ? [] : selectedNodes;
    if (deduper.isDuplicate(requestNodes, 1000)) return;

    setLoading(true);
    setError(null);
    try {
      const res = await fetchIntervalTransfers(requestNodes, "1h", 9);
      setStartTime(res.startTime ?? null);
      setEndTime(res.endTime ?? null);
      setData(Array.isArray(res.buckets) ? res.buckets : []);
    } catch (err: any) {
      setError(err?.message ?? String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedNodes]);

  // use centralized helper to compute effective 24h/12h behavior and react to changes
  const [system24, setSystem24] = useState<boolean>(() => use24hTime());

  useEffect(() => {
    const handler = () => {
      setSystem24(use24hTime());
    };
    window.addEventListener("pref_time_24h_changed", handler as EventListener);
    return () => window.removeEventListener("pref_time_24h_changed", handler as EventListener);
  }, []);

  const rows = useMemo(() => {
    if (!data) return [];

    const mapped = data.map((b) => {
      const bs = new Date(b.bucketStart);
      const be = new Date(b.bucketEnd);

      // format hour-only (no minutes) and respect hour12 preference
      const hourLabel = bs.toLocaleTimeString([], { hour: "2-digit", hour12: !system24 });
      // compute success rates for DL and UL
      const dlSuccess = (b.countDlSuccNor ?? 0) + (b.countDlSuccRep ?? 0);
      const dlTotal = dlSuccess + (b.countDlFailNor ?? 0) + (b.countDlFailRep ?? 0);
      const dlRatePct = dlTotal > 0 ? (dlSuccess / dlTotal) * 100 : 0;

      const ulSuccess = (b.countUlSuccNor ?? 0) + (b.countUlSuccRep ?? 0);
      const ulTotal = ulSuccess + (b.countUlFailNor ?? 0) + (b.countUlFailRep ?? 0);
      const ulRatePct = ulTotal > 0 ? (ulSuccess / ulTotal) * 100 : 0;

      // download/upload speed: sum of successful download bytes / bucket seconds
      const dlBytes = (b.sizeDlSuccNor ?? 0) + (b.sizeDlSuccRep ?? 0);
      const ulBytes = (b.sizeUlSuccNor ?? 0) + (b.sizeUlSuccRep ?? 0);
      const seconds = Math.max(1, Math.floor((be.getTime() - bs.getTime()) / 1000));
      const dlBps = dlBytes / seconds;
      const ulBps = ulBytes / seconds;

      const dlRate = pickRatePresentation(dlBps * 8); // bits per second
      const ulRate = pickRatePresentation(ulBps * 8);
      const dlSize = pickSizePresentation(dlBytes);
      const ulSize = pickSizePresentation(ulBytes);

      return {
        bucketStart: bs,
        bucketEnd: be,
        hourLabel,
        dlRatePct,
        ulRatePct,
        dlRate,
        ulRate,
        dlSize,
        ulSize,
      };
    });

    // sort descending by bucketStart
    mapped.sort((a, b) => b.bucketStart.getTime() - a.bucketStart.getTime());
    return mapped;
  }, [data, system24]);

  const resolveSuccessColor = (percent: number): string => {
    if (percent < 80) {
      return COLOR_STATUS_RED;
    }
    if (percent >= 90) {
      return COLOR_STATUS_GREEN;
    }
    return COLOR_STATUS_YELLOW;
  };

  return (
    <section className="panel">
      <PanelHeader
        title="Hourly Traffic"
        subtitle={<PanelSubtitle windowStart={startTime} windowEnd={endTime} selectedNodes={selectedNodes} />}
        onRefresh={load}
        isRefreshing={loading}
        controls={(
          <PanelControls
            ariaLabel="Display mode"
            storageKey="monstr.panel.HourlyTraffic.mode"
            buttons={[
              <PanelControlsButton key="speed" active={mode === "speed"} onClick={() => setMode("speed")} content="Speed" />,
              <PanelControlsButton key="size" active={mode === "size"} onClick={() => setMode("size")} content="Size" />,
            ]}
          />
        )}
      />

      <div className="panel__body">
        {error ? <p className="panel__error">{error}</p> : null}
        {!data || data.length === 0 ? (
          <p className="panel__empty">No transfer data for the selected window.</p>
        ) : (
          <div className="hourly-grid">
            <table className="table">
              <thead>
                <tr>
                  <th className="col-time">Time</th>
                  <th className="col-dlpct">DL %</th>
                  <th className="col-ulpct">UL %</th>
                  <th className="col-dlspeed">{mode === "size" ? "DL data" : "DL speed"}</th>
                  <th className="col-ulspeed">{mode === "size" ? "UL data" : "UL speed"}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={String((r.bucketStart as Date).toISOString())}>
                    <td className="col-time">{r.hourLabel}</td>
                    <td className="col-dlpct" style={{ color: resolveSuccessColor(r.dlRatePct) }}>{r.dlRatePct.toFixed(2)} %</td>
                    <td className="col-ulpct" style={{ color: resolveSuccessColor(r.ulRatePct) }}>{r.ulRatePct.toFixed(2)} %</td>
                    <td className="col-dlspeed">{mode === "speed" ? `${formatRateValue(r.dlRate.value)} ${r.dlRate.unit}` : `${formatSizeValue(r.dlSize.value)} ${r.dlSize.unit}`}</td>
                    <td className="col-ulspeed">{mode === "speed" ? `${formatRateValue(r.ulRate.value)} ${r.ulRate.unit}` : `${formatSizeValue(r.ulSize.value)} ${r.ulSize.unit}`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
};

export default HourlyTrafficPanel;
