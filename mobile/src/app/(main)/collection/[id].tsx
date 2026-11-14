import { forFixtureActor } from '@/features/social/api/actor-screen';
import { env } from '@/config/env';
import { ApiDiscovery } from '@/features/social/api/posts';
import MockScreen from '@/features/collection/screens/discovery-detail-screen';

export default env.dataSource === 'api' ? forFixtureActor(ApiDiscovery) : MockScreen;
