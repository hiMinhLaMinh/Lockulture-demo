import { Redirect, Stack } from 'expo-router';
import { env } from '@/config/env';
import { useFirebaseSession, useFixtureSession } from '@/features/social/api/session';
import { ActivityIndicator, View } from 'react-native';
import { colors } from '@/shared/theme/tokens';

export default function MainLayout() {
  const fixture = useFixtureSession((s) => s.actor);
  const user = useFirebaseSession((s) => s.user);
  const ready = useFirebaseSession((s) => s.ready);
  const actor = fixture ?? (user?.emailVerified ? user.uid : null);
  if (env.dataSource === 'api' && !ready && !actor) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.background, justifyContent: 'center' }}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }
  if (env.dataSource === 'api' && !actor) return <Redirect href="/(auth)/login" />;
  return <Stack screenOptions={{ headerShown: false }} />;
}
