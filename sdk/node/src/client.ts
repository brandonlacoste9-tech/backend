import fetch, { type Response as NodeFetchResponse } from 'node-fetch';
import { SDKError } from './errors.js';
import type { SDKConfig, TokenResponse, GenerateResponse } from './types.js';

/**
 * Timeout wrapper for fetch using AbortController.
 */
async function fetchWithTimeout(
  url: string,
  options: RequestInit & { timeout?: number }
): Promise<NodeFetchResponse> {
  const { timeout = 120_000, ...rest } = options;
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  try {
    return await fetch(url, { ...rest, signal: controller.signal });
  } finally {
    clearTimeout(id);
  }
}

export type { SDKConfig };

export class MyAIClient {
  private _token?: string;
  private _config: Required<SDKConfig>;

  constructor(cfg: SDKConfig) {
    this._config = {
      baseUrl: cfg.baseUrl.replace(/\/$/, ''),
      timeout: cfg.timeout ?? 120_000,
    };
  }

  private async _post<T = unknown>(
    endpoint: string,
    body?: object
  ): Promise<T> {
    const url = `${this._config.baseUrl}${endpoint}`;
    const res = await fetchWithTimeout(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
      timeout: this._config.timeout,
    });
    if (!res.ok) throw new SDKError(res);
    return res.json() as Promise<T>;
  }

  private async _get<T = unknown>(endpoint: string): Promise<T> {
    const url = `${this._config.baseUrl}${endpoint}`;
    const headers: Record<string, string> = {};
    if (this._token) headers['Authorization'] = `Bearer ${this._token}`;
    const res = await fetchWithTimeout(url, {
      method: 'GET',
      headers,
      timeout: this._config.timeout,
    });
    if (!res.ok) throw new SDKError(res);
    return res.json() as Promise<T>;
  }

  /** Register a new user. Stores the returned access token. */
  async register(email: string, password: string): Promise<TokenResponse> {
    const data = await this._post<TokenResponse>('/auth/register', {
      email,
      password,
    });
    this._token = data.access_token;
    return data;
  }

  /** Log in. Stores the returned access token. */
  async login(email: string, password: string): Promise<TokenResponse> {
    const data = await this._post<TokenResponse>('/auth/login', {
      email,
      password,
    });
    this._token = data.access_token;
    return data;
  }

  /**
   * Submit text for summarisation, poll until the job completes, return the summary.
   * @param text – Text to summarise
   * @param _maxLength – Hint (backend may ignore it)
   * @param pollInterval – Ms between status polls
   * @param timeout – Max ms to wait for completion
   */
  async summarise(
    text: string,
    _maxLength: number = 80,
    pollInterval: number = 1000,
    timeout: number = 120_000
  ): Promise<string> {
    if (!this._token) throw new SDKError('Not authenticated. Call login() or register() first.');

    const job = await fetchWithTimeout(
      `${this._config.baseUrl}/service/generate`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${this._token}`,
        },
        body: JSON.stringify({ prompt: text }),
        timeout: this._config.timeout,
      }
    );
    if (!job.ok) throw new SDKError(job);
    const { job_id } = (await job.json()) as { job_id: string };

    const start = Date.now();
    while (Date.now() - start < timeout) {
      const statusData = await this._get<GenerateResponse>(
        `/service/status/${job_id}`
      );
      const st = statusData.status;
      if (st === 'completed') return statusData.result ?? '';
      if (st === 'failed')
        throw new SDKError(statusData.detail ?? 'Job failed');
      await new Promise((r) => setTimeout(r, pollInterval));
    }
    throw new SDKError(`Summarise timed out after ${timeout}ms`);
  }
}
