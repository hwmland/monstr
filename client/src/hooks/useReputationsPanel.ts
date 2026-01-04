import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { fetchReputationsPanel } from "../services/apiClient";
import createRequestDeduper from "../utils/requestDeduper";
import useSelectedNodesStore from "../store/useSelectedNodes";
import type { NodeReputation } from "../types";

interface ReputationsPanelState {
  reputations: NodeReputation[];
  isLoading: boolean;
  error: string | null;
  refresh: () => void;
  selectedNodes: string[];
}

const useReputationsPanel = (): ReputationsPanelState => {
  const selected = useSelectedNodesStore((state) => state.selected);
  const [reputations, setReputations] = useState<NodeReputation[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  const requestPayload = useMemo(() => {
    if (selected.includes("All")) {
      return [] as string[];
    }

    return selected;
  }, [selected]);

  useEffect(() => {
    let isCurrent = true;

    const deduper = deduperRef.current;

    const load = async () => {
      setIsLoading(true);
      setError(null);

      try {
        // Use coalesce to share an in-flight request for the same selection.
        const data = await deduper.coalesce(requestPayload, () => fetchReputationsPanel(requestPayload));
        if (isCurrent) {
          setReputations(data);
        }
      } catch (cause) {
        if (isCurrent) {
          const message =
            cause instanceof Error && cause.message
              ? cause.message
              : "Failed to load reputations";
          setReputations([]);
          setError(message);
        }
      } finally {
        if (isCurrent) {
          setIsLoading(false);
        }
      }
    };

    load();

    const interval = window.setInterval(() => {
      if (!isCurrent) {
        return;
      }
      setRefreshToken((value) => value + 1);
    }, 60_000);

    return () => {
      isCurrent = false;
      window.clearInterval(interval);
    };
  }, [requestPayload, refreshToken]);

  const deduperRef = useRef(createRequestDeduper());

  const refresh = useCallback(() => {
    setRefreshToken((value) => value + 1);
  }, []);

  return { reputations, isLoading, error, refresh, selectedNodes: requestPayload };
};

export default useReputationsPanel;
