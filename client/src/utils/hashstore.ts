import type { HashstoreCompactionBucket } from "../types";

export const formatBucketDate = (bucketStart: string, bucketSeconds: number): string => {
  try {
    const date = new Date(bucketStart);
    if (Number.isNaN(date.getTime())) return bucketStart;
    if (bucketSeconds >= 86400 * 3) {
      return date.toLocaleDateString([], { month: "short", day: "numeric" });
    }
    return date.toLocaleDateString([], { month: "short", day: "numeric" });
  } catch {
    return bucketStart;
  }
};

export const formatAxisDate = (value: string): string => {
  try {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleDateString([], { month: "short", day: "numeric" });
  } catch {
    return value;
  }
};

export const formatDuration = (ms: number): string => {
  if (ms < 1000) return `${ms}ms`;
  const sec = ms / 1000;
  if (sec < 60) return `${sec.toFixed(1)}s`;
  const min = sec / 60;
  return `${min.toFixed(1)}m`;
};

/** Compute max absolute value of a field across all buckets (for axis scaling) */
export const maxFieldValue = (buckets: HashstoreCompactionBucket[], key: keyof HashstoreCompactionBucket): number => {
  let max = 0;
  for (const b of buckets) {
    const v = Math.abs(Number(b[key]) || 0);
    if (v > max) max = v;
  }
  return max;
};

export const HASHSTORE_COLORS = {
  set: "#4fc3f7",
  trash: "#ff8a65",
  ttl: "#aed581",
  reclaimable: "#90caf9",
  rewritten: "#1565c0",
  trashed: "#ef5350",
  expired: "#ffa726",
  restored: "#66bb6a",
  reclaimed: "#42a5f5",
  load: "#42a5f5",
  duration: "#66bb6a",
  durationMax: "#CC3333",
  durationMedian: "#a5d6a7",
  durationTotal: "#2e7d32",
  passes: "#26a69a",
  freeRequired: "#ffca28",
} as const;
