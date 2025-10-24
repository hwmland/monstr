export interface LogEntry {
  id: number;
  source: string;
  content: string;
  ingestedAt: string;
  processed: boolean;
}

export interface LogEntryQueryParams {
  source?: string;
  limit?: number;
}
