import axios from "axios";

import { translateSatelliteId } from "../constants/satellites";
import type {
  NodeInfo,
  NodeReputation,
  PaystubPeriodsResponse,
  PaystubRecord,
  SatelliteReputation,
  TransferActualCategoryMetrics,
  TransferActualData,
  TransferActualMetrics,
  TransferActualSatelliteMetrics,
  TransferTotalsNode,
  TransferTotalsResponse,
  DiskUsageChangeResponse,
  DiskUsageUsageMode,
  DiskUsageUsageNode,
  DiskUsageUsageResponse,
  IP24StatusResponse,
} from "../types";

const DEFAULT_API_BASE_URL = import.meta.env.DEV ? "http://localhost:8000/api" : "/api";
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL;

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10_000
});

export const fetchNodes = async (): Promise<NodeInfo[]> => {
  const response = await apiClient.get("/nodes");
  const { data } = response;
  const items = Array.isArray(data)
    ? data
    : data && typeof data === "object" && Array.isArray((data as Record<string, unknown>).nodes)
    ? (data as { nodes: unknown[] }).nodes
    : undefined;

  if (!Array.isArray(items)) {
    throw new Error("Unexpected nodes response format");
  }

  return items.map((item: Record<string, unknown>) => {
    const name = String(item.name ?? "");
    const path = String(item.path ?? "");
    const rawNodeapi = item.nodeapi;
    const nodeapiValue = typeof rawNodeapi === "string" && rawNodeapi.trim().length > 0
      ? rawNodeapi
      : undefined;

    const vettingSource = (item as Record<string, unknown>).vetting ?? (item as Record<string, unknown>).vetting_date;
    let vetting: Record<string, string | null> | undefined;
    if (vettingSource && typeof vettingSource === "object" && !Array.isArray(vettingSource)) {
      const normalized: Record<string, string | null> = {};
      for (const [satelliteId, value] of Object.entries(vettingSource as Record<string, unknown>)) {
        if (!satelliteId) {
          continue;
        }
        normalized[satelliteId] = value == null ? null : String(value);
      }
      if (Object.keys(normalized).length > 0) {
        vetting = normalized;
      }
    }

    return {
      name,
      path,
      nodeapi: nodeapiValue,
      vetting,
    } satisfies NodeInfo;
  });
};

export const fetchReputationsPanel = async (nodes: string[]): Promise<NodeReputation[]> => {
  const response = await apiClient.post("/reputations/panel", { nodes });
  const { data } = response;

  if (!Array.isArray(data)) {
    throw new Error("Unexpected reputations response format");
  }

  const toNumber = (value: unknown) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  };

  const toSatellite = (sat: unknown): SatelliteReputation | null => {
    if (!sat || typeof sat !== "object") {
      return null;
    }

    const record = sat as Record<string, unknown>;

    const satelliteId = String(record.satellite_id ?? "");

    return {
      satelliteId,
      satelliteName: translateSatelliteId(satelliteId),
      timestamp: String(record.timestamp ?? ""),
      auditsTotal: toNumber(record.audits_total),
      auditsSuccess: toNumber(record.audits_success),
      scoreAudit: toNumber(record.score_audit),
      scoreOnline: toNumber(record.score_online),
      scoreSuspension: toNumber(record.score_suspension),
    };
  };

  return data.map((item) => {
    const nodeRecord = (item ?? {}) as Record<string, unknown>;
    const satellites = Array.isArray(nodeRecord.satellites)
      ? nodeRecord.satellites
          .map(toSatellite)
          .filter((value): value is SatelliteReputation => value !== null)
      : [];

    return {
      node: String(nodeRecord.node ?? ""),
      satellites,
    } satisfies NodeReputation;
  });
};

const toNumeric = (value: unknown): number => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const extractMetrics = (value: unknown): TransferActualMetrics => {
  if (!value || typeof value !== "object") {
    return { operationsTotal: 0, operationsSuccess: 0, dataBytes: 0, rate: 0 };
  }

  const record = value as Record<string, unknown>;
  const operationsTotal = toNumeric(record.operationsTotal ?? record.operations_total);
  const operationsSuccess = toNumeric(record.operationsSuccess ?? record.operations_success);
  const rate = toNumeric(record.rate);
  const dataBytes = Math.max(0, toNumeric(record.dataBytes ?? record.data_bytes));

  return { operationsTotal, operationsSuccess, dataBytes, rate };
};

const extractCategoryMetrics = (category: unknown): TransferActualCategoryMetrics => {
  if (!category || typeof category !== "object") {
    return { normal: extractMetrics(null), repair: extractMetrics(null) };
  }

  const record = category as Record<string, unknown>;
  return {
    normal: extractMetrics(record.normal),
    repair: extractMetrics(record.repair),
  };
};

const extractSatelliteMetrics = (item: unknown): TransferActualSatelliteMetrics | null => {
  if (!item || typeof item !== "object") {
    return null;
  }

  const record = item as Record<string, unknown>;
  const satelliteId = String(record.satelliteId ?? record.satellite_id ?? "");

  return {
    satelliteId,
    satelliteName: translateSatelliteId(satelliteId),
    download: extractCategoryMetrics(record.download),
    upload: extractCategoryMetrics(record.upload),
  };
};

export const fetchActualPerformance = async (
  nodes: string[],
): Promise<TransferActualData> => {
  const response = await apiClient.post("/transfers/actual", { nodes });
  const { data } = response;

  if (!data || typeof data !== "object") {
    throw new Error("Unexpected actual performance response format");
  }

  const record = data as Record<string, unknown>;

  const startTime = String(record.startTime ?? record.start_time ?? "");
  const endTime = String(record.endTime ?? record.end_time ?? "");
  const satellitesRaw = Array.isArray(record.satellites) ? record.satellites : [];
  const satellites = satellitesRaw
    .map(extractSatelliteMetrics)
    .filter((value): value is TransferActualSatelliteMetrics => value !== null);

  return {
    startTime,
    endTime,
    download: extractCategoryMetrics(record.download),
    upload: extractCategoryMetrics(record.upload),
    satellites,
  };
};

export const fetchDataDistribution = async (nodes: string[]) => {
  const response = await apiClient.post("/transfer-grouped/data-distribution", { nodes });
  return response.data;
};

export const fetchPayoutCurrent = async (nodes: string[]) => {
  const response = await apiClient.post("/payout/current", { nodes });
  return response.data;
};

export const fetchPayoutPaystubs = async (nodes: string[]): Promise<PaystubPeriodsResponse> => {
  const response = await apiClient.post("/payout/paystubs", { nodes });
  const raw = response.data;

  const ensureNumber = (value: unknown): number => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  };

  const sanitizeRecord = (item: Record<string, unknown>): PaystubRecord => ({
    source: String(item.source ?? ""),
    satelliteId: String(item.satelliteId ?? item.satellite_id ?? ""),
    period: String(item.period ?? ""),
    created: String(item.created ?? ""),
    usageAtRest: ensureNumber(item.usageAtRest ?? item.usage_at_rest),
    usageGet: ensureNumber(item.usageGet ?? item.usage_get),
    usagePut: ensureNumber(item.usagePut ?? item.usage_put),
    usageGetRepair: ensureNumber(item.usageGetRepair ?? item.usage_get_repair),
    usagePutRepair: ensureNumber(item.usagePutRepair ?? item.usage_put_repair),
    usageGetAudit: ensureNumber(item.usageGetAudit ?? item.usage_get_audit),
    compAtRest: ensureNumber(item.compAtRest ?? item.comp_at_rest),
    compGet: ensureNumber(item.compGet ?? item.comp_get),
    compPut: ensureNumber(item.compPut ?? item.comp_put),
    compGetRepair: ensureNumber(item.compGetRepair ?? item.comp_get_repair),
    compPutRepair: ensureNumber(item.compPutRepair ?? item.comp_put_repair),
    compGetAudit: ensureNumber(item.compGetAudit ?? item.comp_get_audit),
    surgePercent: ensureNumber(item.surgePercent ?? item.surge_percent),
    held: ensureNumber(item.held),
    owed: ensureNumber(item.owed),
    disposed: ensureNumber(item.disposed),
    paid: ensureNumber(item.paid),
    distributed: ensureNumber(item.distributed),
  });

  const periods: Record<string, PaystubRecord[]> = {};
  const rawPeriods =
    raw && typeof raw === "object" && raw !== null && "periods" in raw
      ? ((raw as { periods?: unknown }).periods ?? {})
      : {};

  if (rawPeriods && typeof rawPeriods === "object") {
    for (const [period, records] of Object.entries(rawPeriods as Record<string, unknown>)) {
      if (!Array.isArray(records)) {
        continue;
      }

      const normalized: PaystubRecord[] = [];
      for (const entry of records) {
        if (!entry || typeof entry !== "object") {
          continue;
        }
        normalized.push(sanitizeRecord(entry as Record<string, unknown>));
      }

      if (normalized.length > 0) {
        periods[period] = normalized;
      }
    }
  }

  return { periods };
};

export const fetchIntervalTransfers = async (nodes: string[], intervalLength: string, numberOfIntervals: number) => {
  const response = await apiClient.post("/transfer-grouped/intervals", { nodes, intervalLength, numberOfIntervals });
  return response.data;
};

export const fetchIp24Status = async (): Promise<IP24StatusResponse> => {
  const response = await apiClient.get("/ip24");
  const data = response.data;
  if (!data || typeof data !== "object") {
    return {};
  }
  return data as IP24StatusResponse;
};

export const fetchTransferTotals = async (nodes: string[], interval: string): Promise<TransferTotalsResponse> => {
  const response = await apiClient.post("/transfer-grouped/totals", { nodes, interval });
  const raw = response.data;

  const totals: Record<string, TransferTotalsNode> = {};
  const rawTotals = raw && typeof raw === "object" ? (raw as Record<string, unknown>).totals : undefined;
  if (rawTotals && typeof rawTotals === "object") {
    for (const [node, entry] of Object.entries(rawTotals as Record<string, unknown>)) {
      if (!entry || typeof entry !== "object") {
        continue;
      }

      const record = entry as Record<string, unknown>;
      totals[node] = {
        sizeDlSuccNor: toNumeric(record.sizeDlSuccNor ?? record.size_dl_succ_nor),
        sizeUlSuccNor: toNumeric(record.sizeUlSuccNor ?? record.size_ul_succ_nor),
        sizeDlFailNor: toNumeric(record.sizeDlFailNor ?? record.size_dl_fail_nor),
        sizeUlFailNor: toNumeric(record.sizeUlFailNor ?? record.size_ul_fail_nor),
        sizeDlSuccRep: toNumeric(record.sizeDlSuccRep ?? record.size_dl_succ_rep),
        sizeUlSuccRep: toNumeric(record.sizeUlSuccRep ?? record.size_ul_succ_rep),
        sizeDlFailRep: toNumeric(record.sizeDlFailRep ?? record.size_dl_fail_rep),
        sizeUlFailRep: toNumeric(record.sizeUlFailRep ?? record.size_ul_fail_rep),
        countDlSuccNor: toNumeric(record.countDlSuccNor ?? record.count_dl_succ_nor),
        countUlSuccNor: toNumeric(record.countUlSuccNor ?? record.count_ul_succ_nor),
        countDlFailNor: toNumeric(record.countDlFailNor ?? record.count_dl_fail_nor),
        countUlFailNor: toNumeric(record.countUlFailNor ?? record.count_ul_fail_nor),
        countDlSuccRep: toNumeric(record.countDlSuccRep ?? record.count_dl_succ_rep),
        countUlSuccRep: toNumeric(record.countUlSuccRep ?? record.count_ul_succ_rep),
        countDlFailRep: toNumeric(record.countDlFailRep ?? record.count_dl_fail_rep),
        countUlFailRep: toNumeric(record.countUlFailRep ?? record.count_ul_fail_rep),
      };
    }
  }

  const intervalSeconds = toNumeric((raw ?? {}) && typeof raw === "object" ? (raw as Record<string, unknown>).intervalSeconds ?? (raw as Record<string, unknown>).interval_seconds : 0);

  return {
    intervalSeconds,
    totals,
  };
};

export const fetchDiskUsageChange = async (
  nodes: string[],
  intervalDays: number,
): Promise<DiskUsageChangeResponse> => {
  const response = await apiClient.post("/diskusage/usage-change", { nodes, intervalDays });
  const raw = response.data ?? {};

  const currentPeriod = String((raw as Record<string, unknown>).currentPeriod ?? (raw as Record<string, unknown>).current_period ?? "");
  const referencePeriod = String((raw as Record<string, unknown>).referencePeriod ?? (raw as Record<string, unknown>).reference_period ?? "");

  const nodesRaw = (raw as Record<string, unknown>).nodes;
  const nodesMap: DiskUsageChangeResponse["nodes"] = {};

  if (nodesRaw && typeof nodesRaw === "object") {
    for (const [node, entry] of Object.entries(nodesRaw as Record<string, unknown>)) {
      if (!entry || typeof entry !== "object") {
        continue;
      }

      const record = entry as Record<string, unknown>;
      nodesMap[node] = {
        freeEnd: toNumeric(record.freeEnd ?? record.free_end),
        usageEnd: toNumeric(record.usageEnd ?? record.usage_end),
        trashEnd: toNumeric(record.trashEnd ?? record.trash_end),
        freeChange: toNumeric(record.freeChange ?? record.free_change),
        usageChange: toNumeric(record.usageChange ?? record.usage_change),
        trashChange: toNumeric(record.trashChange ?? record.trash_change),
      };
    }
  }

  return {
    currentPeriod,
    referencePeriod,
    nodes: nodesMap,
  };
};

export const fetchDiskUsageUsage = async (
  nodes: string[],
  intervalDays: number,
  mode: DiskUsageUsageMode,
): Promise<DiskUsageUsageResponse> => {
  const response = await apiClient.post("/diskusage/usage", { nodes, intervalDays, mode });
  const raw = response.data ?? {};

  const periods: DiskUsageUsageResponse["periods"] = {};
  const periodEntries = (raw as Record<string, unknown>).periods;

  if (periodEntries && typeof periodEntries === "object") {
    for (const [period, periodValue] of Object.entries(periodEntries as Record<string, unknown>)) {
      if (!periodValue || typeof periodValue !== "object") {
        continue;
      }

      const nodesMap: Record<string, DiskUsageUsageNode> = {};
      for (const [nodeName, nodeValue] of Object.entries(periodValue as Record<string, unknown>)) {
        if (!nodeValue || typeof nodeValue !== "object") {
          continue;
        }

        const metrics = nodeValue as Record<string, unknown>;
        nodesMap[nodeName] = {
          capacity: toNumeric(metrics.capacity),
          usage: toNumeric(metrics.usage),
          trash: toNumeric(metrics.trash),
          at: String(metrics.at ?? ""),
        };
      }

      periods[period] = nodesMap;
    }
  }

  return { periods };
};
