import { describe, expect, it } from "vitest";
import {
  formatAxisLabel,
  formatTooltipLabel,
  LONG_RANGE_OPTIONS,
  RANGE_MAP,
  RANGE_VALUES,
} from "./AccumulatedTrafficPanel";

describe("AccumulatedTrafficPanel yearly range", () => {
  it("offers a 1 year range using weekly buckets", () => {
    expect(LONG_RANGE_OPTIONS).toContainEqual({ value: "1y", label: "1 year" });
    expect(RANGE_VALUES).toContain("1y");
    expect(RANGE_MAP["1y"]).toEqual({ intervalLength: "7d", numberOfIntervals: 53 });
  });

  it("shows the year in tooltips but not on the axis", () => {
    const value = new Date(2025, 9, 3, 12).toISOString();

    expect(formatAxisLabel(value, "1y", true)).toBe("03/10");
    expect(formatTooltipLabel(value, "1y", true)).toBe("03/10/2025");
  });

  it("preserves date labels for other long ranges", () => {
    const value = new Date(2025, 9, 3, 12).toISOString();

    expect(formatAxisLabel(value, "90d", true)).toBe("03/10");
    expect(formatTooltipLabel(value, "90d", true)).toBe("03/10");
  });
});
