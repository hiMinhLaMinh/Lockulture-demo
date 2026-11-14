import { forFixtureActor } from '@/features/social/api/actor-screen';
import { env } from '@/config/env';
import { ApiExplore } from '@/features/social/api/phase-status';
import MockScreen from '@/features/exploration/screens/explore-screen';

export default env.dataSource === 'api' ? forFixtureActor(ApiExplore) : MockScreen;
