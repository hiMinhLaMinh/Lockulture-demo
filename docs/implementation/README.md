# Gói triển khai Lockulture v1

Phân công nhóm và thứ tự bàn giao: [Kế hoạch công việc](../TEAM_WORK_PLAN.md) — thành viên 1 → thành viên 3 → thành viên 2.
Chốt 11/11/2026 sau khi người dùng đồng ý các đề xuất tích hợp và chọn Firebase.

Đây là **bộ đầu vào để xây hệ thống**, không phải tuyên bố hệ thống online đã hoàn tất. Chưa tạo project Firebase, cấp secrets hay deploy Cloud Run. Code app hiện tại vẫn mock; backend hiện hành vẫn có policy cũ như CURRENT_STATE/UPSTREAM_MERGE.

## Thứ tự đọc cho Codex / Antigravity

1. [Quyết định bắt buộc](DECISIONS.md) + [sản phẩm](../PROJECT_SPECIFICATION.md).
2. [Auth và quyền](AUTH_PERMISSIONS.md), [quy ước API](API_RULES.md), [OpenAPI](../../contracts/openapi.yaml).
4. [Tác vụ AI](AI_JOBS.md), [upload/deploy](OPERATIONS.md).
5. [Bản đồ frontend](FRONTEND_MAP.md), [nhiệm vụ triển khai](TASKS.md).
6. [Nghiệm thu](ACCEPTANCE.md), [kịch bản máy đọc](../../contracts/acceptance.json), [bằng chứng pack](VERIFICATION.md).

## Nguồn chuẩn

- Các tài liệu `integration/` tóm tắt khoảng cách code → thiết kế và link tới quyết định tại đây. Không dùng legacy/flutter/docs làm luật sản phẩm.
- Không tự thay free/mission bằng boolean is_valid; không đưa anti-spoof, auto-post hoặc reward 150 từ backend cũ vào API v1 mới.
- Nếu contract/schema/luật mâu thuẫn, báo đúng vị trí, sửa đồng thời và chạy validation. Không tạo thêm một nguồn chuẩn riêng cho từng agent.
- Hướng dẫn repo và yêu cầu người dùng vẫn có ưu tiên theo hệ thống chỉ dẫn của agent.

## Phạm vi bàn giao


## Điều kiện hoàn thành hệ thống trong tương lai

Tất cả task và kịch bản live ở ACCEPTANCE pass, hai tài khoản trên hai thiết bị gửi–nhận được, client không còn cấp XP/ACL, artifact đã deploy trùng commit kiểm thử. Gói tài liệu pass kiểm tra **không** đồng nghĩa đã đạt điều kiện này.

## Dữ liệu Firebase

Đọc [mô hình collections/transactions](DATA_TRANSACTIONS.md) và [rules/provision](../../firebase/README.md) trước khi viết repository. Không dùng SQL artifacts trong legacy/supabase-pack. Contract giữ UUID nội bộ bằng mapping Firebase UID. Bộ đầu vào gồm OpenAPI, fixtures, AI schemas, Firebase model/rules và acceptance; Emulator/indexes/staging còn phải xây và kiểm thử.
