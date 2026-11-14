import { useState } from 'react';
import { Text } from 'react-native';
import { createUserWithEmailAndPassword, sendEmailVerification, signOut, updateProfile } from 'firebase/auth';
import { AuthField } from '@/features/auth/components/auth-field';
import { authError } from '@/features/auth/firebase-errors';
import { authFromConfig } from '@/features/auth/firebase-session';
import { Action } from '@/shared/components/action';
import { Screen } from '@/shared/components/screen';
import { commonStyles as c } from '@/shared/components/surface';

export default function FeatureScreen() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function register() {
    setError('');
    setMessage('');
    if (!name.trim() || !email.trim() || password.length < 6) {
      setError('Nhập tên, email hợp lệ và mật khẩu tối thiểu 6 ký tự.');
      return;
    }
    if (password !== confirmation) {
      setError('Mật khẩu xác nhận chưa khớp.');
      return;
    }
    setPending(true);
    try {
      const firebaseAuth = await authFromConfig();
      const credential = await createUserWithEmailAndPassword(firebaseAuth, email.trim(), password);
      await updateProfile(credential.user, { displayName: name.trim() });
      await sendEmailVerification(credential.user);
      await signOut(firebaseAuth);
      setMessage('Đã gửi email xác minh. Xác minh email rồi đăng nhập để tiếp tục.');
    } catch (cause) {
      setError(authError(cause));
    } finally {
      setPending(false);
    }
  }

  return (
    <Screen title="Tạo tài khoản" description="Xác minh email trước khi dùng các tính năng của Lockulture.">
      <AuthField label="Tên hiển thị" value={name} onChangeText={setName} autoComplete="name" />
      <AuthField
        label="Email"
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        autoComplete="email"
        keyboardType="email-address"
        textContentType="emailAddress"
      />
      <AuthField
        label="Mật khẩu"
        value={password}
        onChangeText={setPassword}
        autoCapitalize="none"
        autoComplete="new-password"
        secureTextEntry
        textContentType="newPassword"
      />
      <AuthField
        label="Xác nhận mật khẩu"
        value={confirmation}
        onChangeText={setConfirmation}
        autoCapitalize="none"
        secureTextEntry
        textContentType="newPassword"
      />
      {error ? <Text accessibilityRole="alert" style={c.body}>{error}</Text> : null}
      {message ? <Text style={c.body}>{message}</Text> : null}
      <Action label="Đăng ký" loading={pending} onPress={() => void register()} />
      <Action secondary label="Đã có tài khoản? Đăng nhập" href="/(auth)/login" />
    </Screen>
  );
}
