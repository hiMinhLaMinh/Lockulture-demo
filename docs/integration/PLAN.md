# Kế hoạch tích hợp

[Chỉ mục](../README.md). Thiết kế đã chốt trong [implementation pack](../implementation/README.md); Firebase là Auth/Firestore/Storage, FastAPI là nghiệp vụ và AI.

Trình tự và điều kiện hoàn tất từng task nằm tại [TASKS](../implementation/TASKS.md): contract → dữ liệu/auth → upload/kết quả → AI live → social → tương tác/ranking → hoàn thiện UI → deploy/nghiệm thu.

| Khoảng cách hiện tại | Điểm cần xử lý |
|---|---|
| Auth và dữ liệu local | [CORE](CORE.md) |
| Social state/ACL local | [SOCIAL](SOCIAL.md) |
| Retry, upload, background jobs | [RELIABILITY](RELIABILITY.md) |
| Khác biệt code upstream | [UPSTREAM_MERGE](UPSTREAM_MERGE.md) |

Không cần viết lại UI. Thay nguồn dữ liệu ở service/hook, hoàn thiện scaffold, gỡ quyền cấp XP/ACL từ client. [FRONTEND_MAP](../implementation/FRONTEND_MAP.md) chỉ ra endpoint và query cần refresh.
