import { useState } from "react";

import useDashNodes from "./hooks/useDashNodes";
import NodePanel from "./components/NodePanel";

const DashPage = () => {
  const { nodes } = useDashNodes();
  const [refreshToken] = useState(0);

  return (
    <div className="page dash-page">
      <div className="dash-node-grid">
        {nodes.map((node) => (
          <NodePanel key={`${node}-${refreshToken}`} nodeName={node} refreshToken={refreshToken} />
        ))}
      </div>
    </div>
  );
};

export default DashPage;
