import { env } from '@/config/env';
import { FixtureLogin } from '@/features/social/api/account';
import MockScreen from '@/features/auth/screens/login-screen';

export default env.dataSource === 'api' ? FixtureLogin : MockScreen;
