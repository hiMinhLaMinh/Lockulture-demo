# Trạng thái kiểm chứng sau đổi Firebase

Ngày11/11/2026. Phương án hiện hành: Firebase Auth, Firestore, Cloud Storage.

Contract/examples được kiểm bằng scripts/contract/validate.py. 17tests PostgreSQL trước đây chỉ kiểm phương án Supabase đã lưu ở legacy/supabase-pack; không dùng làm bằng chứng Firebase pass.

Chưa chạy Firebase Emulator, deploy Security Rules/indexes, kiểm IAM/Storage URL signing, Auth native hoặc giao tiếp live. Cần xây các tests Firestore theo acceptance trước khi nghiệm thu. Không sửa runtime app/backend trong đợt này.
