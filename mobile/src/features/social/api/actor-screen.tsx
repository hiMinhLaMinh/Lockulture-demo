import type { ComponentType } from 'react';
import { useFirebaseSession, useFixtureSession } from './session';

export function forFixtureActor(Screen: ComponentType) {
  function FixtureActorScreen() {
    const fixture = useFixtureSession((s) => s.actor);
    const user = useFirebaseSession((s) => s.user);
    const actor = fixture ?? (user?.emailVerified ? user.uid : null);
    return actor ? <Screen key={actor} /> : null;
  }
  return FixtureActorScreen;
}
