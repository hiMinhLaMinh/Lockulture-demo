# Lockulture — tài liệu hiện hành

Phân công nhóm và thứ tự bàn giao: [Kế hoạch công việc](TEAM_WORK_PLAN.md) — thành viên 1 → thành viên 3 → thành viên 2.
Cập nhật 11/11/2026. Firebase đã được chọn; backend mục tiêu là FastAPI trên Cloud Run, frontend React Native/Expo.

## Bắt đầu theo công việc

| Người đọc | Tài liệu |
|---|---|
| AI agent triển khai toàn hệ thống | [Gói triển khai v1](implementation/README.md), đọc theo thứ tự ở đó |
| Thành viên tìm hiểu sản phẩm | [Quyết định sản phẩm](PROJECT_SPECIFICATION.md), [kiến trúc](ARCHITECTURE.md) |
| Sửa frontend | [Hiện trạng](CURRENT_STATE.md), [UI](DESIGN_SYSTEM.md), [bản đồ nối API](implementation/FRONTEND_MAP.md) |
| Tìm thao tác màn hình | [Khám phá](flows/DISCOVERY.md), [Camera](flows/CAPTURE.md), [Xã hội](flows/SOCIAL.md) |
| Kiểm thử/bàn giao | [Nghiệm thu](implementation/ACCEPTANCE.md), [bằng chứng pack](implementation/VERIFICATION.md) |

## Phân biệt thiết kế và code

[CURRENT_STATE](CURRENT_STATE.md) và [API hiện hành](api/CURRENT.md) mô tả code đang có. [API mục tiêu](api/TARGET.md) và implementation là thiết kế đã chốt nhưng chưa nối live. Schema/test pass không đồng nghĩa ứng dụng đã hoàn thành hay dữ liệu đã đồng bộ nhiều người.


Hướng dẫn repo và yêu cầu trực tiếp của người dùng vẫn theo thứ tự ưu tiên chỉ dẫn của agent. Các tài liệu bên ngoài docs và trong legacy/flutter là tư liệu lịch sử, không phải nguồn quy tắc mới.

## Hiện trạng cần đối chiếu

[Ghi chú merge](integration/UPSTREAM_MERGE.md) giữ các khác biệt từ main. Các file [integration](integration/PLAN.md) nay tóm tắt khoảng cách code → thiết kế; lựa chọn Firebase, quota, quyền và luật thưởng không còn bỏ ngỏ.

Chưa có project/secrets/URL production được tạo hay xác nhận trong đợt viết pack. Người triển khai cấu hình môi trường thật theo [OPERATIONS](implementation/OPERATIONS.md), chạy smoke tests và ghi kết quả. Đây là đầu việc triển khai, không phải lý do tự thay luật sản phẩm.
