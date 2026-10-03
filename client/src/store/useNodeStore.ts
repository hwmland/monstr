import { create } from 'zustand';

import type { NodeGroupInfo, NodeInfo } from '../types';

interface NodeState {
  nodes: NodeInfo[];
  nodegroups: NodeGroupInfo[];
  isLoading: boolean;
  error?: string;
  nodegroupsError?: string;
  setNodes: (nodes: NodeInfo[]) => void;
  setNodegroups: (nodegroups: NodeGroupInfo[]) => void;
  setLoading: (isLoading: boolean) => void;
  setError: (error?: string) => void;
  setNodegroupsError: (error?: string) => void;
}

const useNodeStore = create<NodeState>((set) => ({
  nodes: [],
  nodegroups: [],
  isLoading: false,
  error: undefined,
  nodegroupsError: undefined,
  setNodes: (nodes: NodeInfo[]) => set({ nodes }),
  setNodegroups: (nodegroups: NodeGroupInfo[]) => set({ nodegroups }),
  setLoading: (isLoading: boolean) => set({ isLoading }),
  setError: (error?: string) => set({ error }),
  setNodegroupsError: (nodegroupsError?: string) => set({ nodegroupsError }),
}));

export default useNodeStore;
