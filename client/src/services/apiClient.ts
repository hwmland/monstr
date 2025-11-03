import axios from "axios";

import { translateSatelliteId } from "../constants/satellites";
import type {
  NodeInfo,
  NodeReputation,
  SatelliteReputation,
  TransferActualCategoryMetrics,
  TransferActualData,
  TransferActualMetrics,
  TransferActualSatelliteMetrics,
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

  return items.map((item: Record<string, unknown>) => ({
    name: String(item.name ?? ""),
    path: String(item.path ?? ""),
  }));
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

export const fetchIntervalTransfers = async (nodes: string[], intervalLength: string, numberOfIntervals: number) => {
  const response = await apiClient.post("/transfer-grouped/intervals", { nodes, intervalLength, numberOfIntervals });
  return response.data;
};
