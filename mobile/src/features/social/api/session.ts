import { create } from 'zustand';
import { env } from '@/config/env';

export type FixtureActor = 'A' | 'B' | 'C' | 'D';
export const fixtureActors = {
  A: 'Minh',
  B: 'Minh An',
  C: 'Thảo Linh',
  D: 'Người mới',
} satisfies Record<FixtureActor, string>;

export const useFixtureSession = create<{ actor: FixtureActor | null }>(() => ({ actor: null }));
export const socialDev = env.dataSource === 'api' && env.socialFixtures;

export function tokenFor(actor: FixtureActor) {
  return `lockulture-dev-${actor}`;
}
