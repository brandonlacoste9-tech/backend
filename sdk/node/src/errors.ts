/**
 * Custom error for non-2xx responses or SDK failures.
 * Accepts a string message or any response-like object with .status.
 */
export class SDKError extends Error {
  public resp?: { status: number };

  constructor(messageOrResp: string | { status: number }) {
    if (typeof messageOrResp !== 'string' && messageOrResp?.status != null) {
      super(`HTTP ${messageOrResp.status}`);
      this.resp = messageOrResp;
    } else {
      super(typeof messageOrResp === 'string' ? messageOrResp : 'Unknown error');
    }
    this.name = 'SDKError';
    Object.setPrototypeOf(this, SDKError.prototype);
  }
}
