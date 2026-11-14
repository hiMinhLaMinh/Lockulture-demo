import { forFixtureActor } from '@/features/social/api/actor-screen';
import { env } from '@/config/env';
import { ApiCapture } from '@/features/social/api/phase-status';
import MockScreen from '@/features/capture/screens/capture-choice-screen';

export default env.dataSource === 'api' ? forFixtureActor(ApiCapture) : MockScreen;
