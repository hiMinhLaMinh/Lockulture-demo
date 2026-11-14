import { Stack } from 'expo-router';
import { env } from '@/config/env';
import { FixtureLogin } from '@/features/social/api/account';
import { useFixtureSession } from '@/features/social/api/session';

export default function MainLayout() {
  const actor = useFixtureSession((s) => s.actor);
  if (env.dataSource === 'api' && !actor) return <FixtureLogin />;
  return <Stack screenOptions={{ headerShown: false }} />;
}
