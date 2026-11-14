import { forFixtureActor } from '@/features/social/api/actor-screen';
import { env } from '@/config/env';
import { ApiFeed } from '@/features/social/api/posts';
import MockScreen from '@/features/feed/screens/feed-screen';

export default env.dataSource === 'api' ? forFixtureActor(ApiFeed) : MockScreen;
