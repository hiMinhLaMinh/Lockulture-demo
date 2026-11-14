import { forFixtureActor } from '@/features/social/api/actor-screen';
import { env } from '@/config/env';
import { ApiCompose } from '@/features/social/api/posts';
import MockScreen from '@/features/feed/screens/compose-screen';

export default env.dataSource === 'api' ? forFixtureActor(ApiCompose) : MockScreen;
