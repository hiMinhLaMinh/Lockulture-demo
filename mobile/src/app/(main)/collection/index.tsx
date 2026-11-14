import { forFixtureActor } from '@/features/social/api/actor-screen';
import { env } from '@/config/env';
import { ApiCollection } from '@/features/social/api/posts';
import MockScreen from '@/features/collection/screens/collection-screen';

export default env.dataSource === 'api' ? forFixtureActor(ApiCollection) : MockScreen;
