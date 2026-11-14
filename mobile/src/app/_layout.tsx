import { env } from '@/config/env';
import { useSocialStore } from '@/state/social-store';
import { useCaptureStore } from '@/state/capture-store';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { ActivityIndicator, View } from 'react-native';
import { AppProviders } from '@/providers/app-providers';
import { useAppStore } from '@/state/app-store';
import { colors } from '@/shared/theme/tokens';

const screenOptions = { headerShown: false, contentStyle: { backgroundColor: colors.background } };

function RootNavigator() {
  const socialHydrated = useSocialStore((s) => s.hydrated);
  const capturesHydrated = useCaptureStore((s) => s.hydrated);
  const hydrated = useAppStore((s) => s.hydrated);
  const user = useAppStore((s) => s.mockUser);
  if (env.dataSource === 'api') {
    return <Stack screenOptions={screenOptions} />;
  }
  if (!hydrated || !capturesHydrated || !socialHydrated)
    return (
      <View style={{ flex: 1, backgroundColor: colors.background, justifyContent: 'center' }}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  return (
    <Stack screenOptions={screenOptions}>
      <Stack.Screen name="index" />
      <Stack.Protected guard={!user}>
        <Stack.Screen name="(auth)" />
      </Stack.Protected>
      <Stack.Protected guard={!!user}>
        <Stack.Screen name="(main)" />
      </Stack.Protected>
      <Stack.Screen name="+not-found" />
    </Stack>
  );
}
export default function RootLayout() {
  return (
    <AppProviders>
      <StatusBar style="light" />
      <RootNavigator />
    </AppProviders>
  );
}
