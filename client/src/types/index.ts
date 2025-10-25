export interface LogEntry {
  id: number;
  source: string;
  timestamp: string;
  level: string;
  area: string;
  action: string;
  details: Record<string, unknown>;
}

export interface LogEntryQueryParams {
  source?: string;
  level?: string;
  area?: string;
  action?: string;
  limit?: number;
}
