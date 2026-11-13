# API v1 mục tiêu — đã chốt, chưa triển khai

[Hiện hành](CURRENT.md) · [Chỉ mục](../README.md).

Nguồn máy đọc duy nhất là [contracts/openapi.yaml](../../contracts/openapi.yaml): 33 đường dẫn, 43 thao tác, base `/api/v1`. [Payload mẫu](../../contracts/examples/) và [acceptance](../../contracts/acceptance.json) dùng cùng schema. Không suy ra backend đã có route mới từ file này.

## Nhóm chức năng

| Nhóm | Route chính |
|---|---|
| Auth | Firebase SDK email/password, confirmation, reset, refresh; không thêm auth API tự viết |
| Hồ sơ/tiến trình | /me, /users, /timeline, /discoveries, /leaderboard |
| Tìm nhiệm vụ | /mission-searches, /missions/active, /missions/{id}, hints, answer |
| Ảnh và kết quả | /assets, /assets/{id}/url, /submissions, retry |
| Quan hệ | /friends, /friend-requests |
| Nhóm | /groups, members |
| Bài và tương tác | /posts, shares, reaction, comments |

## Hợp đồng cần tuân thủ

- Bearer Firebase JWT, actor lấy từ token; snake_case JSON, UUID server, UTC timestamps.
- Mutation dùng Idempotency-Key; upload multipart qua FastAPI; URL đọc ảnh private có hạn.
- Search/submission trả 202; client GET/poll, không tự POST lại để kiểm tra trạng thái.
- Error envelope `{error:{code,message,retryable,request_id}}`; list `{items,next_cursor}`.
- Free: accepted/retake_required/unidentified/out_of_scope. Mission: completed/retake_required/unidentified/not_matched.
- Publish chọn nhiều bạn/nhóm; backend tạo snapshot, kiểm quyền đọc bài và ảnh. Không auto-post.

Đọc [API_RULES](../implementation/API_RULES.md) cho validation/pagination/retry, [AUTH_PERMISSIONS](../implementation/AUTH_PERMISSIONS.md) cho ACL, [DATA_TRANSACTIONS](../implementation/DATA_TRANSACTIONS.md) cho atomicity, [AI_JOBS](../implementation/AI_JOBS.md) cho state machines.
