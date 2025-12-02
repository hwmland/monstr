import { create } from "zustand";

const PANEL_VISIBILITY_STORAGE_KEY = "monstr.panelVisibility";

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
  togglePanel: (panelId: string) => void;
  setPanelVisibility: (panelId: string, isVisible: boolean) => void;
  isVisible: (panelId: string) => boolean;
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
  togglePanel: (panelId: string) => {
    const panels = get().panels;
    const current = panels[panelId] ?? true;
    // Merge with defaults to avoid persisting an incomplete object that would
    // shadow other panel flags when reloaded from storage.
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
    const panels = get().panels;
    return panels[panelId] ?? false;
  },
}));

export default usePanelVisibilityStore;
