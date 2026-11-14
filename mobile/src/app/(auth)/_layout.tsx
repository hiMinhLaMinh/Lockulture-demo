import { Redirect, Stack } from 'expo-router';
import { env } from '@/config/env';
import { useFirebaseSession, useFixtureSession } from '@/features/social/api/session';

export default function AuthLayout() {
  const fixture = useFixtureSession((s) => s.actor);
  const user = useFirebaseSession((s) => s.user);
  const actor = fixture ?? (user?.emailVerified ? user.uid : null);
  if (env.dataSource === 'api' && actor) return <Redirect href="/" />;
  return <Stack screenOptions={{ headerShown: false }} />;
}
