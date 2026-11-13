# Quyết định MVP v1 — đã chốt cho triển khai

[Chỉ mục](README.md) · Config máy đọc: [config.json](../../contracts/fixtures/config.json).

## Stack và ranh giới

- React Native/Expo/TypeScript hiện tại là frontend chính.
- FastAPI/Python chạy Docker trên Cloud Run. Bốn agent là vai trò trong cùng codebase.
- Firebase Auth dùng email/password, Firestore giữ metadata, Storage giữ ảnh trong bucket private `discoveries`. Không dùng Supabase hoặc Realtime Database.
- Firebase Admin SDK với IAM chỉ dùng server để quản lý Storage và bootstrap test accounts. Realtime/push chưa bắt buộc; refresh khi focus, kéo làm mới và polling jobs.

## Luật điểm và tiến trình

- Free hợp lệ +20, mission hoàn thành +100. Một mission chỉ hoàn thành/cấp thưởng một lần.
- Free cùng subject_key chỉ thưởng một lần/ngày theo Asia/Ho_Chi_Minh, tính ngày tạo submission đầu tiên, không ngày worker chạy xong. Lần hợp lệ tiếp vẫn có discovery/kiến thức, XP 0 và reason daily_subject_limit.
- Ba subject khác nhau cho một era để giải mã; tối đa 3 mảnh. Một subject/era không thêm mảnh lần hai. Không có era phù hợp thì không thêm mảnh; free vẫn có thể nhận XP.
- Daily XP gate không chặn mảnh nếu discovery mới thật sự bổ sung subject/era; tất cả cập nhật trong cùng transaction khóa theo owner.
- Hint/answer không trừ điểm. Reaction/comment/share không tạo XP. Retry không tạo discovery hoặc thưởng mới.
- Leaderboard toàn thời gian gồm actor và friends accepted; rank = 1 + số người XP cao hơn. Đồng XP cùng hạng; tie sort username rồi UUID.

## Chia sẻ và nhóm

- Chọn người nhận bắt buộc; tối đa 50 bạn trực tiếp và 10 nhóm mỗi lần, dedupe ID trước xử lý. Mọi ID phải hợp lệ; sai một ID thì rollback toàn bộ, không gửi một phần.
- Một post cho mỗi discovery, soft delete không cho tái đăng cùng discovery trong MVP. Chia sẻ thêm chỉ thêm nhóm mới, không mở rộng snapshot nhóm cũ.
- Snapshot thành viên tại lúc chia sẻ, có membership incarnation ID. Thành viên mới không đọc bài cũ; rời rồi vào lại cũng không khôi phục grant cũ.
- Rời/bị xóa/giải tán nhóm mất nguồn quyền từ nhóm đó; giữ quyền nếu còn trực tiếp hoặc nhóm khác. Xóa bạn không thu hồi bài trực tiếp đã gửi.
- Owner luôn đọc bài của mình trừ khi đã xóa; global feed gồm bài mình và bài được nhận. Feed nhóm đòi membership hiện tại và nguồn chia sẻ nhóm còn hiệu lực.
- Owner thêm ngay friends accepted vào nhóm, không invitation riêng trong MVP; tối đa 20 thành viên. Owner không rời mà phải giải tán; chưa chuyển quyền owner.
- Caption 0–500 ký tự; bình luận trim 1–300; chỉ tác giả xóa bình luận của mình, kể cả khi mất quyền đọc bài. Chưa có sửa bình luận, moderator hay chat.

## Hạn mức và lưu dữ liệu

- 10 search/user/giờ UTC, 30 submission/user/giờ UTC; cùng idempotency key không trừ quota lại. Retry API tính quota, worker redelivery không tính lại.
- Một search và một submission mỗi session đang xử lý; 4 ảnh tối đa/session, hết 24h đóng phiên. Search tối đa 2 Maps + 3 Gemini; mỗi submission tối đa 1 Gemini, ngân sách tính trước call và không reset khi delivery lại.
- 8 MiB/ảnh, 20 MP, JPEG/PNG/WebP đầu vào; server re-encode JPEG <=1080, bỏ EXIF; không anti-spoof hoặc GPS proof.
- Ảnh orphan xóa sau 24h, bằng chứng thất bại/không tạo discovery xóa sau 7 ngày; ảnh gắn discovery giữ tới yêu cầu xóa tài khoản thủ công. Không có account deletion self-service trong MVP.
- Job deadline 10 phút; tối đa 3 delivery attempts; signed read URL 60 giây; idempotency response giữ 7 ngày. Các hằng số do config version quản lý; đổi luật phải cập nhật fixtures/tests.

Mobile chỉ gọi Firebase trực tiếp cho Auth. Firestore và Storage chỉ do FastAPI/Admin SDK truy cập, actor lấy từ ID token. Admin SDK bỏ qua Security Rules; backend tự kiểm quyền. Bucket dùng tên thật trong STORAGE_BUCKET, prefix discoveries nếu cần; không giả tên bucket luôn là discoveries.
