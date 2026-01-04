import { useCallback, useEffect, useRef, useState } from "react";

import { fetchDiskUsageUsage } from "../services/apiClient";
import createRequestDeduper from "../utils/requestDeduper";
import type { DiskUsageUsageMode, DiskUsageUsageNode } from "../types";

interface UseDiskUsageUsageOptions {
  nodes: string[];
  intervalDays: number;
  mode?: DiskUsageUsageMode;
  enabled?: boolean;
}

interface UseDiskUsageUsageResult {
  periods: Record<string, Record<string, DiskUsageUsageNode>> | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

const useDiskUsageUsage = ({
  nodes,
  intervalDays,
  mode = "end",
  enabled = true,
}: UseDiskUsageUsageOptions): UseDiskUsageUsageResult => {
  const [periods, setPeriods] = useState<Record<string, Record<string, DiskUsageUsageNode>> | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled) {
      setIsLoading(false);
      return;
    }
    const deduper = deduperRef.current;
    const nodeFilter = nodes.includes("All") ? [] : nodes;
    if (deduper.isDuplicate(nodeFilter, 1000)) return;

    setIsLoading(true);
    setError(null);
    try {
      const response = await fetchDiskUsageUsage(nodeFilter, intervalDays, mode);
      setPeriods(response.periods);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load disk usage data");
    } finally {
      setIsLoading(false);
    }
  }, [enabled, intervalDays, mode, nodes]);

  const deduperRef = useRef(createRequestDeduper());

  useEffect(() => {
    if (!enabled) {
      setIsLoading(false);
      return;
    }

    void refresh();
  }, [enabled, refresh]);

  return { periods, isLoading, error, refresh };
};

export default useDiskUsageUsage;
