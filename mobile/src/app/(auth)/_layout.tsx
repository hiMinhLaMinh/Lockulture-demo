import { Redirect, Stack } from 'expo-router';
import { env } from '@/config/env';
import { useFixtureSession } from '@/features/social/api/session';

export default function AuthLayout() {
  const actor = useFixtureSession((s) => s.actor);
  if (env.dataSource === 'api' && actor) return <Redirect href="/" />;
  return <Stack screenOptions={{ headerShown: false }} />;
}
