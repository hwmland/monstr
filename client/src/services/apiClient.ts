import axios from "axios";

import type { NodeInfo } from "../types";

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
