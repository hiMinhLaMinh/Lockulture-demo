# Firebase và triển khai

1. Tạo Firebase project staging, bật Auth email/password, cấu hình email verification/reset và app links; bật Firestore Native mode và Cloud Storage private. Cấu hình billing/quota theo dịch vụ thực tế trước deploy.
2. Cloud Run dùng Application Default Credentials của service account; cấp IAM cho Firestore, object storage, ký URL và Cloud Tasks theo nhu cầu. Không đưa admin credentials vào mobile.
3. Deploy rules tại firebase/, seed10eras theo ID qua Admin SDK, triển khai indexes theo truy vấn. Emulator kiểm Auth/Firestore/Storage; staging kiểm IAM và signed URLs vì Emulator không thay thế các kiểm tra này.
4. Giữ Cloud Tasks/Scheduler/outbox/leases như AI_JOBS; dữ liệu job/outbox nằm Firestore. Dispatcher phải transaction claim generation trước enqueue, xử lý duplicate task name an toàn.

## Upload và ảnh

POST /assets multipart qua FastAPI: tối đa8MiB/20MP JPEG/PNG/WebP, normalize JPEG<=1080 bỏ EXIF. Reservation idempotency Firestore với asset UUID/lease token60s; upload ngoài transaction vào owner/asset/lease.jpg, finalize chỉ nếu lease còn thuộc worker. Hash khác409; lease đang chạy409 retryable=true Retry-After2; replay trả asset cũ. Worker thua cleanup object. Không giữ transaction qua network.

GET asset URL kiểm owner/Post ACL rồi ký Cloud Storage URL60s, Cache-Control:no-store; không persist URL hoặc dùng Firebase download token lâu dài. Dọn orphan24h, evidence không tạo discovery7ngày, giữ ảnh discovery. Cleanup có thể retry; TTL không xóa file bucket thay application.

## Kiểm trước phát hành

HTTPS trên điện thoại, CORS web allowlist, native session persistence, Auth email links, indexes thật, Admin IAM và URL signing, task OIDC allowlist, lỗi provider, deadline/lease recovery. Logs không chứa token/ảnh/URL ký. PROVIDER_MODE=live không fallback fixture. Chưa provision/deploy dịch vụ nào trong đợt đổi tài liệu này.
