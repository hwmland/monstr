import type { FC } from "react";
import { formatSizeValue } from "../../../utils/units";
import { formatDuration } from "../../../utils/hashstore";

export interface HashstoreTooltipEntry {
  name?: string;
  value?: number;
  color?: string;
  dataKey?: string;
  payload?: Record<string, unknown>;
}

interface HashstoreTooltipProps {
  active?: boolean;
  payload?: HashstoreTooltipEntry[];
  label?: string;
  sizeUnit?: string;
  sizeFactor?: number;
  formatValue?: (value: number, name: string) => string;
}

const defaultFormatDate = (value: string): string => {
  try {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return value;
  }
};

export const makeSizeFormatter = (unit: string, factor: number) =>
  (value: number, name: string): string => {
    if (name.endsWith("Duration")) return formatDuration(value);
    if (name === "Passes" || name === "Compactions") return String(Math.round(value));
    if (name === "Load") return `${(value * 100).toFixed(1)}%`;
    return `${formatSizeValue(value / (factor || 1))} ${unit}`;
  };

export const makePercentFormatter = () =>
  (value: number, _name: string): string => `${value.toFixed(1)}%`;

export const makeCountFormatter = () =>
  (value: number, _name: string): string => value.toLocaleString();

const HashstoreTooltip: FC<HashstoreTooltipProps> = ({
  active,
  payload,
  label,
  formatValue,
}) => {
  if (!active || !payload || payload.length === 0) return null;

  const entries = payload.filter((e) => e.value !== undefined && e.value !== null);

  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__label">
        {label ? defaultFormatDate(label) : "—"}
      </div>
      {entries.map((entry) => {
        const name = entry.name ?? entry.dataKey ?? "Series";
        const numeric = Number(entry.value ?? 0);
        const display = formatValue ? formatValue(numeric, name) : String(numeric);
        return (
          <div key={name} className="chart-tooltip__row">
            <span style={{ color: entry.color ?? "var(--color-text)" }}>{name}:</span>
            <span>{display}</span>
          </div>
        );
      })}
    </div>
  );
};

export default HashstoreTooltip;
