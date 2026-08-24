import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import createRequestDeduper from "../utils/requestDeduper";
import { fetchHashstoreSeries } from "../services/apiClient";
import useSelectedNodesStore from "../store/useSelectedNodes";
import useHashstoreFiltersStore from "../store/useHashstoreFilters";
import type { HashstoreSeriesResponse } from "../types";

interface UseHashstoreSeriesOptions {
  enabled?: boolean;
  refreshIntervalMs?: number;
}

interface UseHashstoreSeriesState {
  data: HashstoreSeriesResponse | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => void;
}

const useHashstoreSeries = (options: UseHashstoreSeriesOptions = {}): UseHashstoreSeriesState => {
  const { enabled = true, refreshIntervalMs = 300_000 } = options;
  const selected = useSelectedNodesStore((s) => s.selected);
  const timeRange = useHashstoreFiltersStore((s) => s.timeRange);
  const satelliteId = useHashstoreFiltersStore((s) => s.satelliteId);
  const store = useHashstoreFiltersStore((s) => s.store);

  const [data, setData] = useState<HashstoreSeriesResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);
  const deduperRef = useRef(createRequestDeduper());

  const requestNodes = useMemo(() => {
    if (selected.includes("All")) return [] as string[];
    return selected;
  }, [selected]);

  const cacheKey = useMemo(
    () => JSON.stringify([requestNodes, timeRange, satelliteId, store]),
    [requestNodes, timeRange, satelliteId, store],
  );

  useEffect(() => {
    let isCurrent = true;

    if (!enabled) {
      setIsLoading(false);
      setError(null);
      return () => { isCurrent = false; };
    }

    const load = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const deduper = deduperRef.current;
        const response = await deduper.coalesce(
          [cacheKey],
          () => fetchHashstoreSeries(requestNodes, timeRange, satelliteId, store),
        );
        if (isCurrent) setData(response);
      } catch (cause) {
        if (isCurrent) {
          const message =
            cause instanceof Error && cause.message
              ? cause.message
              : "Failed to load hashstore data";
          setData(null);
          setError(message);
        }
      } finally {
        if (isCurrent) setIsLoading(false);
      }
    };

    load();

    let interval: number | undefined;
    if (typeof window !== "undefined") {
      interval = window.setInterval(() => {
        if (!isCurrent) return;
        setRefreshToken((v) => v + 1);
      }, refreshIntervalMs);
    }

    return () => {
      isCurrent = false;
      if (interval !== undefined) window.clearInterval(interval);
    };
  }, [enabled, cacheKey, refreshToken, refreshIntervalMs]);

  const refresh = useCallback(() => {
    setRefreshToken((v) => v + 1);
  }, []);

  return { data, isLoading, error, refresh };
};

export default useHashstoreSeries;
