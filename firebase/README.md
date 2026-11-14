# Firebase — thiết kế dữ liệu hiện hành

Đã chọn Firebase Auth, Cloud Firestore Native mode và Cloud Storage for Firebase. FastAPI trên Cloud Run vẫn là API nghiệp vụ; mobile chỉ gọi Firebase trực tiếp cho Auth. Không dùng Realtime Database.

Đọc [mô hình dữ liệu](../docs/implementation/DATA_TRANSACTIONS.md), [quyền](../docs/implementation/AUTH_PERMISSIONS.md), [vận hành](../docs/implementation/OPERATIONS.md).

Firestore không dùng SQL migrations/FK/unique constraints. Backend phải validate schema, kiểm references và dùng transaction + document ID xác định cho uniqueness. Seed catalog từ contracts/fixtures/eras.json qua Admin SDK, idempotent theo era ID. Mỗi document có schema_version=1; migration là script có version/checkpoint, dry-run và backup trước khi chạy.

Rules đi kèm chặn client đọc/ghi trực tiếp toàn bộ database/bucket; server Admin SDK dùng IAM và phải tự kiểm ACL. Không coi deny rules là bảo vệ chống lỗi backend.

Project `lockulture-f9c7d` đã được tạo, bật Email/Password Auth và khởi tạo Firestore theo thông tin người dùng cung cấp. Chưa xác minh việc deploy rules/indexes hoặc chạy Emulator/staging integration tests. SQL cũ tại legacy/supabase-pack chỉ để tham khảo lịch sử, không phải schema mục tiêu.

Runtime hiện dùng `STORAGE_TYPE=local` vì project chưa có Storage bucket. Local upload chỉ dành cho development/test và được lưu trong volume backend; không dùng cho production/Cloud Run. Khi có bucket, chuyển sang `STORAGE_TYPE=firebase`, cấu hình `STORAGE_BUCKET` đúng tên bucket và cấp IAM cho service account.
