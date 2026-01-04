import { useCallback, useEffect, useRef } from "react";

import { fetchNodes } from "../services/apiClient";
import useNodeStore from "../store/useNodeStore";
import createRequestDeduper from "../utils/requestDeduper";

const useNodes = () => {
  const { nodes, isLoading, error, setNodes, setLoading, setError } = useNodeStore();

  const load = useCallback(async () => {
    const deduper = deduperRef.current;
    if (deduper.isDuplicate([], 1000)) return;

    setLoading(true);
    setError(undefined);
    try {
      const data = await fetchNodes();
      setNodes(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load nodes");
    } finally {
      setLoading(false);
    }
  }, [setError, setLoading, setNodes]);

  const deduperRef = useRef(createRequestDeduper());

  useEffect(() => {
    void load();
  }, [load]);

  return { nodes, isLoading, error, refresh: load };
};

export default useNodes;
