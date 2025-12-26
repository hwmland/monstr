import type { FC } from "react";

interface NodeIdProps {
  id: string;
}

const NodeId: FC<NodeIdProps> = ({ id }) => {
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(id);
    } catch (error) {
      console.error("Unable to copy Node ID", error);
    }
  };

  return (
    <button
      type="button"
      className="dash-node-card__id"
      onClick={handleCopy}
      title={`Copy Node ID\n${id}`}
    >
      Node ID
    </button>
  );
};

export default NodeId;
