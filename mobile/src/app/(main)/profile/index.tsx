import { forFixtureActor } from '@/features/social/api/actor-screen';
import { env } from '@/config/env';
import { ApiProfile } from '@/features/social/api/account';
import MockScreen from '@/features/profile/screens/profile-screen';

export default env.dataSource === 'api' ? forFixtureActor(ApiProfile) : MockScreen;
