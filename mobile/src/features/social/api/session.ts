import { create } from 'zustand';
import type { User } from 'firebase/auth';
import { env } from '@/config/env';

export type FixtureActor = 'A' | 'B' | 'C' | 'D';
export const fixtureActors = {
  A: 'Minh',
  B: 'Minh An',
  C: 'Thảo Linh',
  D: 'Người mới',
} satisfies Record<FixtureActor, string>;

export const useFixtureSession = create<{ actor: FixtureActor | null }>(() => ({ actor: null }));
type FirebaseSession = { user: User | null; ready: boolean; error: Error | null };
export const useFirebaseSession = create<FirebaseSession>(() => ({
  user: null,
  ready: false,
  error: null,
}));
export const socialDev = env.dataSource === 'api' && env.socialFixtures;

export function tokenFor(actor: FixtureActor) {
  return `lockulture-dev-${actor}`;
}

export function currentActor() {
  const fixture = useFixtureSession.getState().actor;
  const user = useFirebaseSession.getState().user;
  return fixture ?? (user?.emailVerified ? user.uid : null);
}
