import { FC, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Tooltip,
  Cell,
} from "recharts";

import PanelHeader from "../PanelHeader";
import PanelSubtitle from "../PanelSubtitle";
import PanelControlsButton from "../PanelControlsButton";
import Legend from "../Legend";
import usePanelVisibilityStore from "../../store/usePanelVisibility";
import { fetchTransferTotals, fetchDiskUsageChange } from "../../services/apiClient";
import createRequestDeduper from "../../utils/requestDeduper";
import type { DiskUsageChangeResponse, TransferTotalsResponse } from "../../types";
import { formatSizeValue, pickSizePresentation, pickRatePresentation, formatRateValue } from "../../utils/units";
import PanelControls, { getStoredSelection } from "../PanelControls";

interface NodeComparePanelProps {
  selectedNodes: string[];
}

type IntervalOption = "1h" | "1d" | "7d" | "30d";
const INTERVAL_VALUES = ["1h", "1d", "7d", "30d"] as const satisfies readonly IntervalOption[];
type ModeOption = "speed" | "size" | "count";
const MODE_VALUES = ["speed", "size", "count"] as const satisfies readonly ModeOption[];

const INTERVAL_OPTIONS: ReadonlyArray<{
  id: IntervalOption;
  label: string;
  subtitle: string;
  refreshMs: number;
}> = [
  { id: "1h", label: "1h", subtitle: "Last 1 hour", refreshMs: 60_000 },
  { id: "1d", label: "1d", subtitle: "Last 1 day", refreshMs: 60_000 },
  { id: "7d", label: "7d", subtitle: "Last 7 days", refreshMs: 300_000 },
  { id: "30d", label: "30d", subtitle: "Last 30 days", refreshMs: 300_000 },
];

const MODE_OPTIONS: ReadonlyArray<{ id: ModeOption; label: string }> = [
  { id: "speed", label: "Speed" },
  { id: "size", label: "Size" },
  { id: "count", label: "Count" },
];

const NODE_PALETTE = [
  "#38BDF8",
  "#22C55E",
  "#818CF8",
  "#F472B6",
  "#14B8A6",
  "#F97316",
  "#EAB308",
  "#A855F7",
  "#FACC15",
  "#2DD4BF",
];

const USAGE_NEGATIVE_RING_STROKE = "#DC2626";
const USAGE_NEGATIVE_RING_STROKE_WIDTH = 2;

const INTERVAL_TO_INTERVAL_DAYS: Record<IntervalOption, number> = {
  "1h": 0,
  "1d": 1,
  "7d": 7,
  "30d": 30,
};

interface ChartSlice {
  name: string;
  value: number;
  color: string;
  rawValue?: number;
  percentBase?: number;
  totalBase?: number;
  isPlaceholder?: boolean;
}

interface SinglePieChartConfig {
  id: string;
  label: string;
  slices: ChartSlice[];
  total: number;
  formatValue: (value: number) => { display: string; unit: string };
  tooltipLabel: string;
}

interface DualRingChartConfig {
  id: string;
  label: string;
  innerSlices: ChartSlice[];
  innerTotal: number;
  outerSlices: ChartSlice[];
  outerTotal: number;
  formatValue: (value: number) => { display: string; unit: string };
  tooltipLabel: string;
}

const EMPTY_RESPONSE: TransferTotalsResponse = {
  intervalSeconds: 0,
  totals: {},
};

const formatPercentMetric = (value: number): { display: string; unit: string } => ({
  display: Number.isFinite(value)
    ? (value >= 100 || value === 0 ? value.toFixed(0) : value.toFixed(1))
    : "0",
  unit: "%",
});

const TooltipContent: FC<{
  active?: boolean;
  payload?: any[];
  label?: string;
  total?: number;
  formatValue: (value: number) => { display: string; unit: string };
  rowLabel?: string;
}> = ({ active, payload, label, total, formatValue, rowLabel = "Transferred" }) => {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  const entry = payload[0];
  if (entry?.payload?.isPlaceholder) {
    return null;
  }
  const nodeName = entry?.payload?.name ?? label ?? "Node";
  const rawValue = typeof entry?.payload?.rawValue === "number"
    ? entry.payload.rawValue
    : Number(entry?.value ?? 0);
  const percentBase = typeof entry?.payload?.percentBase === "number"
    ? entry.payload.percentBase
    : Math.abs(rawValue);
  const totalOverride = typeof entry?.payload?.totalBase === "number"
    ? entry.payload.totalBase
    : undefined;
  const totalValue = typeof totalOverride === "number"
    ? totalOverride
    : (typeof total === "number" && Number.isFinite(total) ? total : 0);
  const { display, unit } = formatValue(rawValue);
  const percent = totalValue > 0 ? (percentBase / totalValue) * 100 : 0;
  const percentFormatted = percent >= 100 || percent === 0 ? percent.toFixed(0) : percent.toFixed(1);

  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__label">{nodeName}</div>
      <div className="chart-tooltip__row">
        <span>{rowLabel}</span>
        <span>
          <strong>{display} {unit}</strong>
          {totalValue > 0 ? <span style={{ marginLeft: 6 }}>({percentFormatted}%)</span> : null}
        </span>
      </div>
    </div>
  );
};

const NodeComparePanel: FC<NodeComparePanelProps> = ({ selectedNodes }) => {
  const { isVisible } = usePanelVisibilityStore();
  const isPanelVisible = isVisible("nodeCompare");

  const [interval, setIntervalOption] = useState<IntervalOption>(() =>
    getStoredSelection<IntervalOption>("monstr.panel.NodeCompare.interval", INTERVAL_VALUES, "1d"),
  );
  const [mode, setMode] = useState<ModeOption>(() =>
    getStoredSelection<ModeOption>("monstr.panel.NodeCompare.mode", MODE_VALUES, "size"),
  );
  const [data, setData] = useState<TransferTotalsResponse>(EMPTY_RESPONSE);
  const [usageChange, setUsageChange] = useState<DiskUsageChangeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [usageChangeError, setUsageChangeError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const requestIdRef = useRef(0);
  const mountedRef = useRef(true);
  const deduperRef = useRef(createRequestDeduper());

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const intervalMeta = useMemo(() => INTERVAL_OPTIONS.find((opt) => opt.id === interval) ?? INTERVAL_OPTIONS[1], [interval]);
  const refreshDelay = intervalMeta.refreshMs;

  const load = useCallback(async () => {
    if (!isPanelVisible) {
      return;
    }
    const deduper = deduperRef.current;
    const nodesArg = selectedNodes.length === 0 ? [] : [...selectedNodes];
    if (deduper.isDuplicate(nodesArg, 1000)) return;
    const requestId = ++requestIdRef.current;
    setIsLoading(true);
    setError(null);
    if (mountedRef.current && requestId === requestIdRef.current && interval === "1h") {
      setUsageChange(null);
      setUsageChangeError(null);
    }

    try {
      const response = await fetchTransferTotals(nodesArg, interval);
      if (mountedRef.current && requestId === requestIdRef.current) {
        setData(response);
      }

      if (interval !== "1h") {
        const intervalDays = INTERVAL_TO_INTERVAL_DAYS[interval] ?? 0;
        try {
          const usageChangeResponse = await fetchDiskUsageChange(nodesArg, intervalDays);
          if (mountedRef.current && requestId === requestIdRef.current) {
            setUsageChange(usageChangeResponse);
            setUsageChangeError(null);
          }
        } catch (cause) {
          if (mountedRef.current && requestId === requestIdRef.current) {
            const message = cause instanceof Error && cause.message
              ? cause.message
              : "Failed to load disk usage changes";
            setUsageChange(null);
            setUsageChangeError(message);
          }
        }
      }
    } catch (cause) {
      if (mountedRef.current && requestId === requestIdRef.current) {
        const message = cause instanceof Error && cause.message ? cause.message : "Failed to load node totals";
        setError(message);
        setData(EMPTY_RESPONSE);
        setUsageChange(null);
        setUsageChangeError(null);
      }
    } finally {
      if (mountedRef.current && requestId === requestIdRef.current) {
        setIsLoading(false);
      }
    }
  }, [interval, isPanelVisible, selectedNodes]);

  useEffect(() => {
    if (!isPanelVisible) {
      return;
    }

    void load();
    if (typeof window === "undefined") {
      return;
    }

    const timer = window.setInterval(() => {
      void load();
    }, refreshDelay);

    return () => {
      window.clearInterval(timer);
    };
  }, [isPanelVisible, load, refreshDelay]);

  const totalsEntries = useMemo(() => {
    const entries = Object.entries(data.totals ?? {});
    entries.sort((a, b) => a[0].localeCompare(b[0]));
    return entries;
  }, [data.totals]);
  const allNodesForColor = useMemo(() => {
    const names = new Set<string>();
    totalsEntries.forEach(([node]) => names.add(node));
    if (usageChange?.nodes) {
      Object.keys(usageChange.nodes).forEach((node) => names.add(node));
    }
    selectedNodes.forEach((node) => names.add(node));
    return Array.from(names).sort((a, b) => a.localeCompare(b));
  }, [totalsEntries, usageChange, selectedNodes]);

  const colorByNode = useMemo(() => {
    const map = new Map<string, string>();
    allNodesForColor.forEach((node, index) => {
      map.set(node, NODE_PALETTE[index % NODE_PALETTE.length]);
    });
    return map;
  }, [allNodesForColor]);

  const formatUsageChangeMetric = useCallback((value: number): { display: string; unit: string } => {
    const magnitude = Math.abs(value);
    const { value: formattedValue, unit } = pickSizePresentation(magnitude);
    const formatted = formatSizeValue(formattedValue);
    const sign = value < 0 ? "-" : "";
    return { display: `${sign}${formatted}`, unit };
  }, []);

  const {
    transferCharts,
    transferLegendNodes,
    hasTransferData,
  } = useMemo(() => {
    const slices: {
      download: ChartSlice[];
      upload: ChartSlice[];
      downloadSuccessRate: ChartSlice[];
      uploadSuccessRate: ChartSlice[];
    } = {
      download: [],
      upload: [],
      downloadSuccessRate: [],
      uploadSuccessRate: [],
    };

    const legendNodes = new Set<string>();

    const formatSizeMetric = (value: number): { display: string; unit: string } => {
      const { value: displayValue, unit } = pickSizePresentation(value);
      return { display: formatSizeValue(displayValue), unit };
    };

    const formatSpeedMetric = (value: number): { display: string; unit: string } => {
      const bitsPerSecond = value * 8;
      const { value: rateValue, unit } = pickRatePresentation(bitsPerSecond);
      return { display: formatRateValue(rateValue), unit };
    };

    const formatCountMetric = (value: number): { display: string; unit: string } => ({
      display: Number.isFinite(value) ? Math.round(value).toString() : "0",
      unit: "ops",
    });

    const intervalSeconds = Number(data.intervalSeconds ?? 0);
    const safeIntervalSeconds = intervalSeconds > 0 ? intervalSeconds : 1;

    const resolveFormatter = (): ((value: number) => { display: string; unit: string }) => {
      if (mode === "speed") {
        return formatSpeedMetric;
      }
      if (mode === "count") {
        return formatCountMetric;
      }
      return formatSizeMetric;
    };

    const activeFormatter = resolveFormatter();

    totalsEntries.forEach(([node, totals], index) => {
      const color = colorByNode.get(node) ?? NODE_PALETTE[index % NODE_PALETTE.length];
      const downloadSize = (totals.sizeDlSuccNor ?? 0) + (totals.sizeDlSuccRep ?? 0);
      const uploadSize = (totals.sizeUlSuccNor ?? 0) + (totals.sizeUlSuccRep ?? 0);
      const downloadFailSize = (totals.sizeDlFailNor ?? 0) + (totals.sizeDlFailRep ?? 0);
      const uploadFailSize = (totals.sizeUlFailNor ?? 0) + (totals.sizeUlFailRep ?? 0);
      const downloadCount = (totals.countDlSuccNor ?? 0) + (totals.countDlSuccRep ?? 0);
      const uploadCount = (totals.countUlSuccNor ?? 0) + (totals.countUlSuccRep ?? 0);
      const downloadFail = (totals.countDlFailNor ?? 0) + (totals.countDlFailRep ?? 0);
      const uploadFail = (totals.countUlFailNor ?? 0) + (totals.countUlFailRep ?? 0);

      let downloadValue = downloadSize;
      let uploadValue = uploadSize;

      if (mode === "speed") {
        downloadValue = downloadSize / safeIntervalSeconds;
        uploadValue = uploadSize / safeIntervalSeconds;
      } else if (mode === "count") {
        downloadValue = downloadCount;
        uploadValue = uploadCount;
      }

      slices.download.push({ name: node, value: downloadValue, color });
      slices.upload.push({ name: node, value: uploadValue, color });
      const downloadSuccessNumerator = mode === "count" ? downloadCount : downloadSize;
      const downloadSuccessDenominator = mode === "count"
        ? downloadCount + downloadFail
        : downloadSize + downloadFailSize;
      const uploadSuccessNumerator = mode === "count" ? uploadCount : uploadSize;
      const uploadSuccessDenominator = mode === "count"
        ? uploadCount + uploadFail
        : uploadSize + uploadFailSize;

      const downloadSuccessRate = downloadSuccessDenominator > 0
        ? (downloadSuccessNumerator / downloadSuccessDenominator) * 100
        : 0;
      const uploadSuccessRate = uploadSuccessDenominator > 0
        ? (uploadSuccessNumerator / uploadSuccessDenominator) * 100
        : 0;
      slices.downloadSuccessRate.push({ name: node, value: downloadSuccessRate, color });
      slices.uploadSuccessRate.push({ name: node, value: uploadSuccessRate, color });

      const hasNodeData = downloadValue > 0
        || uploadValue > 0
        || downloadSuccessDenominator > 0
        || uploadSuccessDenominator > 0;

      if (hasNodeData) {
        legendNodes.add(node);
      }
    });

    const downloadTotal = slices.download.reduce((acc, entry) => acc + entry.value, 0);
    const uploadTotal = slices.upload.reduce((acc, entry) => acc + entry.value, 0);
    const downloadSuccessRateTotal = slices.downloadSuccessRate.reduce((acc, entry) => acc + entry.value, 0);
    const uploadSuccessRateTotal = slices.uploadSuccessRate.reduce((acc, entry) => acc + entry.value, 0);

    const configs: SinglePieChartConfig[] = [
      {
        id: "download",
        label: "Download",
        slices: slices.download,
        total: downloadTotal,
        formatValue: activeFormatter,
        tooltipLabel: "Transferred",
      },
      {
        id: "upload",
        label: "Upload",
        slices: slices.upload,
        total: uploadTotal,
        formatValue: activeFormatter,
        tooltipLabel: "Transferred",
      },
      {
        id: "download-success-rate",
        label: "DL Success Rate",
        slices: slices.downloadSuccessRate,
        total: downloadSuccessRateTotal,
        formatValue: formatPercentMetric,
        tooltipLabel: "Success Rate",
      },
      {
        id: "upload-success-rate",
        label: "UL Success Rate",
        slices: slices.uploadSuccessRate,
        total: uploadSuccessRateTotal,
        formatValue: formatPercentMetric,
        tooltipLabel: "Success Rate",
      },
    ];

    return {
      transferCharts: configs,
      transferLegendNodes: Array.from(legendNodes),
      hasTransferData: configs.some((config) => config.slices.some((slice) => slice.value > 0)),
    };
  }, [colorByNode, data.intervalSeconds, mode, totalsEntries]);

  const {
    config: usageChangeConfig,
    legendNodes: usageChangeLegendNodes,
  } = useMemo(() => {
    if (!usageChange || interval === "1h") {
      return { config: null, legendNodes: [] as string[], hasData: false };
    }

    const nodes = usageChange.nodes ?? {};
    // Split usage deltas into negative (inner ring) and positive (outer ring) slices.
    const negativeSlicesRaw: ChartSlice[] = [];
    const positiveSlicesRaw: ChartSlice[] = [];
    const legendNodes = new Set<string>();

    for (const [node, metrics] of Object.entries(nodes)) {
      if (!metrics) {
        continue;
      }

      const change = Number(metrics.usageChange ?? 0);
      if (!Number.isFinite(change) || change === 0) {
        continue;
      }

      const color = colorByNode.get(node) ?? NODE_PALETTE[0];
      const slice: ChartSlice = {
        name: node,
        value: Math.abs(change),
        color,
        rawValue: change,
      };

      if (change < 0) {
        negativeSlicesRaw.push(slice);
      } else {
        positiveSlicesRaw.push(slice);
      }

      legendNodes.add(node);
    }

    const negativeTotal = negativeSlicesRaw.reduce((acc, slice) => acc + slice.value, 0);
    const positiveTotal = positiveSlicesRaw.reduce((acc, slice) => acc + slice.value, 0);
    const sharedTotal = Math.max(negativeTotal, positiveTotal);

    if (sharedTotal <= 0) {
      return { config: null, legendNodes: [] as string[], hasData: false };
    }

    const normalizeSlices = (items: ChartSlice[], total: number, placeholderId: string): ChartSlice[] => {
      if (total <= 0) {
        return [];
      }
      const normalized = items.map((slice) => ({
        ...slice,
        percentBase: slice.value,
        totalBase: sharedTotal,
      }));
      if (total < sharedTotal) {
        normalized.push({
          name: placeholderId,
          value: sharedTotal - total,
          color: "transparent",
          rawValue: 0,
          percentBase: 0,
          totalBase: sharedTotal,
          isPlaceholder: true,
        });
      }
      return normalized;
    };

    const innerSlices = negativeTotal > 0
      ? normalizeSlices(negativeSlicesRaw, negativeTotal, "usage-negative-placeholder")
      : [];
    const outerSlices = positiveTotal > 0
      ? normalizeSlices(positiveSlicesRaw, positiveTotal, "usage-positive-placeholder")
      : [];

    return {
      config: {
        id: "usage-change",
        label: "Usage Change",
        type: "dual",
        innerSlices,
        innerTotal: negativeTotal,
        outerSlices,
        outerTotal: positiveTotal,
        formatValue: formatUsageChangeMetric,
        tooltipLabel: "Usage",
      } as DualRingChartConfig,
      legendNodes: Array.from(legendNodes),
      hasData: innerSlices.length > 0 || outerSlices.length > 0,
    };
  }, [colorByNode, formatUsageChangeMetric, interval, usageChange]);

  const {
    config: ulGrowConfig,
    legendNodes: ulGrowLegendNodes,
  } = useMemo(() => {
    if (!usageChange || interval === "1h") {
      return { config: null, legendNodes: [] as string[], hasData: false };
    }

    const usageByNode = usageChange.nodes ?? {};
    const negativeRaw: ChartSlice[] = [];
    const positiveRaw: ChartSlice[] = [];
    const legendNodes = new Set<string>();

    totalsEntries.forEach(([node, totals], index) => {
      const metrics = usageByNode[node];
      if (!metrics) return;
      const change = Number(metrics.usageChange ?? 0);
      if (!Number.isFinite(change) || change === 0) return;

        const uploadSize = (totals.sizeUlSuccNor ?? 0) + (totals.sizeUlSuccRep ?? 0);
        if (!(uploadSize > 0)) return;

        const ratio = (change / uploadSize) * 100;
      if (!Number.isFinite(ratio) || ratio === 0) return;

      const color = colorByNode.get(node) ?? NODE_PALETTE[index % NODE_PALETTE.length];
      const slice: ChartSlice = {
        name: node,
        value: Math.abs(ratio),
        color,
        rawValue: ratio,
      };
      if (change < 0) {
        negativeRaw.push(slice);
      } else {
        positiveRaw.push(slice);
      }
      legendNodes.add(node);
    });

    const negativeTotal = negativeRaw.reduce((acc, s) => acc + s.value, 0);
    const positiveTotal = positiveRaw.reduce((acc, s) => acc + s.value, 0);
    const sharedTotal = Math.max(negativeTotal, positiveTotal);
    if (sharedTotal <= 0) {
      return { config: null, legendNodes: [] as string[], hasData: false };
    }

    const normalize = (items: ChartSlice[], total: number, placeholderId: string) => {
      if (total <= 0) return [] as ChartSlice[];
      const normalized = items.map((slice) => ({ ...slice, percentBase: slice.value, totalBase: sharedTotal }));
      if (total < sharedTotal) {
        normalized.push({
          name: placeholderId,
          value: sharedTotal - total,
          color: "transparent",
          rawValue: 0,
          percentBase: 0,
          totalBase: sharedTotal,
          isPlaceholder: true,
        });
      }
      return normalized;
    };

    const innerSlices = negativeTotal > 0 ? normalize(negativeRaw, negativeTotal, "ulgrow-negative-placeholder") : [];
    const outerSlices = positiveTotal > 0 ? normalize(positiveRaw, positiveTotal, "ulgrow-positive-placeholder") : [];

    return {
      config: {
        id: "ul-grow-ratio",
        label: "UL Grow Ratio",
        type: "dual",
        innerSlices,
        innerTotal: negativeTotal,
        outerSlices,
        outerTotal: positiveTotal,
        formatValue: formatPercentMetric,
        tooltipLabel: "UL / UsageChange",
      } as DualRingChartConfig,
      legendNodes: Array.from(legendNodes),
      hasData: innerSlices.length > 0 || outerSlices.length > 0,
    };
  }, [colorByNode, interval, totalsEntries, usageChange]);

  const downloadSizeRatioChart = useMemo<SinglePieChartConfig | null>(() => {
    if (!usageChange || interval === "1h") {
      return null;
    }

    const usageByNode = usageChange.nodes ?? {};
    const slices: ChartSlice[] = [];

    totalsEntries.forEach(([node, totals], index) => {
      const usageMetrics = usageByNode[node];
      if (!usageMetrics) {
        return;
      }

      const usageEnd = Number(usageMetrics.usageEnd ?? 0);
      const usageChangeValue = Number(usageMetrics.usageChange ?? 0);
      // Use midpoint between start and end usage as a stable baseline for the ratio.
      const averageUsage = usageEnd - usageChangeValue / 2;
      if (!(averageUsage > 0)) {
        return;
      }

      // Always rely on successful download size for the ratio, regardless of the active mode in the UI.
      const downloadSize = (totals.sizeDlSuccNor ?? 0) + (totals.sizeDlSuccRep ?? 0);
      if (!(downloadSize > 0)) {
        return;
      }

      const ratio = (downloadSize / averageUsage) * 100;
      if (!Number.isFinite(ratio) || !(ratio > 0)) {
        return;
      }

      const color = colorByNode.get(node) ?? NODE_PALETTE[index % NODE_PALETTE.length];
      slices.push({
        name: node,
        value: ratio,
        color,
        rawValue: ratio,
      });
    });

    if (slices.length === 0) {
      return null;
    }

    const totalRatio = slices.reduce((acc, slice) => acc + slice.value, 0);
    if (totalRatio > 0) {
      slices.forEach((slice) => {
        slice.percentBase = slice.value;
        slice.totalBase = totalRatio;
      });
    }

    return {
      id: "download-size-ratio",
      label: "DL Size Ratio",
      slices,
      total: totalRatio,
      formatValue: formatPercentMetric,
      tooltipLabel: "Download / Usage",
    };
  }, [colorByNode, interval, totalsEntries, usageChange]);

  const usageEndChart = useMemo<SinglePieChartConfig | null>(() => {
    if (!usageChange || interval === "1h") {
      return null;
    }

    const usageByNode = usageChange.nodes ?? {};
    const slices: ChartSlice[] = [];

    totalsEntries.forEach(([node], index) => {
      const usageMetrics = usageByNode[node];
      if (!usageMetrics) return;
      const usageEnd = Number(usageMetrics.usageEnd ?? 0);
      if (!(usageEnd > 0)) return;
      const color = colorByNode.get(node) ?? NODE_PALETTE[index % NODE_PALETTE.length];
      slices.push({ name: node, value: usageEnd, color, rawValue: usageEnd });
    });

    if (slices.length === 0) return null;

    const total = slices.reduce((acc, s) => acc + s.value, 0);
    slices.forEach((s) => {
      s.percentBase = s.value;
      s.totalBase = total;
    });

    return {
      id: "node-size",
      label: "Node Size",
      slices,
      total,
      formatValue: formatUsageChangeMetric,
      tooltipLabel: "Size",
    };
  }, [colorByNode, interval, totalsEntries, usageChange, formatUsageChangeMetric]);

  const chartConfigs = useMemo<(SinglePieChartConfig | DualRingChartConfig)[]>(() => {
    const configs: (SinglePieChartConfig | DualRingChartConfig)[] = [];
    if (hasTransferData) {
      configs.push(...transferCharts);
    }
    if (downloadSizeRatioChart) {
      configs.push(downloadSizeRatioChart);
    }
    if (usageEndChart) {
      configs.push(usageEndChart);
    }
    if (usageChangeConfig) {
      configs.push(usageChangeConfig);
    }
    if (ulGrowConfig) {
      configs.push(ulGrowConfig);
    }
    return configs;
  }, [downloadSizeRatioChart, hasTransferData, transferCharts, usageChangeConfig, ulGrowConfig, usageEndChart]);

  const legendItems = useMemo(() => {
    const nodes = new Set<string>();
    transferLegendNodes.forEach((node) => nodes.add(node));
    usageChangeLegendNodes.forEach((node) => nodes.add(node));
    ulGrowLegendNodes.forEach((node) => nodes.add(node));

    const ordered = Array.from(nodes).sort((a, b) => a.localeCompare(b));
    return ordered.map((node) => ({
      label: node,
      color: colorByNode.get(node) ?? NODE_PALETTE[0],
    }));
  }, [colorByNode, transferLegendNodes, usageChangeLegendNodes, ulGrowLegendNodes]);

  const hasChartContent = chartConfigs.length > 0;

  if (!isPanelVisible) {
    return null;
  }

  return (
    <section className="panel">
      <PanelHeader
        title="Node Compare"
        subtitle={<PanelSubtitle selectedNodes={selectedNodes}>Interval: {intervalMeta.subtitle}</PanelSubtitle>}
        onRefresh={() => void load()}
        isRefreshing={isLoading}
        controls={(
          <>
            <PanelControls
              ariaLabel="Display mode"
              storageKey="monstr.panel.NodeCompare.mode"
              buttons={MODE_OPTIONS.map((opt) => (
                <PanelControlsButton
                  key={opt.id}
                  active={mode === opt.id}
                  onClick={() => setMode(opt.id)}
                  content={opt.label}
                />
              ))}
            />
            <PanelControls
              ariaLabel="Interval"
              storageKey="monstr.panel.NodeCompare.interval"
              buttons={INTERVAL_OPTIONS.map((opt) => (
                <PanelControlsButton
                  key={opt.id}
                  active={interval === opt.id}
                  onClick={() => setIntervalOption(opt.id)}
                  content={opt.label}
                />
              ))}
            />
          </>
        )}
      />

      <div className="panel__body">
        {error ? <p className="panel__error">{error}</p> : null}
        {!error && !hasChartContent ? (
          <p className="panel__empty">No transfer totals for the selected window.</p>
        ) : null}

        {usageChangeError && interval !== "1h" ? <p className="panel__error">{usageChangeError}</p> : null}

        {hasChartContent ? (
          <div className="node-compare-charts">
            {chartConfigs.map((config) => {
              const isDual = (config as DualRingChartConfig).innerSlices !== undefined;
              if (!isDual) {
                const single = config as SinglePieChartConfig;
                return (
                  <div className="node-compare-chart" key={single.id}>
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={single.slices} dataKey="value" nameKey="name" innerRadius={20} outerRadius={45} paddingAngle={0} isAnimationActive={false}>
                          {single.slices.map((slice) => (
                            <Cell key={slice.name} fill={slice.color} />
                          ))}
                        </Pie>
                        <Tooltip
                          content={(
                            <TooltipContent
                              total={single.total}
                              formatValue={single.formatValue}
                              rowLabel={single.tooltipLabel}
                            />
                          )}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                    <p className="node-compare-chart__label">{single.label}</p>
                  </div>
                );
              }

              const dual = config as DualRingChartConfig;
              const hasInner = dual.innerSlices && dual.innerSlices.length > 0;
              const hasOuter = dual.outerSlices && dual.outerSlices.length > 0;
              const negativeInnerRadius = hasOuter ? 15 : 20;
              const negativeOuterRadius = hasOuter ? 27 : 45;
              const positiveInnerRadius = hasInner ? 28 : 20;
              const positiveOuterRadius = 45;

              return (
                <div className="node-compare-chart node-compare-chart--usage" key={dual.id}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      {hasInner ? (
                        <Pie
                          data={dual.innerSlices}
                          dataKey="value"
                          nameKey="name"
                          innerRadius={negativeInnerRadius}
                          outerRadius={negativeOuterRadius}
                          paddingAngle={0}
                          isAnimationActive={false}
                          stroke={USAGE_NEGATIVE_RING_STROKE}
                          strokeWidth={USAGE_NEGATIVE_RING_STROKE_WIDTH}
                        >
                          {dual.innerSlices.map((slice) => (
                            <Cell key={`${slice.name}-inner`} fill={slice.color} />
                          ))}
                        </Pie>
                      ) : null}
                      {hasOuter ? (
                        <Pie
                          data={dual.outerSlices}
                          dataKey="value"
                          nameKey="name"
                          innerRadius={positiveInnerRadius}
                          outerRadius={positiveOuterRadius}
                          paddingAngle={0}
                          isAnimationActive={false}
                        >
                          {dual.outerSlices.map((slice) => (
                            <Cell key={`${slice.name}-outer`} fill={slice.color} />
                          ))}
                        </Pie>
                      ) : null}
                      <Tooltip
                        content={(
                          <TooltipContent
                            total={undefined}
                            formatValue={dual.formatValue}
                            rowLabel={dual.tooltipLabel}
                          />
                        )}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  <p className="node-compare-chart__label">{dual.label}</p>
                </div>
              );
            })}
          </div>
        ) : null}

        {legendItems.length > 0 ? <Legend items={legendItems} fontSize={14} /> : null}
      </div>
    </section>
  );
};

export default NodeComparePanel;
