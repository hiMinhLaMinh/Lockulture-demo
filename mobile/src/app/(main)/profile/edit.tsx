import { forFixtureActor } from '@/features/social/api/actor-screen';
import { env } from '@/config/env';
import { ApiEditProfile } from '@/features/social/api/account';
import MockScreen from '@/features/profile/screens/edit-profile-screen';

export default env.dataSource === 'api' ? forFixtureActor(ApiEditProfile) : MockScreen;
