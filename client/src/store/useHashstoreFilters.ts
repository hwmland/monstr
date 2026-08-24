import { create } from "zustand";
import type { HashstoreTimeRange } from "../types";

const STORAGE_KEY = "monstr.hashstore.filters";

interface HashstoreFiltersState {
  timeRange: HashstoreTimeRange;
  satelliteId: string | null;
  store: string | null;
  setTimeRange: (value: HashstoreTimeRange) => void;
  setSatelliteId: (value: string | null) => void;
  setStore: (value: string | null) => void;
}

interface PersistedFilters {
  timeRange?: HashstoreTimeRange;
  satelliteId?: string | null;
  store?: string | null;
}

const loadFromStorage = (): PersistedFilters => {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw) as PersistedFilters;
  } catch {
    // ignore
  }
  return {};
};

const persist = (state: PersistedFilters) => {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // ignore
  }
};

const stored = loadFromStorage();

const useHashstoreFiltersStore = create<HashstoreFiltersState>((set, get) => ({
  timeRange: stored.timeRange ?? "30d",
  satelliteId: stored.satelliteId ?? null,
  store: stored.store ?? null,
  setTimeRange: (value) => {
    set({ timeRange: value });
    persist({ timeRange: value, satelliteId: get().satelliteId, store: get().store });
  },
  setSatelliteId: (value) => {
    set({ satelliteId: value });
    persist({ timeRange: get().timeRange, satelliteId: value, store: get().store });
  },
  setStore: (value) => {
    set({ store: value });
    persist({ timeRange: get().timeRange, satelliteId: get().satelliteId, store: value });
  },
}));

export default useHashstoreFiltersStore;
