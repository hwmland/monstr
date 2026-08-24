import { create } from "zustand";

const PANEL_VISIBILITY_STORAGE_KEY = "monstr.panelVisibility";
const HASHSTORE_GROUP_KEY = "monstr.hashstoreGroupEnabled";

const HASHSTORE_PANEL_IDS = [
  "hashstoreStorage",
  "hashstoreCompaction",
  "hashstoreHealth",
  "hashstoreActivity",
  "hashstoreDiagnostics",
] as const;

const persistPanels = (panels: Record<string, boolean>) => {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.setItem(PANEL_VISIBILITY_STORAGE_KEY, JSON.stringify(panels));
  } catch (error) {
    console.warn("Failed to persist panel visibility", error);
  }
};

interface PanelVisibilityState {
  panels: Record<string, boolean>;
  hashstoreGroupEnabled: boolean;
  togglePanel: (panelId: string) => void;
  setPanelVisibility: (panelId: string, isVisible: boolean) => void;
  isVisible: (panelId: string) => boolean;
  toggleHashstoreGroup: () => void;
}

const DEFAULT_PANELS: Record<string, boolean> = {
  nodeCompare: true,
  reputations: true,
  actualPerformance: true,
  satelliteTraffic: true,
  dataDistribution: true,
  hourlyTransfers: true,
  accumulatedTraffic: true,
  longTerm: false,
  diskUsage: false,
  bandwidthUsage: false,
  hashstoreStorage: true,
  hashstoreCompaction: true,
  hashstoreHealth: true,
  hashstoreActivity: false,
  hashstoreDiagnostics: false,
};

const usePanelVisibilityStore = create<PanelVisibilityState>((set, get) => ({
  panels: (() => {
    if (typeof window !== "undefined") {
      try {
        const raw = window.localStorage.getItem(PANEL_VISIBILITY_STORAGE_KEY);
        if (raw) {
          const parsed = JSON.parse(raw) as Record<string, boolean>;
          return { ...DEFAULT_PANELS, ...parsed };
        }
      } catch (error) {
        console.warn("Failed to parse panel visibility from storage", error);
      }
    }
    return { ...DEFAULT_PANELS };
  })(),
  hashstoreGroupEnabled: (() => {
    if (typeof window !== "undefined") {
      try {
        const raw = window.localStorage.getItem(HASHSTORE_GROUP_KEY);
        if (raw !== null) return raw === "1";
      } catch { /* ignore */ }
    }
    return true;
  })(),
  togglePanel: (panelId: string) => {
    const panels = get().panels;
    const current = panels[panelId] ?? true;
    const next = { ...DEFAULT_PANELS, ...panels, [panelId]: !current };
    set({ panels: next });
    persistPanels(next);
  },
  setPanelVisibility: (panelId: string, isVisible: boolean) => {
    set((state) => {
      const next = { ...DEFAULT_PANELS, ...state.panels, [panelId]: isVisible };
      persistPanels(next);
      return { panels: next };
    });
  },
  isVisible: (panelId: string) => {
    const state = get();
    if (!state.hashstoreGroupEnabled && (HASHSTORE_PANEL_IDS as readonly string[]).includes(panelId)) {
      return false;
    }
    return state.panels[panelId] ?? false;
  },
  toggleHashstoreGroup: () => {
    const next = !get().hashstoreGroupEnabled;
    set({ hashstoreGroupEnabled: next });
    try {
      window.localStorage.setItem(HASHSTORE_GROUP_KEY, next ? "1" : "0");
    } catch { /* ignore */ }
  },
}));

export default usePanelVisibilityStore;
