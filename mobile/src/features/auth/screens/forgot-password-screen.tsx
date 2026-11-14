import { useState } from 'react';
import { Text } from 'react-native';
import { router } from 'expo-router';
import { sendPasswordResetEmail } from 'firebase/auth';
import { AuthField } from '@/features/auth/components/auth-field';
import { authError } from '@/features/auth/firebase-errors';
import { authFromConfig } from '@/features/auth/firebase-session';
import { Action } from '@/shared/components/action';
import { Screen } from '@/shared/components/screen';
import { commonStyles as c } from '@/shared/components/surface';

export default function FeatureScreen() {
  const [email, setEmail] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function resetPassword() {
    setError('');
    setMessage('');
    if (!email.trim()) {
      setError('Nhập email đã đăng ký.');
      return;
    }
    setPending(true);
    try {
      const firebaseAuth = await authFromConfig();
      await sendPasswordResetEmail(firebaseAuth, email.trim());
      setMessage('Nếu email có tài khoản, Firebase sẽ gửi hướng dẫn đặt lại mật khẩu.');
    } catch (cause) {
      setError(authError(cause));
    } finally {
      setPending(false);
    }
  }

  return (
    <Screen title="Đặt lại mật khẩu" description="Firebase sẽ gửi liên kết đặt lại mật khẩu tới email của bạn.">
      <AuthField
        label="Email"
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        autoComplete="email"
        keyboardType="email-address"
        textContentType="emailAddress"
      />
      {error ? <Text accessibilityRole="alert" style={c.body}>{error}</Text> : null}
      {message ? <Text style={c.body}>{message}</Text> : null}
      <Action label="Gửi liên kết" loading={pending} onPress={() => void resetPassword()} />
      <Action secondary label="Quay lại đăng nhập" onPress={() => router.replace('/(auth)/login')} />
    </Screen>
  );
}
