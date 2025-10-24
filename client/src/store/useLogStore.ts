import { create } from "zustand";

import type { LogEntry } from "../types";

interface LogState {
  entries: LogEntry[];
  isLoading: boolean;
  error?: string;
  setEntries: (entries: LogEntry[]) => void;
  setLoading: (isLoading: boolean) => void;
  setError: (error?: string) => void;
}

const useLogStore = create<LogState>((set) => ({
  entries: [],
  isLoading: false,
  error: undefined,
  setEntries: (entries: LogEntry[]) => set({ entries }),
  setLoading: (isLoading: boolean) => set({ isLoading }),
  setError: (error?: string) => set({ error })
}));

export default useLogStore;
