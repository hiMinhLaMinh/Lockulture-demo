import { env } from '@/config/env';
import { useFirebaseSession, useFixtureSession } from '@/features/social/api/session';
import { Redirect } from 'expo-router';
import { useAppStore } from '@/state/app-store';
import { ActivityIndicator, View } from 'react-native';
import { colors } from '@/shared/theme/tokens';
export default function Index() {
  const user = useAppStore((s) => s.mockUser);
  const fixture = useFixtureSession((s) => s.actor);
  const firebaseUser = useFirebaseSession((s) => s.user);
  const ready = useFirebaseSession((s) => s.ready);
  const actor = fixture ?? (firebaseUser?.emailVerified ? firebaseUser.uid : null);
  if (env.dataSource === 'api') {
    if (!ready && !actor) {
      return (
        <View style={{ flex: 1, backgroundColor: colors.background, justifyContent: 'center' }}>
          <ActivityIndicator color={colors.accent} />
        </View>
      );
    }
    return actor ? <Redirect href="/(main)/(tabs)/feed" /> : <Redirect href="/(auth)/login" />;
  }
  return <Redirect href={user ? '/(main)/(tabs)' : '/(auth)/login'} />;
}
