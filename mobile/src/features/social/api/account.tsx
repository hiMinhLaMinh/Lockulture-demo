import { router, useLocalSearchParams } from 'expo-router';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Text } from 'react-native';
import { reload, sendEmailVerification, signInWithEmailAndPassword, signOut } from 'firebase/auth';
import { AuthField } from '@/features/auth/components/auth-field';
import { authError } from '@/features/auth/firebase-errors';
import { authFromConfig } from '@/features/auth/firebase-session';
import { Action } from '@/shared/components/action';
import { Page } from '@/shared/components/page';
import { Screen } from '@/shared/components/screen';
import { Surface, commonStyles as c } from '@/shared/components/surface';
import { leaderboard, socialRequest, user } from '@/services/api/social';
import { useCaptureStore } from '@/state/capture-store';
import { Person } from '@/features/social/ui';
import { ErrorNote, QueryView } from './components';
import { useRefreshOnFocus, useSocialQuery } from './hooks';
import {
  fixtureActors,
  socialDev,
  tokenFor,
  useFirebaseSession,
  useFixtureSession,
  type FixtureActor,
} from './session';

function FixtureActorPicker({ onSignedIn }: { onSignedIn?: () => void }) {
  const client = useQueryClient();
  const [pending, setPending] = useState<FixtureActor | null>(null);
  const [error, setError] = useState<Error | null>(null);

  async function signIn(actor: FixtureActor) {
    setPending(actor);
    setError(null);
    try {
      const profile = await socialRequest(tokenFor(actor), '/me', user);
      useCaptureStore.setState({ draft: null, continuation: null });
      client.clear();
      client.setQueryData(['social', actor, '/me'], profile);
      useFixtureSession.setState({ actor });
      onSignedIn?.();
    } catch (cause) {
      setError(cause instanceof Error ? cause : new Error('Không kết nối được máy chủ.'));
    } finally {
      setPending(null);
    }
  }

  return (
    <>
      {socialDev &&
        (Object.keys(fixtureActors) as FixtureActor[]).map((actor) => (
          <Action
            key={actor}
            label={`${actor} · ${fixtureActors[actor]}`}
            loading={pending === actor}
            disabled={pending !== null}
            onPress={() => void signIn(actor)}
          />
        ))}
      <ErrorNote error={error} />
    </>
  );
}

export function FirebaseLogin() {
  const bootstrapError = useFirebaseSession((state) => state.error);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function login() {
    setPending(true);
    setError('');
    setMessage('');
    try {
      const auth = await authFromConfig();
      if (auth.currentUser) await signOut(auth);
      const credential = await signInWithEmailAndPassword(auth, email.trim(), password);
      await reload(credential.user);
      if (!credential.user.emailVerified) {
        await sendEmailVerification(credential.user);
        await signOut(auth);
        setMessage('Email chưa được xác minh. Đã gửi lại liên kết xác minh; hãy kiểm tra hộp thư.');
        return;
      }
    } catch (cause) {
      setError(authError(cause));
    } finally {
      setPending(false);
    }
  }

  return (
    <Screen
      title="Đăng nhập"
      description="Đăng nhập bằng email đã xác minh để kết nối tài khoản với Lockulture."
    >
      <AuthField
        label="Email"
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        autoComplete="email"
        keyboardType="email-address"
        textContentType="emailAddress"
      />
      <AuthField
        label="Mật khẩu"
        value={password}
        onChangeText={setPassword}
        autoCapitalize="none"
        autoComplete="current-password"
        secureTextEntry
        textContentType="password"
      />
      <ErrorNote error={error ? new Error(error) : bootstrapError} />
      {message ? <Text style={c.body}>{message}</Text> : null}
      <Action label="Đăng nhập" loading={pending} onPress={() => void login()} />
      <Action secondary label="Đăng ký" href="/(auth)/register" />
      <Action secondary label="Quên mật khẩu" href="/(auth)/forgot-password" />
      {socialDev && <FixtureActorPicker />}
    </Screen>
  );
}

export const FixtureLogin = FirebaseLogin;

export function ApiProfile() {
  const me = useSocialQuery('/me', user);
  const [switching, setSwitching] = useState(false);
  const firebaseUser = useFirebaseSession((state) => state.user);
  const queryClient = useQueryClient();
  async function logout() {
    const auth = await authFromConfig();
    await signOut(auth);
    useFirebaseSession.setState({ user: null, ready: true, error: null });
    useFixtureSession.setState({ actor: null });
    useCaptureStore.setState({ draft: null, continuation: null });
    queryClient.clear();
    router.replace('/(auth)/login');
  }
  if (switching) {
    return (
      <Page title="Đổi tài khoản thử nghiệm">
        <FixtureActorPicker
          onSignedIn={() => {
            setSwitching(false);
            router.dismissTo('/(main)/(tabs)/feed');
          }}
        />
        <Action secondary label="Hủy" onPress={() => setSwitching(false)} />
      </Page>
    );
  }
  return (
    <Page title="Hồ sơ">
      <QueryView query={me}>
        {me.data && (
          <Surface>
            <Person
              name={me.data.display_name}
              detail={`@${me.data.username} · ${me.data.xp} XP`}
            />
            {me.data.bio ? <Text style={c.body}>{me.data.bio}</Text> : null}
          </Surface>
        )}
        <Action secondary label="Bảng tin" href="/(main)/(tabs)/feed" />
        <Action secondary label="Bộ sưu tập" href="/(main)/collection" />
        <Action secondary label="Bạn bè" href="/(main)/friends" />
        <Action secondary label="Nhóm của tôi" href="/(main)/groups" />
      </QueryView>
      {firebaseUser ? (
        <Action secondary label="Đăng xuất" onPress={() => void logout()} />
      ) : (
        <Action secondary label="Đổi tài khoản thử nghiệm" onPress={() => setSwitching(true)} />
      )}
    </Page>
  );
}

export function ApiLeaderboard() {
  const ranking = useSocialQuery('/leaderboard', leaderboard);
  const me = useSocialQuery('/me', user);
  useRefreshOnFocus(ranking.refetch);
  return (
    <Page title="Bảng xếp hạng" tabs>
      <QueryView query={ranking}>
        {ranking.data && <Text style={c.title}>Hạng của bạn · {ranking.data.my_rank}</Text>}
        {ranking.data?.items.map(({ user: person, rank }) => (
          <Surface key={person.id}>
            <Person
              name={person.display_name}
              detail={`Hạng ${rank} · ${person.xp} XP`}
              onPress={() =>
                person.id === me.data?.id
                  ? router.push('/(main)/profile')
                  : router.push({ pathname: '/(main)/friends/[id]', params: { id: person.id } })
              }
            />
          </Surface>
        ))}
        {ranking.data?.items.length === 1 && <Action label="Tìm bạn" href="/(main)/friends" />}
      </QueryView>
    </Page>
  );
}

export function ApiEditProfile() {
  return (
    <Page title="Chỉnh hồ sơ">
      <Text style={c.body}>Chỉnh hồ sơ đang chờ tích hợp Firebase.</Text>
    </Page>
  );
}

export function useRouteId() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return id ?? '';
}
