import { useCallback, useEffect, useState } from "react";

import { fetchDashNodeDetails } from "../api";
import type { DashNodeDetails } from "../types";

const REFRESH_INTERVAL_MS = 60_000;

const useDashNodeDetails = (nodeName: string | null, refreshKey: number = 0) => {
  const [details, setDetails] = useState<DashNodeDetails | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | undefined>();

  const load = useCallback(async () => {
    if (!nodeName) {
      setDetails(null);
      return;
    }

    setIsLoading(true);
    setError(undefined);
    try {
      const data = await fetchDashNodeDetails(nodeName);
      setDetails(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load node details");
    } finally {
      setIsLoading(false);
    }
  }, [nodeName, refreshKey]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!nodeName || typeof window === "undefined") return undefined;
    const timer = window.setInterval(() => {
      void load();
    }, REFRESH_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [load, nodeName]);

  return { details, isLoading, error, refresh: load };
};

export default useDashNodeDetails;
