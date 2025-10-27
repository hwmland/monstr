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
