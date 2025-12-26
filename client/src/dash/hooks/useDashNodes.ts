import { useCallback, useEffect, useState } from "react";

import { fetchDashNodes } from "../api";

const REFRESH_INTERVAL_MS = 60_000;

const useDashNodes = () => {
  const [nodes, setNodes] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | undefined>();

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(undefined);
    try {
      const data = await fetchDashNodes();
      setNodes(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load dash nodes");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    const timer = window.setInterval(() => {
      void load();
    }, REFRESH_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [load]);

  return { nodes, isLoading, error, refresh: load };
};

export default useDashNodes;
