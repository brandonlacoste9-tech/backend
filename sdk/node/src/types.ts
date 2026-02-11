/**
 * Request/response shapes for the Summarise-as-a-Service API.
 */

export interface SDKConfig {
  baseUrl: string;
  timeout?: number; // ms, default 120_000
}

export interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  token_type?: string;
}

export interface GenerateResponse {
  job_id: string;
  status: string;
  result?: string | null;
  detail?: string | null;
}
