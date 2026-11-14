export function authError(cause: unknown) {
  if (cause instanceof Error && 'code' in cause) {
    const code = String(cause.code);
    if (code === 'auth/invalid-credential' || code === 'auth/user-not-found') {
      return 'Email hoặc mật khẩu chưa đúng.';
    }
    if (code === 'auth/email-already-in-use') return 'Email này đã có tài khoản.';
    if (code === 'auth/weak-password') return 'Mật khẩu chưa đủ mạnh.';
    if (code === 'auth/too-many-requests') return 'Bạn thử quá nhiều lần. Hãy đợi rồi thử lại.';
    if (code === 'auth/network-request-failed') return 'Không kết nối được. Kiểm tra mạng rồi thử lại.';
  }
  return cause instanceof Error ? cause.message : 'Không thực hiện được yêu cầu Firebase.';
}
