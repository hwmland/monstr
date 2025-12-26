import { apiClient } from "../services/apiClient";
import type {
  DashAuditEntry,
  DashBandwidth,
  DashBandwidthDailyEgress,
  DashBandwidthDailyEntry,
  DashBandwidthDailyIngress,
  DashDiskSpace,
  DashNodeDetails,
  DashNodeStatistics,
  DashNodeStatus,
  DashSatellite,
  DashStorageDailyEntry,
} from "./types";

const toNumber = (value: unknown): number => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const toStringSafe = (value: unknown): string => {
  return typeof value === "string" ? value : String(value ?? "");
};

const toBoolean = (value: unknown): boolean => value === true || value === "true";

const normalizeSatellite = (value: unknown): DashSatellite | null => {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  const id = toStringSafe(record.id);
  const url = toStringSafe(record.url);
  if (!id && !url) return null;
  return {
    id,
    url,
    disqualified: record.disqualified as boolean | null | undefined,
    suspended: record.suspended as boolean | null | undefined,
  };
};

const normalizeDiskSpace = (value: unknown): DashDiskSpace => {
  if (!value || typeof value !== "object") {
    return { used: 0, available: 0, trash: 0, overused: 0 };
  }
  const record = value as Record<string, unknown>;
  return {
    used: toNumber(record.used),
    available: toNumber(record.available),
    trash: toNumber(record.trash),
    overused: toNumber(record.overused),
  };
};

const normalizeBandwidth = (value: unknown): DashBandwidth => {
  if (!value || typeof value !== "object") {
    return { used: 0, available: 0 };
  }
  const record = value as Record<string, unknown>;
  return {
    used: toNumber(record.used),
    available: toNumber(record.available),
  };
};

const normalizeNodeStatus = (value: unknown): DashNodeStatus => {
  const record = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  const satellitesRaw = Array.isArray(record.satellites) ? record.satellites : [];
  const satellites = satellitesRaw
    .map(normalizeSatellite)
    .filter((item): item is DashSatellite => Boolean(item));

  const walletFeatures = Array.isArray(record.walletFeatures)
    ? record.walletFeatures.map((item) => toStringSafe(item)).filter(Boolean)
    : undefined;

  return {
    nodeID: toStringSafe(record.nodeID ?? record.nodeId),
    wallet: toStringSafe(record.wallet),
    walletFeatures,
    satellites,
    diskSpace: normalizeDiskSpace(record.diskSpace),
    bandwidth: normalizeBandwidth(record.bandwidth),
    lastPinged: toStringSafe(record.lastPinged),
    version: toStringSafe(record.version),
    allowedVersion: toStringSafe(record.allowedVersion),
    upToDate: toBoolean(record.upToDate),
    startedAt: toStringSafe(record.startedAt),
    configuredPort: toStringSafe(record.configuredPort),
    quicStatus: toStringSafe(record.quicStatus),
    lastQuicPingedAt: toStringSafe(record.lastQuicPingedAt),
  };
};

const normalizeStorageDailyEntry = (value: unknown): DashStorageDailyEntry | null => {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  return {
    atRestTotal: toNumber(record.atRestTotal),
    atRestTotalBytes: toNumber(record.atRestTotalBytes),
    intervalStart: toStringSafe(record.intervalStart),
  };
};

const normalizeBandwidthDailyEgress = (value: unknown): DashBandwidthDailyEgress => {
  if (!value || typeof value !== "object") return { repair: 0, audit: 0, usage: 0 };
  const record = value as Record<string, unknown>;
  return {
    repair: toNumber(record.repair),
    audit: toNumber(record.audit),
    usage: toNumber(record.usage),
  };
};

const normalizeBandwidthDailyIngress = (value: unknown): DashBandwidthDailyIngress => {
  if (!value || typeof value !== "object") return { repair: 0, usage: 0 };
  const record = value as Record<string, unknown>;
  return {
    repair: toNumber(record.repair),
    usage: toNumber(record.usage),
  };
};

const normalizeBandwidthDailyEntry = (value: unknown): DashBandwidthDailyEntry | null => {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  return {
    egress: normalizeBandwidthDailyEgress(record.egress),
    ingress: normalizeBandwidthDailyIngress(record.ingress),
    delete: toNumber(record.delete),
    intervalStart: toStringSafe(record.intervalStart),
  };
};

const normalizeAuditEntry = (value: unknown): DashAuditEntry | null => {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  return {
    auditScore: Number(record.auditScore ?? 0),
    suspensionScore: Number(record.suspensionScore ?? 0),
    onlineScore: Number(record.onlineScore ?? 0),
    satelliteName: toStringSafe(record.satelliteName),
  };
};

const normalizeNodeStatistics = (value: unknown): DashNodeStatistics => {
  const record = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  const storageDaily = Array.isArray(record.storageDaily)
    ? record.storageDaily.map(normalizeStorageDailyEntry).filter((item): item is DashStorageDailyEntry => Boolean(item))
    : [];
  const bandwidthDaily = Array.isArray(record.bandwidthDaily)
    ? record.bandwidthDaily.map(normalizeBandwidthDailyEntry).filter((item): item is DashBandwidthDailyEntry => Boolean(item))
    : [];
  const audits = Array.isArray(record.audits)
    ? record.audits.map(normalizeAuditEntry).filter((item): item is DashAuditEntry => Boolean(item))
    : [];

  return {
    storageDaily,
    bandwidthDaily,
    storageSummary: toNumber(record.storageSummary),
    averageUsageBytes: toNumber(record.averageUsageBytes),
    bandwidthSummary: toNumber(record.bandwidthSummary),
    egressSummary: toNumber(record.egressSummary),
    ingressSummary: toNumber(record.ingressSummary),
    earliestJoinedAt: toStringSafe(record.earliestJoinedAt),
    audits,
  };
};

export const fetchDashNodes = async (): Promise<string[]> => {
  const response = await apiClient.get("/dash/nodes");
  const { data } = response;
  if (Array.isArray(data)) {
    return data.map((item) => toStringSafe(item)).filter(Boolean);
  }
  if (data && typeof data === "object" && Array.isArray((data as Record<string, unknown>).nodes)) {
    return (data as { nodes: unknown[] }).nodes.map((item) => toStringSafe(item)).filter(Boolean);
  }
  throw new Error("Unexpected dash nodes response format");
};

export const fetchDashNodeStatus = async (nodeName: string): Promise<DashNodeStatus> => {
  const response = await apiClient.get("/dash/node-info", { params: { nodeName } });
  return normalizeNodeStatus(response.data);
};

export const fetchDashNodeStatistics = async (nodeName: string): Promise<DashNodeStatistics> => {
  const response = await apiClient.get("/dash/node-satellites", { params: { nodeName } });
  return normalizeNodeStatistics(response.data);
};

export const fetchDashNodeDetails = async (nodeName: string): Promise<DashNodeDetails> => {
  const [status, statistics] = await Promise.all([
    fetchDashNodeStatus(nodeName),
    fetchDashNodeStatistics(nodeName),
  ]);

  return { status, statistics };
};
