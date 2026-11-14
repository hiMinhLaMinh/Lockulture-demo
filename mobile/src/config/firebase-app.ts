import { getApp, getApps, initializeApp } from 'firebase/app';
import { env, requireFirebaseConfig } from './env';

requireFirebaseConfig();

export const firebaseApp =
  getApps().length > 0
    ? getApp()
    : initializeApp({
        apiKey: env.firebaseApiKey,
        authDomain: env.firebaseAuthDomain,
        projectId: env.firebaseProjectId,
        storageBucket: env.firebaseStorageBucket || undefined,
        messagingSenderId: env.firebaseMessagingSenderId || undefined,
        appId: env.firebaseAppId,
      });
