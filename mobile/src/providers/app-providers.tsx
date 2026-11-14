import { useEffect, useState, type PropsWithChildren } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { env } from '@/config/env';
import { useFirebaseSession } from '@/features/social/api/session';
import { onAuthStateChanged } from 'firebase/auth';

export function AppProviders({ children }: PropsWithChildren) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { retry: 1, staleTime: 30000 }, mutations: { retry: false } },
      }),
  );
  useEffect(() => {
    if (env.dataSource !== 'api') return;
    let active = true;
    let unsubscribe: (() => void) | undefined;
    void import('@/config/firebase-auth')
      .then(({ auth }) => {
        if (!active) return;
        unsubscribe = onAuthStateChanged(
          auth,
          (user) => useFirebaseSession.setState({ user, ready: true, error: null }),
          (error) => useFirebaseSession.setState({ user: null, ready: true, error }),
        );
      })
      .catch((cause: unknown) => {
        const error = cause instanceof Error ? cause : new Error('Không khởi tạo được Firebase Auth.');
        useFirebaseSession.setState({ user: null, ready: true, error });
      });
    return () => {
      active = false;
      unsubscribe?.();
    };
  }, []);
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
