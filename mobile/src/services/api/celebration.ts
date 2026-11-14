import { z } from 'zod';
export const celebration = z.object({
  discovery_id: z.uuid(),
  badge: z.object({
    id: z.uuid(),
    title: z.string(),
    motif: z.string(),
    era_id: z.string(),
    earned_at: z.iso.datetime(),
  }),
  heritage: z.object({
    summary: z.string(),
    fun_facts: z.array(z.string()),
    era_id: z.string(),
    sources: z.array(z.object({ title: z.string(), url: z.url() })),
  }),
  souvenir: z.object({
    job_id: z.uuid().nullable(),
    status: z.enum(['not_requested', 'queued', 'running', 'succeeded', 'failed']),
    asset_id: z.uuid().nullable(),
    error: z.object({ message: z.string() }).nullable(),
  }),
});
