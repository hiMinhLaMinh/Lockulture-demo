import { forFixtureActor } from '@/features/social/api/actor-screen';
import { env } from '@/config/env';
import { ApiCreateGroup } from '@/features/social/api/groups';
import MockScreen from '@/features/groups/screens/create-group-screen';

export default env.dataSource === 'api' ? forFixtureActor(ApiCreateGroup) : MockScreen;
