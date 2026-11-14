import { forFixtureActor } from '@/features/social/api/actor-screen';
import { env } from '@/config/env';
import { ApiFriends } from '@/features/social/api/friends';
import MockScreen from '@/features/friends/screens/friends-screen';

export default env.dataSource === 'api' ? forFixtureActor(ApiFriends) : MockScreen;
