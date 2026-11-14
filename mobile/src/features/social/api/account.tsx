import { router, useLocalSearchParams } from 'expo-router';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Text } from 'react-native';
import { Action } from '@/shared/components/action';
import { Page } from '@/shared/components/page';
import { Screen } from '@/shared/components/screen';
import { Surface, commonStyles as c } from '@/shared/components/surface';
import { leaderboard, socialRequest, user } from '@/services/api/social';
import { Person } from '@/features/social/ui';
import { ErrorNote, QueryView } from './components';
import { useRefreshOnFocus, useSocialQuery } from './hooks';
import {
  fixtureActors,
  socialDev,
  tokenFor,
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

export function FixtureLogin() {
  return (
    <Screen
      title="Đăng nhập"
      description={
        socialDev
          ? 'Chọn tài khoản thử nghiệm để kết nối với máy chủ dev.'
          : 'Đăng nhập Firebase đang chờ tích hợp.'
      }
    >
      <FixtureActorPicker />
    </Screen>
  );
}

export function ApiProfile() {
  const me = useSocialQuery('/me', user);
  const [switching, setSwitching] = useState(false);
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
      <Action secondary label="Đổi tài khoản thử nghiệm" onPress={() => setSwitching(true)} />
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
