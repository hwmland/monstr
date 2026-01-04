import type { FC } from "react";
import { useEffect, useMemo, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis } from "recharts";

import usePanelVisibilityStore from "../../store/usePanelVisibility";
import PanelHeader from "../PanelHeader";
import PanelSubtitle from "../PanelSubtitle";
import PanelControls, { getStoredSelection } from "../PanelControls";
import PanelControlsButton from "../PanelControlsButton";
import PanelControlsCheckbox from "../PanelControlsCheckbox";
import useDiskUsageUsage from "../../hooks/useDiskUsageUsage";
import { formatSizeValue, pickSizeUnit } from "../../utils/units";
import { DISK_USAGE_MODE_VALUES, type DiskUsageUsageMode, type DiskUsageUsageNode } from "../../types";

interface DiskUsagePanelProps {
	selectedNodes: string[];
}

type IntervalKey = "8d" | "30d" | "90d" | "1y";

type LayoutMode = "stacked" | "separate";

const INTERVAL_VALUES = ["8d", "30d", "90d", "1y"] as const satisfies readonly IntervalKey[];
const LAYOUT_MODE_VALUES = ["stacked", "separate"] as const satisfies readonly LayoutMode[];

const BOOLEAN_OPTIONS = ["true", "false"] as const;
const SHOW_PERCENT_KEY = "monstr.panel.DiskUsage.showPercent";
const ZOOM_KEY = "monstr.panel.DiskUsage.zoom";

const INTERVAL_TO_DAYS: Record<IntervalKey, number> = {
	"8d": 8,
	"30d": 30,
	"90d": 90,
	"1y": 364, // 364 == 52 weeks or 13 * 28 days
};

const INTERVAL_LABELS: Record<IntervalKey, string> = {
	"8d": "8d",
	"30d": "30d",
	"90d": "90d",
	"1y": "1y",
};

const INTERVAL_SUBTITLES: Record<IntervalKey, string> = {
	"8d": "Last 8 days",
	"30d": "Last 30 days",
	"90d": "Last 90 days",
	"1y": "Last year",
};

const MODE_OPTIONS: Array<{ id: DiskUsageUsageMode; label: string }> = [
	{ id: "end", label: "End" },
	{ id: "maxTrash", label: "Trash" },
	{ id: "maxUsage", label: "Usage" },
];

const formatAxisLabel = (value: string): string => {
	try {
		const date = new Date(value);
		if (Number.isNaN(date.getTime())) {
			return value;
		}
		return date.toLocaleDateString([], { month: "short", day: "numeric" });
	} catch {
		return value;
	}
};

const formatTooltipTimestamp = (value: string): string => {
	try {
		const date = new Date(value);
		if (Number.isNaN(date.getTime())) {
			return value;
		}
		return date.toLocaleDateString([], {
			month: "short",
			day: "2-digit",
			year: "numeric",
		});
	} catch {
		return value;
	}
};

const DiskUsageTooltip: FC<{
	unitLabel: string;
	active?: boolean;
	payload?: any[];
}> = ({ unitLabel, active, payload }) => {
	if (!active || !payload || payload.length === 0) {
		return null;
	}

	const period = String(payload[0]?.payload?.period ?? "");
	const label = formatTooltipTimestamp(period);
	const source = payload[0]?.payload as {
		trashPercent?: number;
		freePercent?: number;
	};

	const filteredEntries = payload.filter((entry: any) => entry?.dataKey !== "trashPercent" && entry?.dataKey !== "freePercent");
	const tableKeys = new Set(["usage", "trash", "capacity"]);
	const tableEntries = filteredEntries
		.filter((entry: any) => tableKeys.has(String(entry?.dataKey ?? "")))
		.sort((a: any, b: any) => {
			const order = ["usage", "trash", "capacity"];
			return order.indexOf(String(a?.dataKey)) - order.indexOf(String(b?.dataKey));
		});
	const extraEntries = filteredEntries.filter((entry: any) => !tableKeys.has(String(entry?.dataKey ?? "")));

	return (
		<div className="chart-tooltip">
			<div className="chart-tooltip__label">{label}</div>
			{tableEntries.length > 0 ? (
				<table className="chart-tooltip__table" style={{ width: "100%", borderCollapse: "collapse" }}>
					<tbody>
						{tableEntries.map((entry: any) => {
						const name = entry?.name ?? entry?.dataKey ?? "Series";
						const color = entry?.color ?? "var(--color-text)";
						const value = Number(entry?.value ?? 0);
						let percentAnnotation: string | null = null;
						if (entry?.dataKey === "trash" && typeof source?.trashPercent === "number") {
							percentAnnotation = `${source.trashPercent.toFixed(1)}%`;
						} else if (entry?.dataKey === "capacity" && typeof source?.freePercent === "number") {
							percentAnnotation = `(${source.freePercent.toFixed(1)}% Free)`;
						}

						return (
							<tr key={String(entry?.dataKey ?? name)}>
                <td style={{ color, padding: "2px 6px", fontWeight: 500, textAlign: "left" }}>{name}:</td>
								<td style={{ padding: "2px 6px", textAlign: "right" }}>
									{formatSizeValue(value)} {unitLabel}
								</td>
								<td style={{ padding: "2px 1rem", textAlign: "right", minWidth: "3.5rem" }}>
									{percentAnnotation ?? ""}
								</td>
							</tr>
						);
					})}
				</tbody>
			</table>
			) : null}
			{extraEntries.map((entry: any) => {
				const name = entry?.name ?? entry?.dataKey ?? "Series";
				const color = entry?.color ?? "var(--color-text)";
				const value = Number(entry?.value ?? 0);
				return (
					<div key={String(entry?.dataKey ?? name)} className="chart-tooltip__row" style={{ display: "flex", justifyContent: "space-between", fontVariantNumeric: "tabular-nums" }}>
						<span style={{ color }}>{name}</span>
						<span>{formatSizeValue(value)} {unitLabel}</span>
					</div>
				);
			})}
		</div>
	);
};

const DiskUsagePanel: FC<DiskUsagePanelProps> = ({ selectedNodes }) => {
	const { isVisible } = usePanelVisibilityStore();
	const visible = isVisible("diskUsage");
	const [interval, setInterval] = useState<IntervalKey>(() =>
		getStoredSelection<IntervalKey>("monstr.panel.DiskUsage.interval", INTERVAL_VALUES, "1y"),
	);
	const [mode, setMode] = useState<DiskUsageUsageMode>(() =>
		getStoredSelection<DiskUsageUsageMode>("monstr.panel.DiskUsage.mode", DISK_USAGE_MODE_VALUES, "end"),
	);
	const [layout, setLayout] = useState<LayoutMode>(() =>
		getStoredSelection<LayoutMode>("monstr.panel.DiskUsage.layout", LAYOUT_MODE_VALUES, "stacked"),
	);
	const [showPercent, setShowPercent] = useState<boolean>(() =>
		getStoredSelection(SHOW_PERCENT_KEY, BOOLEAN_OPTIONS, "false") === "true",
	);
	const [zoomMode, setZoomMode] = useState<boolean>(() =>
		getStoredSelection(ZOOM_KEY, BOOLEAN_OPTIONS, "false") === "true",
	);

	const handleShowPercentChange = (value: boolean) => {
		setShowPercent(value);
		try {
			localStorage.setItem(SHOW_PERCENT_KEY, value ? "true" : "false");
		} catch {
			// ignore
		}
	};

	const handleZoomModeChange = (value: boolean) => {
		setZoomMode(value);
		try {
			localStorage.setItem(ZOOM_KEY, value ? "true" : "false");
		} catch {
			// ignore
		}
	};

	const intervalDays = INTERVAL_TO_DAYS[interval];

	const { periods, isLoading, error, refresh } = useDiskUsageUsage({
		nodes: selectedNodes,
		intervalDays,
		mode,
		enabled: visible,
	});

	useEffect(() => {
		if (!visible) return undefined;
		const id = window.setInterval(() => {
			void refresh();
		}, 600_000);

		return () => window.clearInterval(id);
	}, [refresh, visible]);

	const sortedPeriods = useMemo(() => {
		if (!periods) return [] as string[];
		return Object.keys(periods).sort();
	}, [periods]);

	const aggregatedSeries = useMemo(() => {
		if (!periods) {
			return [] as Array<{ period: string; usage: number; trash: number; capacity: number }>;
		}

		return sortedPeriods.map((period) => {
			const nodes = periods[period] ?? {};
			let usage = 0;
			let trash = 0;
			let capacity = 0;

			Object.values(nodes as Record<string, DiskUsageUsageNode>).forEach((metrics) => {
				usage += Number(metrics?.usage ?? 0);
				trash += Number(metrics?.trash ?? 0);
				capacity += Number(metrics?.capacity ?? 0);
			});

			return { period, usage, trash, capacity };
		});
	}, [periods, sortedPeriods]);

	const { chartData, unitLabel } = useMemo(() => {
		if (aggregatedSeries.length === 0) {
			return {
				chartData: [] as Array<{
					period: string;
					label: string;
					usage: number;
					trash: number;
					capacity: number;
					freePercent: number;
					trashPercent: number;
				}>,
				unitLabel: "B",
			};
		}

		const maxValue = aggregatedSeries.reduce((max, entry) => {
			const stackedValue = entry.usage + entry.trash;
			return Math.max(max, entry.capacity, stackedValue);
		}, 0);

		const unitInfo = pickSizeUnit(maxValue || 1);
		const factor = unitInfo.factor || 1;

		const data = aggregatedSeries.map((entry) => {
			const freeBytes = entry.capacity - entry.trash - entry.usage;
			const rawFreePercent = entry.capacity > 0 ? (freeBytes / entry.capacity) * 100 : 0;
			const freePercent = Math.max(0, Math.min(rawFreePercent, 100));
			const rawTrashPercent = entry.usage > 0 ? (entry.trash / entry.usage) * 100 : 0;
			const trashPercent = Math.max(0, Math.min(rawTrashPercent, 100));

			return {
				period: entry.period,
				label: formatAxisLabel(entry.period),
				usage: entry.usage / factor,
				trash: entry.trash / factor,
				capacity: entry.capacity / factor,
				freePercent,
				trashPercent,
			};
		});

		return { chartData: data, unitLabel: unitInfo.unit };
	}, [aggregatedSeries]);

	const hasData = chartData.length > 0;

	if (!visible) {
		return null;
	}

	const handleRefresh = () => {
		void refresh();
	};

	const showCapacitySeries = !zoomMode;
	const showTrashSeries = !zoomMode || layout === "stacked";

	const absoluteYAxisDomain = useMemo(() => {
		if (!zoomMode || chartData.length === 0) {
			return ["auto", "auto"] as const;
		}

		let minValue = Number.POSITIVE_INFINITY;
		let maxValue = Number.NEGATIVE_INFINITY;

		chartData.forEach((point) => {
			const usageValue = Number(point.usage);
			const trashValue = Number(point.trash);
			const stackedValue = showTrashSeries ? usageValue + trashValue : usageValue;
			maxValue = Math.max(maxValue, stackedValue);
			minValue = Math.min(minValue, usageValue);
		});

		if (!Number.isFinite(minValue) || !Number.isFinite(maxValue)) {
			return ["auto", "auto"] as const;
		}

		const range = Math.max(maxValue - minValue, 0);
		const padding = Math.max(range * 0.08, maxValue * 0.02, 0.1);
		const lowerBound = Math.max(0, minValue - padding);
		const upperBound = maxValue + padding;

		return [lowerBound, upperBound] as const;
	}, [chartData, zoomMode, showTrashSeries, layout]);

	return (
		<section className="panel">
			<PanelHeader
				title="Disk Usage"
				subtitle={(
					<PanelSubtitle selectedNodes={selectedNodes}>
						Interval: {INTERVAL_SUBTITLES[interval]}
					</PanelSubtitle>
				)}
				onRefresh={handleRefresh}
				isRefreshing={isLoading}
				refreshLabels={{ idle: "Refresh", active: "Loading..." }}
				controls={(
					<>
						<PanelControls
							ariaLabel="Disk usage toggles"
							buttons={[
								<PanelControlsCheckbox
									key="show-percent-toggle"
									label="Show&nbsp;%"
									checked={showPercent}
									onChange={handleShowPercentChange}
									ariaLabel="Toggle percentage view"
								/>,
								<PanelControlsCheckbox
									key="zoom-toggle"
									label="Zoom"
									checked={zoomMode}
									onChange={handleZoomModeChange}
									ariaLabel="Toggle zoom mode"
								/>,
							]}
						/>
						<PanelControls
							ariaLabel="Disk usage layout"
							storageKey="monstr.panel.DiskUsage.layout"
							buttons={[
								<PanelControlsButton key="stacked" type="button" active={layout === "stacked"} onClick={() => setLayout("stacked")} content="Stacked" />,
								<PanelControlsButton key="separate" type="button" active={layout === "separate"} onClick={() => setLayout("separate")} content="Separate" />,
							]}
						/>
						<PanelControls
							ariaLabel="Disk usage snapshot mode"
							storageKey="monstr.panel.DiskUsage.mode"
							buttons={MODE_OPTIONS.map((option) => (
								<PanelControlsButton key={option.id} type="button" active={mode === option.id} onClick={() => setMode(option.id)} content={option.label} />
							))}
						/>
						<PanelControls
							ariaLabel="Disk usage window"
							storageKey="monstr.panel.DiskUsage.interval"
							buttons={INTERVAL_VALUES.map((key) => (
								<PanelControlsButton key={key} type="button" active={interval === key} onClick={() => setInterval(key)} content={INTERVAL_LABELS[key]} />
							))}
						/>
					</>
				)}
			/>

			<div className="panel__body">
				{error ? <p className="panel__error">{error}</p> : null}
				{!hasData ? (
					<p className="panel__empty">No disk usage data for the selected window.</p>
				) : (
					<>
						<div style={{ width: "100%", height: 360 }}>
							<ResponsiveContainer width="100%" height="100%">
								<ComposedChart data={chartData} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
									<CartesianGrid strokeDasharray="3 3" opacity={0.2} />
									<XAxis dataKey="label" tick={{ fill: "var(--color-text-muted)", fontSize: 12 }} />
									<YAxis
										yAxisId="absolute"
										tickFormatter={(value: number) => formatSizeValue(Number(value))}
										tick={{ fill: "var(--color-text-muted)", fontSize: 12 }}
										label={{ value: unitLabel, angle: -90, position: "insideLeft", fill: "var(--color-text-muted)", offset: 10 }}
										domain={absoluteYAxisDomain} allowDataOverflow
									/>
									{showPercent ? (
										<YAxis
											yAxisId="percent"
											orientation="right"
											tickFormatter={(value: number) => `${value.toFixed(0)}%`}
											tick={{ fill: "var(--color-text-muted)", fontSize: 12 }}
											label={{ value: "%", angle: 90, position: "insideRight", fill: "var(--color-text-muted)", offset: 10 }}
											domain={[0, 100]}
										/>
									) : null}
									<RechartsTooltip content={<DiskUsageTooltip unitLabel={unitLabel} />} />
									<Legend />
									{layout === "stacked" ? (
										<>
											<Area
												yAxisId="absolute"
												type="linear"
												dataKey="usage"
												name="Usage"
												stackId="usage"
												stroke="#38BDF8"
												fill="rgba(56, 189, 248, 0.35)"
												strokeWidth={2}
												isAnimationActive={false}
												activeDot={{ r: 3 }}
											/>
											{showTrashSeries ? (
												<Area
													yAxisId="absolute"
													type="linear"
													dataKey="trash"
													name="Trash"
													stackId="usage"
													stroke="#F97316"
													fill="rgba(249, 115, 22, 0.35)"
													strokeWidth={2}
													isAnimationActive={false}
													activeDot={{ r: 3 }}
												/>
											) : null}
										</>
									) : (
										<>
											<Line yAxisId="absolute" type="linear" dataKey="usage" name="Usage" stroke="#38BDF8" strokeWidth={2} dot={false} isAnimationActive={false} />
											{showTrashSeries ? (
												<Line yAxisId="absolute" type="linear" dataKey="trash" name="Trash" stroke="#F97316" strokeWidth={2} dot={false} isAnimationActive={false} />
											) : null}
										</>
									)}
									{showCapacitySeries ? (
										<Line
											yAxisId="absolute"
											type="linear"
											dataKey="capacity"
											name="Capacity"
											stroke="#94A3B8"
											strokeWidth={2}
											dot={false}
											isAnimationActive={false}
										/>
									) : null}
									{showPercent ? (
										<>
											<Line
												yAxisId="percent"
												type="linear"
												dataKey="freePercent"
												name="Free %"
												stroke="#34D399"
												strokeWidth={2}
												dot={false}
												strokeDasharray="5 4"
												isAnimationActive={false}
											/>
											<Line
												yAxisId="percent"
												type="linear"
												dataKey="trashPercent"
												name="Trash %"
												stroke="#EC4899"
												strokeWidth={2}
												dot={false}
												strokeDasharray="5 4"
												isAnimationActive={false}
											/>
										</>
									) : null}
								</ComposedChart>
							</ResponsiveContainer>
						</div>
					</>
				)}
			</div>
		</section>
	);
};

export default DiskUsagePanel;

