export interface NodeInfo {
  name: string;
  path: string;
  nodeapi?: string;
  vetting?: Record<string, string | null>;
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

export interface DisqualEntry {
  node: string;
  satelliteId: string;
  period: string;
}

export interface PaystubPeriodsResponse {
  periods: Record<string, PaystubRecord[]>;
  disqualifications?: DisqualEntry[];
}

export interface TransferTotalsNode {
  sizeDlSuccNor: number;
  sizeUlSuccNor: number;
  sizeDlFailNor: number;
  sizeUlFailNor: number;
  sizeDlSuccRep: number;
  sizeUlSuccRep: number;
  sizeDlFailRep: number;
  sizeUlFailRep: number;
  countDlSuccNor: number;
  countUlSuccNor: number;
  countDlFailNor: number;
  countUlFailNor: number;
  countDlSuccRep: number;
  countUlSuccRep: number;
  countDlFailRep: number;
  countUlFailRep: number;
}

export interface TransferTotalsResponse {
  intervalSeconds: number;
  totals: Record<string, TransferTotalsNode>;
}

export interface DiskUsageChangeNode {
  capacityEnd: number;
  usefullEnd: number;
  trashEnd: number;
  usageEnd: number;
  reclaimableEnd: number;
  capacityChange: number;
  usefullChange: number;
  trashChange: number;
  usageChange: number;
  reclaimableChange: number;
}

export interface DiskUsageChangeResponse {
  currentPeriod: string;
  referencePeriod: string;
  nodes: Record<string, DiskUsageChangeNode>;
}

export interface DiskUsageUsageNode {
  capacity: number;
  usefull: number;
  usage: number;
  trash: number;
  reclaimable: number;
  at: string;
}

export interface DiskUsageUsageResponse {
  periods: Record<string, Record<string, DiskUsageUsageNode>>;
}

// IP24 monitoring
export interface IP24StatusEntry {
  valid: boolean;
  expectedInstances: number;
  instances: number | null;
}

export type IP24StatusResponse = Record<string, IP24StatusEntry>;

// Satellite bandwidth usage
export interface SatelliteUsageRecord {
  source: string;
  satelliteId: string;
  period: string;
  dlUsage: number;
  dlRepair: number;
  dlAudit: number;
  ulUsage: number;
  ulRepair: number;
  delete: number;
  diskUsage?: number;
}

export interface SatelliteUsageResponse {
  periods: Record<string, SatelliteUsageRecord[]>;
}
