import { requireFirebaseConfig } from '@/config/env';

export async function authFromConfig() {
  requireFirebaseConfig();
  const { auth } = await import('@/config/firebase-auth');
  return auth;
}
