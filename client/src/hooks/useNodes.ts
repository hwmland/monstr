import { useCallback, useEffect, useRef } from 'react';

import { fetchNodeGroups, fetchNodes } from '../services/apiClient';
import useNodeStore from '../store/useNodeStore';
import createRequestDeduper from '../utils/requestDeduper';

const useNodes = () => {
  const {
    nodes,
    nodegroups,
    isLoading,
    error,
    nodegroupsError,
    setNodes,
    setNodegroups,
    setLoading,
    setError,
    setNodegroupsError,
  } = useNodeStore();

  const load = useCallback(async () => {
    const deduper = deduperRef.current;
    if (deduper.isDuplicate([], 1000)) return;

    setLoading(true);
    setError(undefined);
    setNodegroupsError(undefined);
    try {
      const [nodesResult, nodegroupsResult] = await Promise.allSettled([
        fetchNodes(),
        fetchNodeGroups(),
      ]);
      if (nodesResult.status === 'fulfilled') {
        setNodes(nodesResult.value);
      } else {
        setError(
          nodesResult.reason instanceof Error ? nodesResult.reason.message : 'Unable to load nodes',
        );
      }
      if (nodegroupsResult.status === 'fulfilled') {
        setNodegroups(nodegroupsResult.value);
      } else {
        setNodegroupsError(
          nodegroupsResult.reason instanceof Error
            ? nodegroupsResult.reason.message
            : 'Unable to load node groups',
        );
      }
    } finally {
      setLoading(false);
    }
  }, [setError, setLoading, setNodegroups, setNodegroupsError, setNodes]);

  const deduperRef = useRef(createRequestDeduper());

  useEffect(() => {
    void load();
  }, [load]);

  return { nodes, nodegroups, isLoading, error, nodegroupsError, refresh: load };
};

export default useNodes;
