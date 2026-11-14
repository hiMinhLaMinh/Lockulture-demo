import { useState } from 'react';
import { router } from 'expo-router';
import { Text, View } from 'react-native';
import { z } from 'zod';
import { friendRequest, user } from '@/services/api/social';
import { Action } from '@/shared/components/action';
import { Page } from '@/shared/components/page';
import { Surface, commonStyles as c } from '@/shared/components/surface';
import { Confirm, Person, SearchInput } from '@/features/social/ui';
import { MutationFeedback, PageControls, QueryView } from './components';
import { useRefreshOnFocus, useSocialMutation, useSocialPage, useSocialQuery } from './hooks';
import { useRouteId } from './account';

const tabs = ['Bạn bè', 'Lời mời', 'Tìm bạn'] as const;
type FriendAction = 'accept' | 'reject' | 'cancel';

function useFriendActions() {
  const mutation = useSocialMutation();
  return {
    ...mutation,
    request: (id: string) =>
      mutation.send({
        path: '/friend-requests',
        method: 'POST',
        body: { target_user_id: id },
        schema: friendRequest,
      }),
    respond: (id: string, action: FriendAction) =>
      mutation.send({
        path: `/friend-requests/${id}`,
        method: 'PATCH',
        body: { action },
        schema: friendRequest,
      }),
    remove: (id: string, onSuccess: () => void) =>
      mutation.send(
        {
          path: `/friends/${id}`,
          method: 'DELETE',
          schema: z.undefined(),
        },
        onSuccess,
      ),
  };
}

function FriendList() {
  const friends = useSocialPage('/friends', user);
  useRefreshOnFocus(friends.refetch);
  const rows = friends.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <QueryView query={friends}>
      {rows.map((row) => (
        <ProfileRow key={row.id} person={row} />
      ))}
      <PageControls query={friends} empty={!rows.length ? 'Chưa có bạn bè.' : undefined} />
    </QueryView>
  );
}

function ProfileRow({ person }: { person: z.infer<typeof user> }) {
  return (
    <Surface>
      <Person
        name={person.display_name}
        detail={`@${person.username}`}
        onPress={() => router.push({ pathname: '/(main)/friends/[id]', params: { id: person.id } })}
      />
    </Surface>
  );
}

function Requests({ direction }: { direction: 'incoming' | 'outgoing' }) {
  const requests = useSocialPage(`/friend-requests?direction=${direction}`, friendRequest);
  const actions = useFriendActions();
  useRefreshOnFocus(requests.refetch);
  const rows =
    requests.data?.pages.flatMap((page) => page.items).filter((row) => row.status === 'pending') ??
    [];
  return (
    <QueryView query={requests}>
      <Text style={c.title}>{direction === 'incoming' ? 'Lời mời đến' : 'Lời mời đã gửi'}</Text>
      {rows.map((row) => (
        <Surface key={row.id}>
          <ProfileRow person={direction === 'incoming' ? row.sender : row.recipient} />
          {direction === 'incoming' ? (
            <>
              <Action
                label="Chấp nhận"
                disabled={actions.pending}
                onPress={() => void actions.respond(row.id, 'accept')}
              />
              <Action
                secondary
                label="Từ chối"
                disabled={actions.pending}
                onPress={() => void actions.respond(row.id, 'reject')}
              />
            </>
          ) : (
            <Action
              secondary
              label="Hủy lời mời"
              disabled={actions.pending}
              onPress={() => void actions.respond(row.id, 'cancel')}
            />
          )}
        </Surface>
      ))}
      <MutationFeedback mutation={actions} />
      <PageControls
        query={requests}
        empty={!rows.length ? 'Không có lời mời đang chờ.' : undefined}
      />
    </QueryView>
  );
}

function SearchFriends() {
  const [text, setText] = useState('');
  const term = text.trim();
  const valid = Array.from(term).length >= 2 && Array.from(term).length <= 50;
  const results = useSocialPage(`/users?query=${encodeURIComponent(term)}`, user, valid);
  const rows = results.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <>
      <SearchInput label="Tìm theo tên hoặc username" value={text} onChangeText={setText} />
      {valid && (
        <QueryView query={results}>
          {rows.map((row) => (
            <ProfileRow key={row.id} person={row} />
          ))}
          <PageControls
            query={results}
            empty={!rows.length ? 'Không tìm thấy người dùng.' : undefined}
          />
        </QueryView>
      )}
    </>
  );
}

export function ApiFriends() {
  const [tab, setTab] = useState<(typeof tabs)[number]>('Bạn bè');
  return (
    <Page title="Bạn bè" tabs>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
        {tabs.map((label) => (
          <Action
            key={label}
            label={label}
            secondary={tab !== label}
            onPress={() => setTab(label)}
          />
        ))}
      </View>
      {tab === 'Bạn bè' && <FriendList />}
      {tab === 'Lời mời' && (
        <>
          <Requests direction="incoming" />
          <Requests direction="outgoing" />
        </>
      )}
      {tab === 'Tìm bạn' && <SearchFriends />}
    </Page>
  );
}

function Relationship({ id }: { id: string }) {
  const friends = useSocialPage('/friends', user);
  const incoming = useSocialPage('/friend-requests?direction=incoming', friendRequest);
  const outgoing = useSocialPage('/friend-requests?direction=outgoing', friendRequest);
  const actions = useFriendActions();
  const [confirm, setConfirm] = useState(false);
  const accepted = friends.data?.pages.some((page) =>
    page.items.some((person) => person.id === id),
  );
  const received = incoming.data?.pages
    .flatMap((page) => page.items)
    .find((row) => row.sender.id === id && row.status === 'pending');
  const sent = outgoing.data?.pages
    .flatMap((page) => page.items)
    .find((row) => row.recipient.id === id && row.status === 'pending');

  return (
    <QueryView query={friends}>
      <QueryView query={incoming}>
        <QueryView query={outgoing}>
          {accepted ? (
            confirm ? (
              <Confirm
                label="Xóa bạn"
                onCancel={() => setConfirm(false)}
                onConfirm={() => void actions.remove(id, () => setConfirm(false))}
              >
                Xóa người này khỏi danh sách bạn bè?
              </Confirm>
            ) : (
              <Action
                secondary
                label="Xóa bạn"
                disabled={actions.pending}
                onPress={() => setConfirm(true)}
              />
            )
          ) : received ? (
            <>
              <Action
                label="Chấp nhận"
                disabled={actions.pending}
                onPress={() => void actions.respond(received.id, 'accept')}
              />
              <Action
                secondary
                label="Từ chối"
                disabled={actions.pending}
                onPress={() => void actions.respond(received.id, 'reject')}
              />
            </>
          ) : sent ? (
            <Action
              secondary
              label="Hủy lời mời"
              disabled={actions.pending}
              onPress={() => void actions.respond(sent.id, 'cancel')}
            />
          ) : friends.hasNextPage || incoming.hasNextPage || outgoing.hasNextPage ? (
            <>
              <Text style={c.label}>Tải thêm để kiểm tra quan hệ.</Text>
              <PageControls query={friends} />
              <PageControls query={incoming} />
              <PageControls query={outgoing} />
            </>
          ) : (
            <Action
              label="Gửi lời mời"
              loading={actions.pending}
              onPress={() => void actions.request(id)}
            />
          )}
          <MutationFeedback mutation={actions} />
        </QueryView>
      </QueryView>
    </QueryView>
  );
}

export function ApiFriendProfile() {
  const id = useRouteId();
  const profile = useSocialQuery(`/users/${id}`, user);
  const me = useSocialQuery('/me', user);
  return (
    <Page title="Hồ sơ">
      <QueryView query={profile}>
        {profile.data && (
          <Surface>
            <Person
              name={profile.data.display_name}
              detail={`@${profile.data.username} · ${profile.data.xp} XP`}
            />
            {profile.data.bio ? <Text style={c.body}>{profile.data.bio}</Text> : null}
          </Surface>
        )}
      </QueryView>
      {profile.data && me.data && me.data.id !== id && <Relationship id={id} />}
    </Page>
  );
}
