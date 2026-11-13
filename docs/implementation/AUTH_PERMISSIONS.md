# Firebase Auth và quyền

Mobile dùng Firebase Auth SDK email/password: createUserWithEmailAndPassword, sendEmailVerification, signInWithEmailAndPassword, sendPasswordResetEmail, signOut. Chỉ vào nghiệp vụ khi email_verified=true. Cấu hình persistence phù hợp Expo/native và callback xác nhận/reset; kiểm thử trên điện thoại trước khi bàn giao.

Gửi Firebase ID token trong Authorization Bearer. FastAPI dùng Firebase Admin verify_id_token, kiểm project/audience/issuer/expiry/email_verified; không dùng custom token như ID token. Khi401 client refresh ID token một lần và retry cùng idempotency key, thất bại quay login. Logout xóa cache/draft theo account. Không commit service account key.

Firebase UID không phải UUID. Giữ HTTP contract UUID bằng mapping auth_identities/{SHA256(firebase_uid)} → user_id UUID do server cấp. GET /me tạo mapping và profiles trong một Firestore transaction, đọc lại khi retry; mọi route resolve actor từ mapping đã xác minh. Không nhận user_id từ client để xác định actor. Username mặc định dùng UUID nội bộ; usernames/{normalized_username} giữ unique reservation trong transaction.

## Quyền nghiệp vụ

- Mission/search/submission/discovery/timeline: owner; resource riêng tư không được nhìn trả404.
- User profile/search: signed-in, chỉ public fields, không email. Leaderboard gồm actor và accepted friends.
- Friend request: sender cancel, recipient accept/reject. Group: active members đọc; owner quản trị; member tự rời, owner giải tán.
- Post: author hoặc direct grant hoặc group grant còn membership incarnation hợp lệ. Thành viên mới/rejoin không nhận bài cũ; direct grant tồn tại sau unfriend.
- Asset: owner hoặc post context hợp lệ, asset khớp bài. Comment/reaction cần quyền post; xóa comment chỉ author kể cả sau mất quyền đọc.
- Quyền role bị cấm trên resource nhìn được trả403. Counts/feed phải lọc ACL trước khi trả.

Mobile không truy cập Firestore/Storage trực tiếp; rules deny-all ở firebase/. Admin SDK bỏ qua rules nên backend bắt buộc kiểm actor và ACL trong repository. Cloud Run dùng service account với IAM cần thiết. Ảnh private dùng URL ký60s sau kiểm quyền; không dùng download URL có token lâu dài. URL đã cấp không thu hồi ngay; dữ liệu đã tải có thể được người nhận giữ lại.

Nguồn: [xác minh ID token](https://firebase.google.com/docs/auth/admin/verify-id-tokens), [server SDK và Security Rules](https://firebase.google.com/docs/firestore/security/rules-conditions).
