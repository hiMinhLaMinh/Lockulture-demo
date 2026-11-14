import { env } from '@/config/env';

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly code?: string,
    public readonly retryable = false,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}
// Caller supplies token and validates the DTO against its feature schema.
export async function requestJson<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set('Accept', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (options.signal?.aborted) abort();
  options.signal?.addEventListener('abort', abort, { once: true });
  const timer = setTimeout(abort, 15000);
  try {
    const response = await fetch(
      `${env.apiBaseUrl.replace(/\/$/, '')}/${path.replace(/^\//, '')}`,
      {
        ...options,
        headers,
        signal: controller.signal,
      },
    );
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      const error = payload?.error;
      throw new ApiError(
        response.status,
        `Yêu cầu thất bại (${response.status}).`,
        typeof error?.code === 'string' ? error.code : undefined,
        error?.retryable === true,
      );
    }
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener('abort', abort);
  }
}
