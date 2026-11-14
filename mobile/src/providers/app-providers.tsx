import { useEffect, useState, type PropsWithChildren } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { env } from '@/config/env';
import { useFirebaseSession, useFixtureSession } from '@/features/social/api/session';
import { onAuthStateChanged } from 'firebase/auth';
import { socialRequest, user as profileSchema } from '@/services/api/social';
import { useCaptureStore } from '@/state/capture-store';

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
        let sequence = 0;
        unsubscribe = onAuthStateChanged(auth, (user) => {
          const attempt = ++sequence;
          const previous = useFirebaseSession.getState().user?.uid;
          if (previous && previous !== user?.uid) {
            client.clear();
            useCaptureStore.setState({ draft: null, continuation: null });
          }
          if (!user?.emailVerified) {
            useFirebaseSession.setState({ user: null, ready: true, error: null });
            return;
          }
          useFirebaseSession.setState({ user: null, ready: false, error: null });
          void socialRequest(undefined, '/me', profileSchema, undefined, user.uid)
            .then((profile) => {
              if (!active || attempt !== sequence) return;
              client.setQueryData(['social', user.uid, '/me'], profile);
              useFixtureSession.setState({ actor: null });
              useFirebaseSession.setState({ user, ready: true, error: null });
            })
            .catch((error: unknown) => {
              if (!active || attempt !== sequence) return;
              useFirebaseSession.setState({
                user: null,
                ready: true,
                error: error instanceof Error ? error : new Error('Không tải được hồ sơ.'),
              });
            });
        });
      })
      .catch((cause: unknown) => {
        const error =
          cause instanceof Error ? cause : new Error('Không khởi tạo được Firebase Auth.');
        useFirebaseSession.setState({ user: null, ready: true, error });
      });
    return () => {
      active = false;
      unsubscribe?.();
    };
  }, [client]);
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
