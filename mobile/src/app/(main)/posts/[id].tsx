import { forFixtureActor } from '@/features/social/api/actor-screen';
import { env } from '@/config/env';
import { ApiPostDetail } from '@/features/social/api/posts';
import MockScreen from '@/features/feed/screens/post-detail-screen';

export default env.dataSource === 'api' ? forFixtureActor(ApiPostDetail) : MockScreen;
