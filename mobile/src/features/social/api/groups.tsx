import { useState } from 'react';
import { router } from 'expo-router';
import { Text } from 'react-native';
import { z } from 'zod';
import { group, member, post, user } from '@/services/api/social';
import { Action } from '@/shared/components/action';
import { Page } from '@/shared/components/page';
import { Surface, commonStyles as c } from '@/shared/components/surface';
import { Confirm, Person, SearchInput } from '@/features/social/ui';
import { MutationFeedback, PageControls, QueryView, Selection } from './components';
import { useRefreshOnFocus, useSocialMutation, useSocialPage, useSocialQuery } from './hooks';
import { useRouteId } from './account';
import { PostList, usePostList } from './posts';

export function ApiGroups() {
  const query = useSocialPage('/groups', group);
  useRefreshOnFocus(query.refetch);
  const rows = query.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <Page title="Nhóm của tôi" tabs>
      <Action label="Tạo nhóm" href="/(main)/groups/create" />
      <QueryView query={query}>
        {rows.map((row) => (
          <Surface key={row.id}>
            <Person
              name={row.name}
              detail={`${row.member_count} thành viên · ${row.post_count} bài viết`}
              onPress={() =>
                router.push({ pathname: '/(main)/groups/[id]', params: { id: row.id } })
              }
            />
          </Surface>
        ))}
        <PageControls
          query={query}
          empty={!rows.length ? 'Bạn chưa tham gia nhóm nào.' : undefined}
        />
      </QueryView>
    </Page>
  );
}

function FriendPicker({
  selected,
  change,
  maximum,
  exclude = [],
}: {
  selected: string[];
  change: (ids: string[]) => void;
  maximum: number;
  exclude?: string[];
}) {
  const friends = useSocialPage('/friends', user);
  const rows =
    friends.data?.pages
      .flatMap((page) => page.items)
      .filter((person) => !exclude.includes(person.id))
      .map((person) => ({ id: person.id, label: person.display_name })) ?? [];
  return (
    <QueryView query={friends}>
      <Selection rows={rows} ids={selected} change={change} maximum={maximum} />
      <PageControls
        query={friends}
        empty={!rows.length ? 'Chưa có bạn bè có thể thêm.' : undefined}
      />
    </QueryView>
  );
}

function validName(name: string) {
  const length = Array.from(name.trim()).length;
  return length >= 1 && length <= 50;
}

export function ApiCreateGroup() {
  const [name, setName] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const mutation = useSocialMutation();
  return (
    <Page title="Tạo nhóm">
      <SearchInput label="Tên nhóm" value={name} onChangeText={setName} />
      <Text style={c.title}>Thành viên · {selected.length}/19</Text>
      <FriendPicker selected={selected} change={setSelected} maximum={19} />
      <MutationFeedback mutation={mutation} />
      <Action
        label="Tạo nhóm"
        loading={mutation.pending}
        disabled={!validName(name)}
        onPress={() =>
          void mutation.send(
            {
              method: 'POST',
              path: '/groups',
              schema: group,
              body: { name: name.trim(), member_ids: [...selected].sort() },
            },
            (row) => router.replace({ pathname: '/(main)/groups/[id]', params: { id: row.id } }),
          )
        }
      />
    </Page>
  );
}

function AddMembers({
  id,
  maximum,
  existing,
}: {
  id: string;
  maximum: number;
  existing: string[];
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const mutation = useSocialMutation();
  return (
    <Surface>
      <Text style={c.title}>
        Thêm thành viên · {selected.length}/{maximum}
      </Text>
      <FriendPicker selected={selected} change={setSelected} maximum={maximum} exclude={existing} />
      <MutationFeedback mutation={mutation} />
      <Action
        label="Thêm thành viên"
        loading={mutation.pending}
        disabled={!selected.length || selected.length > maximum}
        onPress={() =>
          void mutation.send(
            {
              method: 'POST',
              path: `/groups/${id}/members`,
              schema: group,
              body: { user_ids: [...selected].sort() },
            },
            () => setSelected([]),
          )
        }
      />
    </Surface>
  );
}

function ShareToGroup({ id }: { id: string }) {
  const feed = usePostList();
  const mutation = useSocialMutation();
  const rows =
    feed.data?.pages
      .flatMap((page) => page.items)
      .filter((row) => row.audience && !row.audience.group_ids.includes(id)) ?? [];
  return (
    <Surface>
      <Text style={c.title}>Chia sẻ bài đã đăng</Text>
      <QueryView query={feed}>
        {rows.map((row) => (
          <Action
            key={row.id}
            secondary
            label={row.subject_name}
            disabled={mutation.pending}
            onPress={() =>
              void mutation.send({
                method: 'POST',
                path: `/posts/${row.id}/shares`,
                schema: post,
                body: { group_ids: [id] },
              })
            }
          />
        ))}
        <PageControls
          query={feed}
          empty={!rows.length ? 'Chưa có bài của bạn để chia sẻ vào nhóm.' : undefined}
        />
      </QueryView>
      <MutationFeedback mutation={mutation} />
    </Surface>
  );
}

function GroupContent({ row, actor }: { row: z.infer<typeof group>; actor: string }) {
  const [name, setName] = useState(row.name);
  const [editing, setEditing] = useState(false);
  const [confirm, setConfirm] = useState<string | null>(null);
  const mutation = useSocialMutation();
  const path = `/groups/${row.id}`;
  const members = useSocialPage(`${path}/members`, member);
  const feed = usePostList(row.id);
  useRefreshOnFocus(members.refetch);
  useRefreshOnFocus(feed.refetch);
  const people = members.data?.pages.flatMap((page) => page.items) ?? [];
  const owner = row.owner_id === actor;

  function removeMember(target: string) {
    void mutation.send(
      { method: 'DELETE', path: `${path}/members/${target}`, schema: z.undefined() },
      () => {
        setConfirm(null);
        if (actor === target) router.replace('/(main)/groups');
      },
    );
  }

  return (
    <>
      <Surface>
        <Text style={c.title}>{row.name}</Text>
        <Text style={c.label}>
          {row.member_count} thành viên · {row.post_count} bài viết
        </Text>
        {owner &&
          (editing ? (
            <>
              <SearchInput label="Tên nhóm" value={name} onChangeText={setName} />
              <Action
                label="Lưu tên nhóm"
                loading={mutation.pending}
                disabled={!validName(name)}
                onPress={() =>
                  void mutation.send(
                    {
                      method: 'PATCH',
                      path,
                      schema: group,
                      body: { name: name.trim() },
                    },
                    () => setEditing(false),
                  )
                }
              />
              <Action secondary label="Hủy đổi tên" onPress={() => setEditing(false)} />
            </>
          ) : (
            <Action
              secondary
              label="Đổi tên nhóm"
              onPress={() => {
                setName(row.name);
                setEditing(true);
              }}
            />
          ))}
        {confirm === 'group' ? (
          <Confirm
            label={owner ? 'Giải tán nhóm' : 'Rời nhóm'}
            onCancel={() => setConfirm(null)}
            onConfirm={() =>
              owner
                ? void mutation.send({ method: 'DELETE', path, schema: z.undefined() }, () =>
                    router.replace('/(main)/groups'),
                  )
                : removeMember(actor)
            }
          >
            {owner ? 'Giải tán nhóm này?' : 'Rời nhóm này?'}
          </Confirm>
        ) : (
          <Action
            secondary
            label={owner ? 'Giải tán nhóm' : 'Rời nhóm'}
            disabled={mutation.pending}
            onPress={() => setConfirm('group')}
          />
        )}
        <MutationFeedback mutation={mutation} />
      </Surface>
      <Text style={c.title}>Thành viên</Text>
      <QueryView query={members}>
        {people.map((entry) => (
          <Surface key={entry.user.id}>
            <Person
              name={entry.user.display_name}
              detail={entry.role === 'owner' ? 'Chủ nhóm' : 'Thành viên'}
            />
            {owner &&
              entry.role !== 'owner' &&
              (confirm === entry.user.id ? (
                <Confirm
                  label="Xóa thành viên"
                  onCancel={() => setConfirm(null)}
                  onConfirm={() => removeMember(entry.user.id)}
                >
                  Xóa thành viên này khỏi nhóm?
                </Confirm>
              ) : (
                <Action
                  secondary
                  label="Xóa thành viên"
                  disabled={mutation.pending}
                  onPress={() => setConfirm(entry.user.id)}
                />
              ))}
          </Surface>
        ))}
        <PageControls query={members} />
        {owner && row.member_count < 20 && (
          <AddMembers
            id={row.id}
            maximum={20 - row.member_count}
            existing={people.map((entry) => entry.user.id)}
          />
        )}
      </QueryView>
      <Text style={c.title}>Bảng tin nhóm</Text>
      <PostList query={feed} />
      <ShareToGroup id={row.id} />
    </>
  );
}

export function ApiGroupDetail() {
  const id = useRouteId();
  const query = useSocialQuery(`/groups/${id}`, group);
  const me = useSocialQuery('/me', user);
  useRefreshOnFocus(query.refetch);
  return (
    <Page title="Nhóm">
      <QueryView query={query}>
        <QueryView query={me}>
          {query.data && me.data && <GroupContent key={id} row={query.data} actor={me.data.id} />}
        </QueryView>
      </QueryView>
    </Page>
  );
}
