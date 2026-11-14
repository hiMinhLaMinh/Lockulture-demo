import { z } from 'zod';

const schema = z.object({
  dataSource: z.enum(['mock', 'api']).default('mock'),
  socialFixtures: z
    .enum(['0', '1'])
    .default('0')
    .transform((value) => value === '1'),
  apiBaseUrl: z.string().url().default('http://localhost:8080/api/v1'),
  firebaseApiKey: z.string().default(''),
  firebaseAuthDomain: z.string().default(''),
  firebaseProjectId: z.string().default(''),
  firebaseStorageBucket: z.string().default(''),
  firebaseMessagingSenderId: z.string().default(''),
  firebaseAppId: z.string().default(''),
});
// Expo replaces direct EXPO_PUBLIC references at bundle time. Never put API secrets here.
export const env = schema.parse({
  socialFixtures: process.env.EXPO_PUBLIC_SOCIAL_FIXTURES,
  dataSource: process.env.EXPO_PUBLIC_DATA_SOURCE,
  apiBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL,
  firebaseApiKey: process.env.EXPO_PUBLIC_FIREBASE_API_KEY,
  firebaseAuthDomain: process.env.EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN,
  firebaseProjectId: process.env.EXPO_PUBLIC_FIREBASE_PROJECT_ID,
  firebaseStorageBucket: process.env.EXPO_PUBLIC_FIREBASE_STORAGE_BUCKET,
  firebaseMessagingSenderId: process.env.EXPO_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  firebaseAppId: process.env.EXPO_PUBLIC_FIREBASE_APP_ID,
});

export function requireFirebaseConfig() {
  const missing = [
    ['EXPO_PUBLIC_FIREBASE_API_KEY', env.firebaseApiKey],
    ['EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN', env.firebaseAuthDomain],
    ['EXPO_PUBLIC_FIREBASE_PROJECT_ID', env.firebaseProjectId],
    ['EXPO_PUBLIC_FIREBASE_APP_ID', env.firebaseAppId],
  ]
    .filter(([, value]) => !value)
    .map(([name]) => name);
  if (missing.length) {
    throw new Error(`Missing Firebase configuration: ${missing.join(', ')}`);
  }
}
