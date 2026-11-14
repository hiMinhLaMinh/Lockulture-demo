import { Platform } from 'react-native';
import { z } from 'zod';
import type { CaptureDraft, Era } from '@/domain/models';
import { currentActor } from '@/features/social/api/session';
import { requestJson } from './client';
import { newKey } from './idempotency';
import { discovery, pageSchema, socialRequest } from './social';

const era = z.object({
  id: z.string(),
  name: z.string(),
  period: z.string(),
  status: z.enum(['not_started', 'in_progress', 'decoded']),
  fragment_count: z.number(),
  fragment_goal: z.number(),
});
const submission = z.object({
  id: z.uuid(),
  evaluation_session_id: z.uuid(),
  session_status: z.enum(['open', 'awaiting_evidence', 'completed', 'closed', 'expired']),
  status: z.enum(['queued', 'running', 'succeeded', 'failed']),
  mode: z.enum(['free', 'mission']),
  verdict: z
    .enum([
      'accepted',
      'completed',
      'retake_required',
      'unidentified',
      'out_of_scope',
      'not_matched',
      'wrong_subject',
      'out_of_radius',
      'location_unverified',
    ])
    .nullable(),
  stage: z.string().optional(),
  tool_status: z.record(z.string(), z.unknown()).optional(),
  name: z.string().nullable(),
  knowledge: z.string().nullable(),
  instruction: z.string().nullable(),
  discovery: discovery.nullable(),
  error: z.object({ message: z.string(), retryable: z.boolean() }).nullable(),
});
const asset = z.object({ id: z.uuid() });

function credentials(actor: string) {
  if (actor !== currentActor()) throw new Error('Phiên đăng nhập đã thay đổi.');
  return undefined;
}

export async function listTimeline(): Promise<Era[]> {
  const actor = currentActor();
  if (!actor) throw new Error('Phiên đăng nhập đã kết thúc.');
  const timeline = await socialRequest(
    credentials(actor),
    '/timeline',
    pageSchema(era),
    undefined,
    actor,
  );
  return timeline.items.map((item) => ({
    id: item.id,
    name: item.name,
    period: item.period,
    status: item.status,
    fragmentCount: item.fragment_count,
    fragmentGoal: item.fragment_goal,
  }));
}

export function captureKeys() {
  return { upload: newKey(), portraitUpload: newKey(), submit: newKey(), retry: newKey() };
}

async function uploadPhoto(
  photo: CaptureDraft['photo'],
  actor: string,
  key: string,
  signal: AbortSignal,
) {
  const form = new FormData();
  if (Platform.OS === 'web') {
    const response = await fetch(photo.uri, { signal });
    form.append('photo', await response.blob(), 'capture.jpg');
  } else {
    const nativeFile = { uri: photo.uri, name: 'capture.jpg', type: 'image/jpeg' };
    form.append('photo', nativeFile as unknown as Blob);
  }
  return asset.parse(
    await requestJson(
      '/assets',
      {
        method: 'POST',
        headers: { 'Idempotency-Key': key },
        body: form,
        signal,
      },
      credentials(actor),
      actor,
    ),
  );
}

export async function uploadAndSubmit(
  draft: CaptureDraft,
  keys: ReturnType<typeof captureKeys>,
  signal: AbortSignal,
) {
  const actor = draft.ownerId;
  const image = await uploadPhoto(draft.photo, actor, keys.upload, signal);
  const portrait =
    draft.souvenirOptIn && draft.portraitPhoto
      ? await uploadPhoto(draft.portraitPhoto, actor, keys.portraitUpload, signal)
      : null;
  return socialRequest(
    credentials(actor),
    '/submissions',
    submission,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': keys.submit },
      body: JSON.stringify({
        asset_id: image.id,
        capture_location: draft.captureLocation ?? null,
        souvenir_opt_in: draft.souvenirOptIn ?? false,
        portrait_asset_id: portrait?.id ?? null,
        mode: draft.mode,
        mission_id: draft.mission?.id ?? null,
        mission_version: draft.mission?.version ?? null,
        evaluation_session_id: draft.serverSession?.id ?? null,
        expected_previous_submission_id: draft.serverSession?.previous ?? null,
      }),
      signal,
    },
    actor,
  );
}

export function getSubmission(id: string, actor: string, signal: AbortSignal) {
  return socialRequest(credentials(actor), `/submissions/${id}`, submission, { signal }, actor);
}

export function retrySubmission(id: string, actor: string, key: string, signal: AbortSignal) {
  return socialRequest(
    credentials(actor),
    `/submissions/${id}/retry`,
    submission,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': key },
      body: '{}',
      signal,
    },
    actor,
  );
}

export type Submission = z.infer<typeof submission>;
