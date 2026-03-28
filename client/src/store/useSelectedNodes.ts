import { create } from "zustand";

interface ToggleModifiers {
  shift?: boolean;
  ctrl?: boolean;
}

interface SelectedNodesState {
  selected: string[];
  toggleNode: (name: string, availableNodeNames: string[], modifiers?: ToggleModifiers) => void;
  isSelected: (name: string) => boolean;
}

const useSelectedNodesStore = create<SelectedNodesState>((set, get) => ({
  selected: ["All"],
  isSelected: (name: string) => get().selected.includes(name),
  toggleNode: (name: string, availableNodeNames: string[], modifiers?: ToggleModifiers) => {
    let next = [...get().selected];

    if (name === "All") {
      // "All" always means "select everything" regardless of modifiers
      next = ["All"];
    } else if (modifiers?.shift) {
      // Shift+Click: select only this node
      next = [name];
    } else if (modifiers?.ctrl) {
      // Ctrl+Click: select all nodes except this one
      next = availableNodeNames.filter((n) => n !== name);
      if (next.length === 0 || next.length === availableNodeNames.length) {
        next = ["All"];
      }
    } else {
      if (next.includes("All")) {
        next = [];
      }

      if (next.includes(name)) {
        next = next.filter((item) => item !== name);
      } else {
        next = [...next, name];
      }

      if (next.length === 0) {
        next = ["All"];
      } else if (next.length === availableNodeNames.length) {
        next = ["All"];
      }
    }

    set({ selected: next });
  },
}));

export default useSelectedNodesStore;
