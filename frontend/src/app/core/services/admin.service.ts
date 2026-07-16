import { HttpClient } from '@angular/common/http';
import { Inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { API_BASE_URL } from '../config/api-config';
import {
  IngestJobResponse,
  IngestRequest,
  IngestStartResponse,
  ResetRequest,
  ResetResponse,
  SourceDbStatusResponse,
} from '../models/admin.models';

@Injectable({ providedIn: 'root' })
export class AdminService {
  constructor(
    private readonly http: HttpClient,
    @Inject(API_BASE_URL) private readonly baseUrl: string,
  ) {}

  sourceDbStatus(): Observable<SourceDbStatusResponse> {
    return this.http.get<SourceDbStatusResponse>(`${this.baseUrl}/admin/source-db/status`);
  }

  startIngestion(request: IngestRequest): Observable<IngestStartResponse> {
    return this.http.post<IngestStartResponse>(`${this.baseUrl}/admin/ingest`, request);
  }

  getIngestionJob(jobId: string): Observable<IngestJobResponse> {
    return this.http.get<IngestJobResponse>(`${this.baseUrl}/admin/ingest/${jobId}`);
  }

  resetVectorStore(request: ResetRequest): Observable<ResetResponse> {
    return this.http.post<ResetResponse>(`${this.baseUrl}/admin/vector-store/reset`, request);
  }
}
