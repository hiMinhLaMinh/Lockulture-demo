# Nghiệm thu và bằng chứng

[Chỉ mục](README.md) · [36 kịch bản máy đọc](../../contracts/acceptance.json) · [Bằng chứng pack](VERIFICATION.md).

## Các mức kiểm tra

| Mức | Cách chạy | Điều chứng minh |
|---|---|---|
| Contract | `python scripts/contract/validate.py` | OpenAPI/schema/payload/catalog/link và coverage operation nhất quán |
| HTTP fixture | Viết pytest/httpx cho API-01…20, INV-01…12, model/Maps adapter deterministic | Handler, actor, transactions, budgets, job recovery và client DTO hoạt động |
| Firebase staging | LIVE-01, LIVE-04; Auth thật, Storage private, runtime role đúng | Không nhầm stub local với Firebase Auth/Storage |
| Provider live | LIVE-03 với key/model/Maps thật | Đường gọi thật và output hữu ích; không fallback fixture |
| Mobile hai thiết bị | LIVE-02 và toàn UI map | Camera/native lifecycle, resume, gửi nhận, phản hồi, tiến trình đa tài khoản |


## Dữ liệu test


Test API bằng raw HTTP với JWT từng actor, không chỉ ẩn UI: đoán UUID bài/asset, đổi owner/group IDs, lấy URL ảnh không có grant, rời/rejoin, cùng key khác payload. Kiểm ledger/discovery/post count sau concurrency và crash injection, không chỉ response200.

## Luồng UI bắt buộc

- Auth confirm/reset/deep link, login/logout/refresh, clear cache khi đổi tài khoản.
- Chọn era/GPS/manual, giữ tọa độ nhập, giữ mission khi search no_result, hint không gọi AI.
- Free và mission: upload, pending, lỗi, retake, unidentified, mismatch, success; restore app giữa job; không thưởng kép.
- Compose nhiều bạn/nhóm, mặc định chưa chọn; failure giữ draft. Feed/ảnh signed URL refresh; comment/reaction; friends/groups/ranking đúng quyền.
- Timeline ba mảnh/era từ server, nhiệm vụ100XP/free20XP theo luật ngày; app không mutate điểm local ở API mode.
- Giữ tab bar ở Friends/Groups/Leaderboard; camera không tab. Typography/palette theo DESIGN_SYSTEM.

## Cổng phát hành


Các chi tiết môi trường cần cung cấp lúc triển khai: Firebase project, Cloud project/region, domain callback, secrets provider, model đã smoke. Đây là cấu hình vận hành; agent có đủ luật để viết code trước, không cần tự chọn lại sản phẩm.

## Cổng kiểm Firebase

Viết Emulator tests cho duplicate reward, profile/username reservation, concurrent membership/publication, lease takeover và idempotency. Tạo user bằng Firebase Auth Emulator/staging, map UID sang UUID nội bộ. Rules tests phải chứng minh mobile bị từ chối đọc/ghi Firestore/Storage trực tiếp. Backend tests dùng Admin SDK phải kiểm riêng ACL vì Admin bỏ qua rules. Staging kiểm signed URL/IAM/Auth email flows và indexes. Kết quả17tests PostgreSQL trước đây không áp dụng. Chưa có các tests Firebase trong repo ở đợt này.
