import { create } from "zustand";

interface SelectedNodesState {
  selected: string[];
  toggleNode: (name: string, availableNodeNames: string[]) => void;
  isSelected: (name: string) => boolean;
}

const useSelectedNodesStore = create<SelectedNodesState>((set, get) => ({
  selected: ["All"],
  isSelected: (name: string) => get().selected.includes(name),
  toggleNode: (name: string, availableNodeNames: string[]) => {
    let next = [...get().selected];

    if (name === "All") {
      next = ["All"];
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
    console.log("Selected nodes:", next);
  }
}));

export default useSelectedNodesStore;
