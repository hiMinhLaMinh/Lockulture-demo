import { z } from 'zod';
import { requestJson } from './client';

const id = z.uuid();
const time = z.iso.datetime();
const count = z.number().int().nonnegative();
export const user = z.object({
  id,
  display_name: z.string(),
  username: z.string(),
  bio: z.string(),
  xp: count,
});
export const friendRequest = z.object({
  id,
  sender: user,
  recipient: user,
  created_at: time,
  status: z.enum(['pending', 'accepted', 'rejected', 'cancelled']),
});
export const group = z.object({
  id,
  owner_id: id,
  name: z.string(),
  created_at: time,
  member_count: count,
  post_count: count,
});
export const member = z.object({
  user,
  role: z.enum(['owner', 'member']),
  joined_at: time,
});
export const reaction = z.enum(['heart', 'clap', 'wow']);
const counts = z.object({ heart: count, clap: count, wow: count });
export const reactionResult = z.object({ reaction: reaction.nullable(), counts });
export const post = z.object({
  id,
  discovery_id: id,
  asset_id: id,
  subject_name: z.string(),
  knowledge: z.string(),
  caption: z.string(),
  created_at: time,
  author: user,
  my_reaction: reaction.nullable(),
  reaction_counts: counts,
  comment_count: count,
  audience: z.object({ friend_ids: z.array(id), group_ids: z.array(id) }).nullable(),
});
export const comment = z.object({
  id,
  post_id: id,
  author: user,
  text: z.string(),
  created_at: time,
});
export const discovery = z.object({
  id,
  asset_id: id,
  owner_id: id,
  submission_id: id,
  name: z.string(),
  knowledge: z.string(),
  created_at: time,
  mode: z.enum(['free', 'mission']),
  mission_id: id.nullable(),
  subject_key: z.string(),
  era_id: z.string().nullable(),
  xp_awarded: count,
  fragment_added: z.boolean(),
  reward_reason: z.enum(['granted', 'daily_subject_limit']),
});
export const assetUrl = z.object({ url: z.url(), expires_at: time });
export const leaderboard = z.object({
  items: z.array(z.object({ user, rank: count.positive() })),
  my_rank: count.positive(),
  as_of: time,
});

export function pageSchema<T>(item: z.ZodType<T>) {
  return z.object({ items: z.array(item), next_cursor: z.string().nullable() });
}

export async function socialRequest<T>(
  token: string | undefined,
  path: string,
  schema: z.ZodType<T>,
  options?: RequestInit,
): Promise<T> {
  return schema.parse(await requestJson<unknown>(path, options, token));
}
