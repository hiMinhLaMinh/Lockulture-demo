import { forFixtureActor } from '@/features/social/api/actor-screen';
import { env } from '@/config/env';
import { ApiFriendProfile } from '@/features/social/api/friends';
import MockScreen from '@/features/friends/screens/friend-profile-screen';

export default env.dataSource === 'api' ? forFixtureActor(ApiFriendProfile) : MockScreen;
