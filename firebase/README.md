# Firebase — thiết kế dữ liệu hiện hành

Đã chọn Firebase Auth, Cloud Firestore Native mode và Cloud Storage for Firebase. FastAPI trên Cloud Run vẫn là API nghiệp vụ; mobile chỉ gọi Firebase trực tiếp cho Auth. Không dùng Realtime Database.

Đọc [mô hình dữ liệu](../docs/implementation/DATA_TRANSACTIONS.md), [quyền](../docs/implementation/AUTH_PERMISSIONS.md), [vận hành](../docs/implementation/OPERATIONS.md).

Firestore không dùng SQL migrations/FK/unique constraints. Backend phải validate schema, kiểm references và dùng transaction + document ID xác định cho uniqueness. Seed catalog từ contracts/fixtures/eras.json qua Admin SDK, idempotent theo era ID. Mỗi document có schema_version=1; migration là script có version/checkpoint, dry-run và backup trước khi chạy.

Rules đi kèm chặn client đọc/ghi trực tiếp toàn bộ database/bucket; server Admin SDK dùng IAM và phải tự kiểm ACL. Không coi deny rules là bảo vệ chống lỗi backend.

Project `lockulture-f9c7d` là đích staging. Dùng [runbook giai đoạn B](../docs/implementation/PHASE_B_HANDOFF.md) để chạy Emulator và cấu hình deploy rules, indexes và Storage private. Tên bucket lấy từ project. `STORAGE_TYPE=local` dùng cho development/test.
