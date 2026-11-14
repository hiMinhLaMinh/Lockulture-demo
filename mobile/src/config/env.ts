import { z } from 'zod';

const schema = z.object({
  dataSource: z.enum(['mock', 'api']).default('mock'),
  socialFixtures: z
    .enum(['0', '1'])
    .default('0')
    .transform((value) => value === '1'),
  apiBaseUrl: z.string().url().default('http://localhost:8080/api/v1'),
});
// Expo replaces direct EXPO_PUBLIC references at bundle time. Never put API secrets here.
export const env = schema.parse({
  socialFixtures: process.env.EXPO_PUBLIC_SOCIAL_FIXTURES,
  dataSource: process.env.EXPO_PUBLIC_DATA_SOURCE,
  apiBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL,
});
