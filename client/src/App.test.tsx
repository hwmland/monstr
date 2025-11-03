import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";

import App from "./App";

const renderApp = () =>
  render(
    <BrowserRouter>
      <App />
    </BrowserRouter>
  );

describe("App", () => {
  it("renders the nodes panel heading", () => {
    renderApp();
    const heading = screen.getByRole("heading", {
      name: /monitor storj nodes by hwm\.land/i
    });

    expect(heading).toBeTruthy();
  });
});
