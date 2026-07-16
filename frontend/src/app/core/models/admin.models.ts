// Mirrors ragchatbot.api.routes.admin (backend) — keep in sync if the API changes.

export type IngestJobStatus = 'pending' | 'running' | 'succeeded' | 'failed';

export interface IngestRequest {
  tables?: string[] | null;
}

export interface IngestStartResponse {
  job_id: string;
  status: IngestJobStatus;
}

export interface IngestJobResponse {
  job_id: string;
  status: IngestJobStatus;
  tables: string[];
  stats: Record<string, number> | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface ResetRequest {
  tables?: string[] | null;
  confirm: boolean;
}

export interface ResetResponse {
  deleted_chunks: number;
  reset_tables: string[] | null;
}

export interface SourceDbStatusResponse {
  connected: boolean;
  engine: string;
  host: string;
  port: number;
  database: string;
  source_schema: string | null;
  error: string | null;
}
