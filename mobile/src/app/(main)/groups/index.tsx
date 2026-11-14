import { forFixtureActor } from '@/features/social/api/actor-screen';
import { env } from '@/config/env';
import { ApiGroups } from '@/features/social/api/groups';
import MockScreen from '@/features/groups/screens/groups-screen';

export default env.dataSource === 'api' ? forFixtureActor(ApiGroups) : MockScreen;
