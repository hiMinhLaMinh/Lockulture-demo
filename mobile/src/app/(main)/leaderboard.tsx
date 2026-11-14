import { forFixtureActor } from '@/features/social/api/actor-screen';
import { env } from '@/config/env';
import { ApiLeaderboard } from '@/features/social/api/account';
import MockScreen from '@/features/leaderboard/screens/leaderboard-screen';

export default env.dataSource === 'api' ? forFixtureActor(ApiLeaderboard) : MockScreen;
