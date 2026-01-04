import { useCallback, useEffect, useMemo, useState, useRef } from "react";
import createRequestDeduper from "../utils/requestDeduper";

import { fetchActualPerformance } from "../services/apiClient";
import useSelectedNodesStore from "../store/useSelectedNodes";
import type {
  TransferActualAggregated,
  TransferActualCategoryMetrics,
  TransferActualData,
  TransferActualMetrics,
} from "../types";

interface UseTransfersActualOptions {
  enabled?: boolean;
}

interface UseTransfersActualState {
  data: TransferActualData | null;
  aggregated: TransferActualAggregated | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => void;
  selectedNodes: string[];
}

const ZERO_METRICS: TransferActualMetrics = {
  operationsTotal: 0,
  operationsSuccess: 0,
  dataBytes: 0,
  rate: 0,
};

const combineCategoryMetrics = (
  category: TransferActualCategoryMetrics | undefined,
): TransferActualMetrics => {
  const normal = category?.normal ?? ZERO_METRICS;
  const repair = category?.repair ?? ZERO_METRICS;

  return {
    operationsTotal: normal.operationsTotal + repair.operationsTotal,
    operationsSuccess: normal.operationsSuccess + repair.operationsSuccess,
    dataBytes: normal.dataBytes + repair.dataBytes,
    rate: normal.rate + repair.rate,
  };
};

const useTransfersActual = (options: UseTransfersActualOptions = {}): UseTransfersActualState => {
  const { enabled = true } = options;
  const selected = useSelectedNodesStore((state) => state.selected);
  const [data, setData] = useState<TransferActualData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);
  const deduperRef = useRef(createRequestDeduper());
  

  const requestNodes = useMemo(() => {
    if (selected.includes("All")) {
      return [] as string[];
    }

    return selected;
  }, [selected]);

  useEffect(() => {
    let isCurrent = true;

    if (!enabled) {
      setIsLoading(false);
      setError(null);
      return () => {
        isCurrent = false;
      };
    }

    const load = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const deduper = deduperRef.current;
        const response = await deduper.coalesce(requestNodes, () => fetchActualPerformance(requestNodes));
        if (isCurrent) {
          setData(response);
        }
      } catch (cause) {
        if (isCurrent) {
          const message =
            cause instanceof Error && cause.message
              ? cause.message
              : "Failed to load transfer statistics";
          setData(null);
          setError(message);
        }
      } finally {
        if (isCurrent) {
          setIsLoading(false);
        }
      }
    };

    load();

    let interval: number | undefined;
    if (typeof window !== "undefined") {
      interval = window.setInterval(() => {
        if (!isCurrent) {
          return;
        }
        setRefreshToken((value) => value + 1);
      }, 10_000);
    }

    return () => {
      isCurrent = false;
      if (interval !== undefined) {
        window.clearInterval(interval);
      }
    };
  }, [enabled, requestNodes, refreshToken]);

  const refresh = useCallback(() => {
    setRefreshToken((value) => value + 1);
  }, []);

  const aggregated = useMemo<TransferActualAggregated | null>(() => {
    if (!data) {
      return null;
    }

    return {
      startTime: data.startTime,
      endTime: data.endTime,
      download: combineCategoryMetrics(data.download),
      upload: combineCategoryMetrics(data.upload),
    };
  }, [data]);

  return {
    data,
    aggregated,
    isLoading: enabled ? isLoading : false,
    error: enabled ? error : null,
    refresh,
    selectedNodes: requestNodes,
  };
};

export default useTransfersActual;
