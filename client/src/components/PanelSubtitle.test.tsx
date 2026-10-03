import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import PanelSubtitle from "./PanelSubtitle";
import useNodeStore from "../store/useNodeStore";

describe("PanelSubtitle selected node labels", () => {
  beforeEach(() => {
    useNodeStore.setState({
      nodes: [],
      nodegroups: [{ name: "Ashburn", nodes: ["node-a", "node-b"] }],
    });
  });

  it("shows the group name when the selected nodes match a group", () => {
    render(<PanelSubtitle selectedNodes={["node-b", "node-a"]} />);

    expect(screen.getByText("Ashburn nodes").textContent).toBe("Ashburn nodes");
  });

  it("keeps listing nodes for a custom selection", () => {
    render(<PanelSubtitle selectedNodes={["node-a"]} />);

    expect(screen.getByText("Nodes: node-a").textContent).toBe("Nodes: node-a");
  });

  it("keeps the all-nodes label", () => {
    render(<PanelSubtitle selectedNodes={[]} />);

    expect(screen.getByText("All nodes").textContent).toBe("All nodes");
  });
});
