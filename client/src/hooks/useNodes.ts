import { useCallback, useEffect } from "react";

import { fetchNodes } from "../services/apiClient";
import useNodeStore from "../store/useNodeStore";

const useNodes = () => {
  const { nodes, isLoading, error, setNodes, setLoading, setError } = useNodeStore();

  const load = useCallback(async () => {
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

  useEffect(() => {
    void load();
  }, [load]);

  return { nodes, isLoading, error, refresh: load };
};

export default useNodes;
