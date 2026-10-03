import useNodeStore from "../store/useNodeStore";
import { getNodeGroupSelectionValue } from "../utils/nodeGroups";

export default function useSelectedNodeGroupName(selectedNodes?: string[]): string | null {
  const nodes = useNodeStore((state) => state.nodes);
  const nodegroups = useNodeStore((state) => state.nodegroups);

  if (
    selectedNodes === undefined ||
    selectedNodes.length === 0 ||
    selectedNodes.includes("All")
  ) {
    return null;
  }

  const selectedGroup = getNodeGroupSelectionValue(
    selectedNodes,
    nodes.map((node) => node.name),
    nodegroups,
  );
  return selectedGroup === "All" ? null : selectedGroup;
}
