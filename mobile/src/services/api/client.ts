import { env } from '@/config/env';

async function firebaseSession(expectedUid?: string | null) {
  if (env.dataSource !== 'api') return undefined;
  const { auth } = await import('@/config/firebase-auth');
  const user = auth.currentUser;
  if (expectedUid !== undefined && user?.uid !== expectedUid)
    throw new Error('Phiên đăng nhập đã thay đổi.');
  if (!user || !user.emailVerified) return undefined;
  return { token: await user.getIdToken(), uid: user.uid };
}

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
  expectedUid?: string | null,
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set('Accept', 'application/json');
  const firebase = token ? undefined : await firebaseSession(expectedUid);
  const activeToken = token ?? firebase?.token;
  if (activeToken) headers.set('Authorization', `Bearer ${activeToken}`);
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (options.signal?.aborted) abort();
  options.signal?.addEventListener('abort', abort, { once: true });
  const timer = setTimeout(abort, 15000);
  try {
    let response = await fetch(`${env.apiBaseUrl.replace(/\/$/, '')}/${path.replace(/^\//, '')}`, {
      ...options,
      headers,
      signal: controller.signal,
    });
    if (response.status === 401 && firebase) {
      const { auth } = await import('@/config/firebase-auth');
      const user = auth.currentUser;
      if (user?.emailVerified && user.uid === firebase.uid) {
        headers.set('Authorization', `Bearer ${await user.getIdToken(true)}`);
        response = await fetch(`${env.apiBaseUrl.replace(/\/$/, '')}/${path.replace(/^\//, '')}`, {
          ...options,
          headers,
          signal: controller.signal,
        });
      }
    }
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
