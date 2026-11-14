import { z } from 'zod';
import type { Mission, MissionSearchInput, MissionSearchStage } from '@/domain/models';
import { requestJson } from './client';
import { newKey } from './idempotency';
import { currentActor } from '@/features/social/api/session';

const missionDto = z.object({
  id: z.uuid(),
  version: z.number().int().positive(),
  era_id: z.string(),
  era_name: z.string(),
  place_id: z.string(),
  place_name: z.string(),
  address: z.string(),
  location: z.object({ latitude: z.number(), longitude: z.number() }),
  clue: z.string(),
  hints: z.array(z.string()),
  photo_requirements: z.array(z.string()),
  distance_meters: z.number(),
  xp: z.number(),
  revealed_hints: z.number(),
  answer_revealed: z.boolean(),
  status: z.enum(['active', 'replaced', 'completed']),
  arrival_radius_m: z.number().int().positive(),
});
const jobDto = z.object({
  id: z.uuid(),
  status: z.enum(['queued', 'running', 'succeeded', 'no_result', 'failed']),
  stage: z.enum([
    'queued',
    'finding',
    'reviewing',
    'preparing',
    'evaluating',
    'persisting',
    'done',
  ]),
  resource_id: z.uuid().nullable(),
  retry_after_seconds: z.number().nonnegative(),
  error: z.object({ message: z.string() }).nullable(),
});
function mapMission(m: z.infer<typeof missionDto>): Mission {
  return {
    id: m.id,
    version: m.version,
    eraId: m.era_id,
    eraName: m.era_name,
    placeId: m.place_id,
    placeName: m.place_name,
    address: m.address,
    location: m.location,
    clue: m.clue,
    hints: m.hints,
    photoRequirements: m.photo_requirements,
    distanceMeters: m.distance_meters,
    xp: m.xp,
    revealedHints: m.revealed_hints,
    answerRevealed: m.answer_revealed,
    status: m.status,
    arrivalRadiusM: m.arrival_radius_m,
  };
}
export async function getMission(id: string, signal?: AbortSignal) {
  return mapMission(
    missionDto.parse(await requestJson(`/missions/${id}`, { signal }, undefined, currentActor())),
  );
}
export async function getActiveMission(signal?: AbortSignal) {
  const result = missionDto
    .nullable()
    .parse(await requestJson('/missions/active', { signal }, undefined, currentActor()));
  return result ? mapMission(result) : null;
}
export async function revealMission(m: Mission, answer: boolean, key: string) {
  return mapMission(
    missionDto.parse(
      await requestJson(
        `/missions/${m.id}/${answer ? 'answer' : 'hints'}`,
        {
          method: answer ? 'PUT' : 'POST',
          headers: { 'Content-Type': 'application/json', 'Idempotency-Key': key },
          body: JSON.stringify(answer ? {} : { expected_revealed_hints: m.revealedHints }),
        },
        undefined,
        currentActor(),
      ),
    ),
  );
}
// Retain the exact request and key after ambiguous network failures, including across screen remounts.
let intent: { actor: string; body: string; key: string; jobId?: string } | undefined;
export async function searchMissions(
  input: MissionSearchInput,
  signal: AbortSignal,
  onStage: (stage: MissionSearchStage) => void,
) {
  const actor = currentActor();
  if (!actor) throw new Error('Cần phiên đăng nhập đã xác minh.');
  const body = JSON.stringify({
    location: input.location,
    location_source: input.locationSource,
    radius_meters: input.radiusMeters,
    era_id: input.eraId ?? null,
    exclude_place_id: input.excludePlaceId ?? null,
    expected_active_mission_id: input.expectedActiveMissionId ?? null,
  });
  if (!intent || intent.actor !== actor || intent.body !== body)
    intent = { actor, body, key: newKey() };
  const attempt = intent;
  let job = jobDto.parse(
    await requestJson(
      attempt.jobId ? `/mission-searches/${attempt.jobId}` : '/mission-searches',
      attempt.jobId
        ? { signal }
        : {
            method: 'POST',
            signal,
            headers: { 'Content-Type': 'application/json', 'Idempotency-Key': attempt.key },
            body,
          },
      undefined,
      actor,
    ),
  );
  attempt.jobId = job.id;
  while (true) {
    onStage(job.stage);
    if (job.status === 'no_result') {
      intent = undefined;
      return { status: 'no_suitable_place' as const };
    }
    if (job.status === 'failed') {
      intent = undefined;
      throw new Error(job.error?.message ?? 'Tìm nhiệm vụ thất bại.');
    }
    if (job.status === 'succeeded') {
      if (!job.resource_id) throw new Error('Server chưa trả nhiệm vụ.');
      const mission = await getMission(job.resource_id, signal);
      intent = undefined;
      return { status: 'ready' as const, mission };
    }
    await new Promise<void>((resolve, reject) => {
      const abort = () => {
        clearTimeout(timer);
        reject(new Error('Đã dừng tìm.'));
      };
      const timer = setTimeout(
        () => {
          signal.removeEventListener('abort', abort);
          resolve();
        },
        Math.max(1000, job.retry_after_seconds * 1000),
      );
      signal.addEventListener('abort', abort, { once: true });
      if (signal.aborted) abort();
    });
    job = jobDto.parse(
      await requestJson(`/mission-searches/${job.id}`, { signal }, undefined, actor),
    );
  }
}
