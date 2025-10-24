import axios from "axios";

import type { LogEntry, LogEntryQueryParams } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10_000
});

const mapLogEntry = (payload: Record<string, unknown>): LogEntry => ({
  id: Number(payload.id),
  source: String(payload.source ?? ""),
  content: String(payload.content ?? ""),
  ingestedAt: String(payload.ingested_at ?? payload.ingestedAt ?? ""),
  processed: Boolean(payload.processed)
});

export const fetchLogEntries = async (
  params: LogEntryQueryParams = {}
): Promise<LogEntry[]> => {
  const response = await apiClient.get("/logs", { params });
  return response.data.map((item: Record<string, unknown>) => mapLogEntry(item));
};
