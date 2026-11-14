import { env } from '@/config/env';
import { FixtureLogin } from '@/features/social/api/account';
import { useFixtureSession } from '@/features/social/api/session';
import { Redirect } from 'expo-router';
import { useAppStore } from '@/state/app-store';
export default function Index() {
  const user = useAppStore((s) => s.mockUser);
  const actor = useFixtureSession((s) => s.actor);
  if (env.dataSource === 'api') {
    return actor ? <Redirect href="/(main)/(tabs)/feed" /> : <FixtureLogin />;
  }
  return <Redirect href={user ? '/(main)/(tabs)' : '/(auth)/login'} />;
}
