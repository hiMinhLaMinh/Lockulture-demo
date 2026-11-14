import { useEffect, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import Ionicons from '@expo/vector-icons/Ionicons';
import { AssetImage } from './asset-image';
import { Celebration } from '@/features/missions/components/celebration';
import { Pressable, RefreshControl, ScrollView, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { ApiError } from '@/services/api/client';
import {
  comment,
  discovery,
  group,
  post,
  reaction,
  reactionResult,
  user,
} from '@/services/api/social';
import { Action } from '@/shared/components/action';
import { Page } from '@/shared/components/page';
import { Surface, commonStyles as c } from '@/shared/components/surface';
import { colors } from '@/shared/theme/tokens';
import { Confirm, Person, socialStyles } from '@/features/social/ui';
import { MutationFeedback, PageControls, QueryView, Selection } from './components';
import { useRefreshOnFocus, useSocialMutation, useSocialPage, useSocialQuery } from './hooks';
import { useRouteId } from './account';
import { useFirebaseSession, useFixtureSession } from './session';

type Post = z.infer<typeof post>;
const reactions = { heart: '❤️', clap: '👏', wow: '😮' };

export function PostCard({ row, detail = false }: { row: Post; detail?: boolean }) {
  return (
    <Surface>
      <Person name={row.author.display_name} detail={`@${row.author.username}`} />
      <View>
        <AssetImage id={row.asset_id} postId={row.id} />
        {!!row.caption && (
          <Text
            style={[
              c.body,
              {
                backgroundColor: colors.background,
                padding: 12,
                borderBottomLeftRadius: 12,
                borderBottomRightRadius: 12,
              },
            ]}
          >
            {row.caption}
          </Text>
        )}
      </View>
      <Text style={c.title}>{row.subject_name}</Text>
      {detail && <Text style={c.body}>{row.knowledge}</Text>}
      <Text style={c.label}>
        ❤️ {row.reaction_counts.heart} · 👏 {row.reaction_counts.clap} · 😮{' '}
        {row.reaction_counts.wow}
        {' · '}
        {row.comment_count} bình luận
      </Text>
      {!detail && (
        <Action
          secondary
          label="Xem bài viết"
          href={{ pathname: '/(main)/posts/[id]', params: { id: row.id } }}
        />
      )}
    </Surface>
  );
}

export function PostList({ query }: { query: ReturnType<typeof usePostList> }) {
  const rows = query.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <QueryView query={query}>
      {rows.map((row) => (
        <PostCard key={row.id} row={row} />
      ))}
      <PageControls query={query} empty={!rows.length ? 'Chưa có bài viết.' : undefined} />
    </QueryView>
  );
}

export function usePostList(groupId?: string) {
  return useSocialPage(groupId ? `/posts?group_id=${groupId}` : '/posts', post);
}

export function ApiFeed() {
  const query = usePostList();
  useRefreshOnFocus(query.refetch);
  return (
    <SafeAreaView
      edges={['top', 'left', 'right']}
      style={{ flex: 1, backgroundColor: colors.background }}
    >
      <ScrollView
        refreshControl={
          <RefreshControl refreshing={query.isRefetching} onRefresh={() => void query.refetch()} />
        }
        contentContainerStyle={{ padding: 22, paddingBottom: 36, gap: 20 }}
      >
        <View
          style={{
            flexDirection: 'row',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 8,
          }}
        >
          <Text accessibilityRole="header" style={[c.title, { fontSize: 27 }]}>
            Bảng tin
          </Text>
          <View style={{ flexDirection: 'row', gap: 6 }}>
            {(
              [
                ['Bảng xếp hạng', 'trophy-outline', '/(main)/leaderboard'],
                ['Bạn bè', 'person-outline', '/(main)/friends'],
                ['Nhóm của tôi', 'people-outline', '/(main)/groups'],
                ['Hồ sơ', 'person-circle-outline', '/(main)/profile'],
              ] as const
            ).map(([label, icon, href]) => (
              <Pressable
                key={label}
                accessibilityRole="button"
                accessibilityLabel={label}
                onPress={() => router.push(href)}
                style={{
                  width: 44,
                  height: 44,
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: 22,
                  backgroundColor: colors.surface,
                }}
              >
                <Ionicons name={icon} size={23} color={colors.accent} />
              </Pressable>
            ))}
          </View>
        </View>
        <Action label="Chia sẻ khám phá" href="/(main)/collection" />
        <PostList query={query} />
      </ScrollView>
    </SafeAreaView>
  );
}

export function ApiCollection() {
  const query = useSocialPage('/discoveries', discovery);
  useRefreshOnFocus(query.refetch);
  const rows = query.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <Page title="Bộ sưu tập">
      <QueryView query={query}>
        {rows.map((row) => (
          <Surface key={row.id}>
            <AssetImage id={row.asset_id} />
            <Text style={c.title}>{row.name}</Text>
            <Action
              secondary
              label="Xem khám phá"
              href={{ pathname: '/(main)/collection/[id]', params: { id: row.id } }}
            />
          </Surface>
        ))}
        <PageControls query={query} empty={!rows.length ? 'Chưa có khám phá.' : undefined} />
      </QueryView>
    </Page>
  );
}

function ComposeAction({ id }: { id: string }) {
  return (
    <Action
      label="Soạn chia sẻ"
      href={{ pathname: '/(main)/posts/compose', params: { discoveryId: id } }}
    />
  );
}

export function ApiDiscovery() {
  const id = useRouteId();
  const query = useSocialQuery(`/discoveries/${id}`, discovery);
  return (
    <Page title="Khám phá">
      <QueryView query={query}>
        {query.data && (
          <Surface>
            <AssetImage id={query.data.asset_id} />
            <Text style={c.title}>{query.data.name}</Text>
            <Text style={c.body}>{query.data.knowledge}</Text>
            <ComposeAction id={query.data.id} />
          </Surface>
        )}
        {query.data?.mode === 'mission' ? <Celebration discoveryId={query.data.id} /> : null}
      </QueryView>
    </Page>
  );
}

export function ApiCompose() {
  const { discoveryId } = useLocalSearchParams<{ discoveryId: string }>();
  const item = useSocialQuery(`/discoveries/${discoveryId}`, discovery, !!discoveryId);
  const friends = useSocialPage('/friends', user);
  const groups = useSocialPage('/groups', group);
  const ownFeed = usePostList();
  const mutation = useSocialMutation();
  const [caption, setCaption] = useState('');
  const [friendIds, setFriends] = useState<string[]>([]);
  const [groupIds, setGroups] = useState<string[]>([]);
  const prior = ownFeed.data?.pages
    .flatMap((page) => page.items)
    .find((row) => row.audience !== null && row.discovery_id === discoveryId);
  const captionLength = Array.from(caption.trim()).length;
  return (
    <Page title="Soạn chia sẻ">
      {discoveryId ? (
        <QueryView query={item}>
          {item.data && (
            <Surface>
              <AssetImage id={item.data.asset_id} />
              <Text style={c.title}>{item.data.name}</Text>
            </Surface>
          )}
        </QueryView>
      ) : (
        <Action label="Chọn khám phá" href="/(main)/collection" />
      )}
      {prior ? (
        <Action
          label="Mở bài đã đăng"
          href={{ pathname: '/(main)/posts/[id]', params: { id: prior.id } }}
        />
      ) : (
        item.data && (
          <>
            <Text style={c.label}>Chú thích · {captionLength}/500</Text>
            <TextInput
              accessibilityLabel="Chú thích"
              multiline
              value={caption}
              onChangeText={setCaption}
              style={socialStyles.input}
            />
            <Text style={c.title}>Bạn bè</Text>
            <QueryView query={friends}>
              <Selection
                rows={
                  friends.data?.pages
                    .flatMap((page) => page.items)
                    .map((person) => ({ id: person.id, label: person.display_name })) ?? []
                }
                ids={friendIds}
                change={setFriends}
                maximum={50}
              />
              <PageControls query={friends} />
            </QueryView>
            <Text style={c.title}>Nhóm</Text>
            <QueryView query={groups}>
              <Selection
                rows={
                  groups.data?.pages
                    .flatMap((page) => page.items)
                    .map((row) => ({ id: row.id, label: row.name })) ?? []
                }
                ids={groupIds}
                change={setGroups}
                maximum={10}
              />
              <PageControls query={groups} />
            </QueryView>
            <MutationFeedback mutation={mutation} />
            {mutation.error instanceof ApiError && mutation.error.status === 409 && (
              <PageControls query={ownFeed} />
            )}
            <Action
              label="Đăng bài"
              loading={mutation.pending}
              disabled={captionLength > 500 || (!friendIds.length && !groupIds.length)}
              onPress={() =>
                void mutation.send(
                  {
                    method: 'POST',
                    path: '/posts',
                    schema: post,
                    body: {
                      discovery_id: discoveryId,
                      caption: caption.trim(),
                      friend_ids: [...friendIds].sort(),
                      group_ids: [...groupIds].sort(),
                    },
                  },
                  (row) =>
                    router.replace({ pathname: '/(main)/posts/[id]', params: { id: row.id } }),
                )
              }
            />
          </>
        )
      )}
    </Page>
  );
}

function PostInteractions({ row }: { row: Post }) {
  const path = `/posts/${row.id}`;
  const comments = useSocialPage(`${path}/comments`, comment);
  const me = useSocialQuery('/me', user);
  const mutation = useSocialMutation();
  const [text, setText] = useState('');
  const length = Array.from(text.trim()).length;
  const rows = comments.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
        {reaction.options.map((value) => (
          <Action
            key={value}
            label={`${reactions[value]} ${row.reaction_counts[value]}`}
            secondary={row.my_reaction !== value}
            disabled={mutation.pending}
            onPress={() =>
              void (row.my_reaction === value
                ? mutation.send({
                    method: 'DELETE',
                    path: `${path}/reaction`,
                    schema: z.undefined(),
                  })
                : mutation.send({
                    method: 'PUT',
                    path: `${path}/reaction`,
                    body: { reaction: value },
                    schema: reactionResult,
                  }))
            }
          />
        ))}
      </View>
      <Text style={c.title}>Bình luận</Text>
      <QueryView query={comments}>
        {rows.map((entry) => (
          <Surface key={entry.id}>
            <Person name={entry.author.display_name} />
            <Text style={c.body}>{entry.text}</Text>
            {me.data?.id === entry.author.id && (
              <Action
                secondary
                label="Xóa bình luận"
                disabled={mutation.pending}
                onPress={() =>
                  void mutation.send({
                    method: 'DELETE',
                    path: `/comments/${entry.id}`,
                    schema: z.undefined(),
                  })
                }
              />
            )}
          </Surface>
        ))}
        <PageControls query={comments} empty={!rows.length ? 'Chưa có bình luận.' : undefined} />
        <Text style={c.label}>Bình luận · {length}/300</Text>
        <TextInput
          accessibilityLabel="Bình luận"
          value={text}
          onChangeText={setText}
          multiline
          editable={!mutation.pending}
          style={socialStyles.input}
        />
        <Action
          label="Gửi bình luận"
          loading={mutation.pending}
          disabled={!length || length > 300}
          onPress={() =>
            void mutation.send(
              {
                method: 'POST',
                path: `${path}/comments`,
                schema: comment,
                body: { text: text.trim() },
              },
              () => setText(''),
            )
          }
        />
      </QueryView>
      <MutationFeedback mutation={mutation} />
    </>
  );
}

function AuthorActions({ row }: { row: Post }) {
  const mutation = useSocialMutation();
  const [confirm, setConfirm] = useState(false);
  if (!row.audience) return null;
  return (
    <>
      {confirm ? (
        <Confirm
          label="Xóa bài viết"
          onCancel={() => setConfirm(false)}
          onConfirm={() =>
            void mutation.send(
              {
                method: 'DELETE',
                path: `/posts/${row.id}`,
                schema: z.undefined(),
              },
              () => router.replace('/(main)/(tabs)/feed'),
            )
          }
        >
          Xóa bài viết này?
        </Confirm>
      ) : (
        <Action secondary label="Xóa bài viết" onPress={() => setConfirm(true)} />
      )}
      <MutationFeedback mutation={mutation} />
    </>
  );
}

export function ApiPostDetail() {
  const id = useRouteId();
  const fixture = useFixtureSession((s) => s.actor);
  const firebaseUser = useFirebaseSession((s) => s.user);
  const actor = fixture ?? (firebaseUser?.emailVerified ? firebaseUser.uid : null);
  const client = useQueryClient();
  const query = useSocialQuery(`/posts/${id}`, post);
  useRefreshOnFocus(query.refetch);
  const revoked =
    query.data === null || (query.error instanceof ApiError && query.error.status === 404);
  const asset = query.data?.asset_id;
  useEffect(() => {
    if (!revoked) return;
    client.setQueryData<Post | null>(['social', actor, `/posts/${id}`], null);
    client.removeQueries({ queryKey: ['social', actor, `/posts/${id}/comments`] });
    if (asset)
      client.removeQueries({ queryKey: ['social', actor, `/assets/${asset}/url?post_id=${id}`] });
  }, [actor, asset, client, id, revoked]);
  return (
    <Page title="Bài viết">
      <Action
        secondary
        label="Về bảng tin"
        onPress={() => router.dismissTo('/(main)/(tabs)/feed')}
      />
      {revoked ? (
        <Text style={c.body}>Bài viết không còn khả dụng.</Text>
      ) : (
        <QueryView query={query}>
          {query.data && (
            <>
              <PostCard row={query.data} detail />
              <PostInteractions row={query.data} />
              <AuthorActions row={query.data} />
            </>
          )}
        </QueryView>
      )}
    </Page>
  );
}
