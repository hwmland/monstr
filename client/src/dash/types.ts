export interface DashSatellite {
  id: string;
  url: string;
  disqualified?: boolean | null;
  suspended?: boolean | null;
}

export interface DashDiskSpace {
  used: number;
  available: number;
  trash: number;
  overused: number;
}

export interface DashBandwidth {
  used: number;
  available: number;
}

export interface DashNodeStatus {
  nodeID: string;
  wallet: string;
  walletFeatures?: string[];
  satellites: DashSatellite[];
  diskSpace: DashDiskSpace;
  bandwidth: DashBandwidth;
  lastPinged: string;
  version: string;
  allowedVersion: string;
  upToDate: boolean;
  startedAt: string;
  configuredPort: string;
  quicStatus: string;
  lastQuicPingedAt: string;
}

export interface DashStorageDailyEntry {
  atRestTotal: number;
  atRestTotalBytes: number;
  intervalStart: string;
}

export interface DashBandwidthDailyEgress {
  repair: number;
  audit: number;
  usage: number;
}

export interface DashBandwidthDailyIngress {
  repair: number;
  usage: number;
}

export interface DashBandwidthDailyEntry {
  egress: DashBandwidthDailyEgress;
  ingress: DashBandwidthDailyIngress;
  delete: number;
  intervalStart: string;
}

export interface DashAuditEntry {
  auditScore: number;
  suspensionScore: number;
  onlineScore: number;
  satelliteName: string;
}

export interface DashNodeStatistics {
  storageDaily: DashStorageDailyEntry[];
  bandwidthDaily: DashBandwidthDailyEntry[];
  storageSummary: number;
  averageUsageBytes: number;
  bandwidthSummary: number;
  egressSummary: number;
  ingressSummary: number;
  earliestJoinedAt: string;
  audits: DashAuditEntry[];
}

export interface DashNodeDetails {
  status: DashNodeStatus;
  statistics: DashNodeStatistics;
}
