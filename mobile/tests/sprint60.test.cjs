/* global __dirname */
// Isolated test doubles only: never imported by the Expo app or connected to providers.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const { z } = require('zod');
function load(file, deps, globals = {}) {
  const source = fs.readFileSync(path.join(__dirname, '..', file), 'utf8');
  const js = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const module = { exports: {} };
  new Function('require', 'module', 'exports', ...Object.keys(globals), js)(
    (name) => {
      if (name === 'zod') return { z };
      if (!(name in deps)) throw new Error(`Unexpected dependency ${name}`);
      return deps[name];
    },
    module,
    module.exports,
    ...Object.values(globals),
  );
  return module.exports;
}
const uuid = '10000000-0000-4000-8000-000000000001';
const session = {
  currentActor: () => 'test-owner',
  useFixtureSession: { getState: () => ({ actor: null }) },
};
function missions(requestJson) {
  let n = 0;
  return load('src/services/api/missions.ts', {
    './client': { requestJson },
    './idempotency': { newKey: () => `key-${++n}` },
    '@/features/social/api/session': session,
  });
}
const input = {
  location: { latitude: 0, longitude: 0 },
  locationSource: 'manual',
  radiusMeters: 1000,
};
test('search timeout retry preserves exact body and idempotency key, never falls back', async () => {
  const calls = [];
  const api = missions(async (route, options) => {
    calls.push({ route, ...options });
    throw new Error('offline');
  });
  for (let i = 0; i < 2; i++)
    await assert.rejects(
      api.searchMissions(input, new AbortController().signal, () => {}),
      /offline/,
    );
  assert.equal(calls.length, 2);
  assert.equal(calls[0].body, calls[1].body);
  assert.equal(calls[0].headers['Idempotency-Key'], calls[1].headers['Idempotency-Key']);
  assert.equal(JSON.parse(calls[0].body).location_source, 'manual');
});
test('known search job resumes with GET after interruption, no_result stays empty', async () => {
  const calls = [];
  const api = missions(async (route, options) => {
    calls.push({ route, ...options });
    return {
      id: uuid,
      status: calls.length === 1 ? 'queued' : 'no_result',
      stage: calls.length === 1 ? 'queued' : 'done',
      resource_id: null,
      retry_after_seconds: 0,
      error: null,
    };
  });
  const controller = new AbortController();
  await assert.rejects(api.searchMissions(input, controller.signal, () => controller.abort()));
  const result = await api.searchMissions(input, new AbortController().signal, () => {});
  assert.equal(result.status, 'no_suitable_place');
  assert.equal(calls[1].route, `/mission-searches/${uuid}`);
  assert.equal(calls[1].method, undefined);
});
test('GPS requires permission, finite accuracy <=50 and fresh native sample', async (t) => {
  const now = Date.now();
  for (const [name, granted, accuracy, timestamp, ok] of [
    ['denied', false, 1, now, false],
    ['null accuracy', true, null, now, false],
    ['poor accuracy', true, 50.1, now, false],
    ['NaN', true, NaN, now, false],
    ['stale', true, 1, now - 61000, false],
    ['future', true, 1, now + 6000, false],
    ['boundary', true, 50, now, true],
  ])
    await t.test(name, async () => {
      const api = load('src/features/capture/lib/location.ts', {
        'expo-location': {
          Accuracy: { High: 4 },
          requestForegroundPermissionsAsync: async () => ({ granted }),
          getCurrentPositionAsync: async () => ({
            coords: { latitude: 0, longitude: 0, accuracy },
            timestamp,
          }),
        },
      });
      if (!ok) await assert.rejects(api.captureLocation());
      else {
        const result = await api.captureLocation();
        assert.equal(result.accuracy_m, 50);
        assert.equal(result.source, 'gps');
      }
    });
});
test('multipart evidence and portrait are separate; retry keeps GPS/body/keys; opt-out uploads no portrait', async () => {
  const uploads = [],
    submissions = [];
  class TestForm {
    append(...args) {
      this.fields = args;
    }
  }
  const api = load(
    'src/services/api/capture.ts',
    {
      'react-native': { Platform: { OS: 'android' } },
      '@/features/social/api/session': session,
      './idempotency': { newKey: () => 'key' },
      './client': {
        requestJson: async (route, options) => {
          uploads.push(options);
          return {
            id:
              options.headers['Idempotency-Key'] === 'portrait-key'
                ? '20000000-0000-4000-8000-000000000002'
                : uuid,
          };
        },
      },
      './social': {
        discovery: z.unknown(),
        pageSchema: () => z.unknown(),
        socialRequest: async (_token, route, _schema, options) => {
          submissions.push(options);
          throw new Error('network response lost');
        },
      },
    },
    { FormData: TestForm },
  );
  const draft = {
    ownerId: 'test-owner',
    mode: 'mission',
    mission: { id: uuid, version: 2 },
    photo: { uri: 'file:///test-evidence.jpg' },
    portraitPhoto: { uri: 'file:///test-portrait.jpg' },
    captureLocation: {
      latitude: 0,
      longitude: 0,
      accuracy_m: 3,
      captured_at: new Date().toISOString(),
      source: 'gps',
    },
    souvenirOptIn: true,
  };
  const keys = {
    upload: 'evidence-key',
    portraitUpload: 'portrait-key',
    submit: 'submission-key',
    retry: 'retry-key',
  };
  for (let i = 0; i < 2; i++)
    await assert.rejects(api.uploadAndSubmit(draft, keys, new AbortController().signal));
  assert.equal(submissions[0].body, submissions[1].body);
  assert.equal(
    submissions[0].headers['Idempotency-Key'],
    submissions[1].headers['Idempotency-Key'],
  );
  assert.equal(uploads[0].body.fields[0], 'photo');
  assert.equal(uploads[1].body.fields[1].uri, draft.portraitPhoto.uri);
  assert.deepEqual(JSON.parse(submissions[0].body).capture_location, draft.captureLocation);
  assert.notEqual(
    JSON.parse(submissions[0].body).portrait_asset_id,
    JSON.parse(submissions[0].body).asset_id,
  );
  const count = uploads.length;
  await assert.rejects(
    api.uploadAndSubmit({ ...draft, souvenirOptIn: false }, keys, new AbortController().signal),
  );
  assert.equal(uploads.length, count + 1);
  assert.equal(JSON.parse(submissions[2].body).portrait_asset_id, null);
});
