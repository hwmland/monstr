import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

import LongTermPanel from "./LongTermPanel";
import { fetchPayoutPaystubs } from "../../services/apiClient";
import type { PaystubRecord } from "../../types";

vi.mock("recharts", async () => {
  const React = await import("react");

  type ChartProps = { data?: unknown[]; children?: ReactNode };
  type SeriesProps = { dataKey?: string; name?: string; fill?: string; barSize?: number };

  const Chart = ({ data, children }: ChartProps) =>
    React.createElement(
      "div",
      { "data-testid": "financial-chart", "data-points": JSON.stringify(data ?? []) },
      children,
    );
  const Container = ({ children }: { children?: ReactNode }) => React.createElement("div", null, children);
  const Series = ({ dataKey, name, fill, barSize }: SeriesProps) =>
    React.createElement("div", {
      "data-testid": `series-${dataKey}`,
      "data-name": name,
      "data-fill": fill,
      "data-bar-size": barSize,
    });
  const Empty = () => null;

  return {
    Bar: Series,
    CartesianGrid: Empty,
    ComposedChart: Chart,
    Legend: Empty,
    Line: Series,
    LineChart: Chart,
    ResponsiveContainer: Container,
    Tooltip: Empty,
    XAxis: Empty,
    YAxis: Empty,
  };
});

vi.mock("../../services/apiClient", () => ({
  fetchPayoutPaystubs: vi.fn(),
}));

interface FinancialPoint {
  period: string;
  held: number;
  disposed: number;
}

const getFinancialPoints = (): FinancialPoint[] =>
  JSON.parse(screen.getByTestId("financial-chart").getAttribute("data-points") ?? "[]") as FinancialPoint[];

const makeRecord = (period: string, held: number, disposed: number): PaystubRecord => ({
  source: "node-1",
  satelliteId: "satellite-1",
  period,
  created: "",
  usageAtRest: 0,
  usageGet: 0,
  usagePut: 0,
  usageGetRepair: 0,
  usagePutRepair: 0,
  usageGetAudit: 0,
  compAtRest: 0,
  compGet: 0,
  compPut: 0,
  compGetRepair: 0,
  compPutRepair: 0,
  compGetAudit: 0,
  surgePercent: 0,
  held,
  owed: 0,
  disposed,
  paid: 0,
  distributed: 0,
});

describe("LongTermPanel", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.mocked(fetchPayoutPaystubs).mockResolvedValue({
      periods: {
        "2025-01": [makeRecord("2025-01", 100, 0)],
        "2025-02": [makeRecord("2025-02", 50, 30)],
      },
      disqualifications: [],
    });
  });

  it("shows disposed payouts as held-back bars and subtracts them from accumulated held", async () => {
    render(<LongTermPanel />);

    await screen.findByTestId("financial-chart");
    expect(screen.getByTestId("series-disposed")).toHaveAttribute("data-name", "held-back");
    expect(screen.getByTestId("series-disposed")).toHaveAttribute("data-fill", "#55f4f7");
    expect(screen.getByTestId("series-disposed")).toHaveAttribute("data-bar-size", "12");
    expect(getFinancialPoints().find((point) => point.period === "2025-02")).toMatchObject({
      held: 50,
      disposed: 30,
    });

    fireEvent.click(screen.getByRole("button", { name: "Accumulate" }));

    await waitFor(() => {
      expect(getFinancialPoints().find((point) => point.period === "2025-02")).toMatchObject({
        held: 120,
        disposed: 30,
      });
    });
  });
});