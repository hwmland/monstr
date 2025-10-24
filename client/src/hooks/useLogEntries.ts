import { useCallback, useEffect } from "react";

import { fetchLogEntries } from "../services/apiClient";
import useLogStore from "../store/useLogStore";
import type { LogEntryQueryParams } from "../types";

const useLogEntries = (params?: LogEntryQueryParams) => {
  const { entries, isLoading, error, setEntries, setLoading, setError } = useLogStore();

  const load = useCallback(
    async (override?: LogEntryQueryParams) => {
      setLoading(true);
      setError(undefined);
      try {
        const data = await fetchLogEntries({ ...params, ...override });
        setEntries(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to load log entries");
      } finally {
        setLoading(false);
      }
    },
    [params, setEntries, setError, setLoading]
  );

  useEffect(() => {
    void load();
  }, [load]);

  return { entries, isLoading, error, refresh: load };
};

export default useLogEntries;
