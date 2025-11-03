import { create } from "zustand";

import type { NodeInfo } from "../types";

interface NodeState {
  nodes: NodeInfo[];
  isLoading: boolean;
  error?: string;
  setNodes: (nodes: NodeInfo[]) => void;
  setLoading: (isLoading: boolean) => void;
  setError: (error?: string) => void;
}

const useNodeStore = create<NodeState>((set) => ({
  nodes: [],
  isLoading: false,
  error: undefined,
  setNodes: (nodes: NodeInfo[]) => set({ nodes }),
  setLoading: (isLoading: boolean) => set({ isLoading }),
  setError: (error?: string) => set({ error }),
}));

export default useNodeStore;
