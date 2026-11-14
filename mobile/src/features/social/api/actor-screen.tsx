import type { ComponentType } from 'react';
import { useFixtureSession } from './session';

export function forFixtureActor(Screen: ComponentType) {
  function FixtureActorScreen() {
    const actor = useFixtureSession((s) => s.actor);
    return actor ? <Screen key={actor} /> : null;
  }
  return FixtureActorScreen;
}
