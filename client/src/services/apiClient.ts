import axios from "axios";

import { translateSatelliteId } from "../constants/satellites";
import type { NodeInfo, NodeReputation, SatelliteReputation } from "../types";

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
