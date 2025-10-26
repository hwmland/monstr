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
