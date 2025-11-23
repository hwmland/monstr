export interface NodeInfo {
  name: string;
  path: string;
}

export interface SatelliteReputation {
  satelliteId: string;
  satelliteName: string;
  timestamp: string;
  auditsTotal: number;
  auditsSuccess: number;
  scoreAudit: number;
  scoreOnline: number;
  scoreSuspension: number;
}

export interface NodeReputation {
  node: string;
  satellites: SatelliteReputation[];
}

export interface TransferActualMetrics {
  operationsTotal: number;
  operationsSuccess: number;
  dataBytes: number;
  rate: number;
}

export interface TransferActualCategoryMetrics {
  normal: TransferActualMetrics;
  repair: TransferActualMetrics;
}

export interface TransferActualSatelliteMetrics {
  satelliteId: string;
  satelliteName: string;
  download: TransferActualCategoryMetrics;
  upload: TransferActualCategoryMetrics;
}

export interface TransferActualData {
  startTime: string;
  endTime: string;
  download: TransferActualCategoryMetrics;
  upload: TransferActualCategoryMetrics;
  satellites: TransferActualSatelliteMetrics[];
}

export interface TransferActualAggregated {
  startTime: string;
  endTime: string;
  download: TransferActualMetrics;
  upload: TransferActualMetrics;
}

export interface PayoutNode {
  joinedAt?: string | null;
  lastEstimatedPayoutAt?: string | null;
  estimatedPayout?: number | null;
  heldBackPayout?: number | null;
  totalHeldPayout?: number | null;
  downloadPayout?: number | null;
  repairPayout?: number | null;
  diskPayout?: number | null;
}

export interface PaystubRecord {
  source: string;
  satelliteId: string;
  period: string;
  created: string;
  usageAtRest: number;
  usageGet: number;
  usagePut: number;
  usageGetRepair: number;
  usagePutRepair: number;
  usageGetAudit: number;
  compAtRest: number;
  compGet: number;
  compPut: number;
  compGetRepair: number;
  compPutRepair: number;
  compGetAudit: number;
  surgePercent: number;
  held: number;
  owed: number;
  disposed: number;
  paid: number;
  distributed: number;
}

export interface PaystubPeriodsResponse {
  periods: Record<string, PaystubRecord[]>;
}
