import { forFixtureActor } from '@/features/social/api/actor-screen';
import { env } from '@/config/env';
import { ApiGroupDetail } from '@/features/social/api/groups';
import MockScreen from '@/features/groups/screens/group-detail-screen';

export default env.dataSource === 'api' ? forFixtureActor(ApiGroupDetail) : MockScreen;
