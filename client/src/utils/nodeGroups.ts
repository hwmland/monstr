import type { NodeGroupInfo } from '../types';

export const ALL_NODES_VALUE = 'All';

const setsEqual = (left: Set<string>, right: Set<string>): boolean =>
  left.size === right.size && [...left].every((value) => right.has(value));

export const getNodeGroupSelectionValue = (
  selectedNodes: string[],
  availableNodeNames: string[],
  nodegroups: NodeGroupInfo[],
): string | null => {
  const available = new Set(availableNodeNames);
  const selected = new Set(selectedNodes.filter((name) => name !== ALL_NODES_VALUE));
  if (
    selectedNodes.includes(ALL_NODES_VALUE) ||
    (available.size > 0 && setsEqual(selected, available))
  ) {
    return ALL_NODES_VALUE;
  }

  const matches = nodegroups.filter(
    (group) => group.nodes.length > 0 && setsEqual(selected, new Set(group.nodes)),
  );
  return matches.length === 1 ? matches[0].name : null;
};
