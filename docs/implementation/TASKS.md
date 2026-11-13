# Thứ tự triển khai và trách nhiệm

Nguồn phân công hiện hành là [TEAM_WORK_PLAN](../TEAM_WORK_PLAN.md), chốt 12/11/2026: **thành viên 1 → thành viên 3 → thành viên 2 → nghiệm thu chung**. Thứ tự này thay kế hoạch làm nền tảng Firebase trước toàn bộ social.

| Mốc | Chủ trì | Điều kiện bắt đầu | Điều kiện bàn giao |
|---|---|---|---|
| Chuẩn bị | Cả nhóm | Đọc implementation pack | Thống nhất API, repository interfaces và result writer |
| A: Frontend/social | Thành viên 1 | Contract đã rà soát | HTTP/social nghiệp vụ thật, adapters giả tách riêng, tests và hướng dẫn chạy |
| B: Firebase/nền tảng | Thành viên 3 | Nhận interface/tests mốc A | Repositories/Auth/Storage thật, transaction XP, job hạ tầng; luồng end-to-end với assessment fixture |
| C: Missions/AI | Thành viên 2 | Nền tảng và result writer mốc B | Maps/Gemini live, worker/schema/budget đúng, dùng cùng transaction kết quả |
| Nghiệm thu | Cả nhóm | Ba phần ghép được | Hai thiết bị, quyền/XP/retry và các kịch bản live đạt |

Đọc chi tiết phạm vi, ranh giới sở hữu, cổng bàn giao và rủi ro trong tài liệu phân công. API/schema vẫn theo [contract](../../contracts/README.md), luật theo [DECISIONS](DECISIONS.md); không thay chúng chỉ vì mock thuận tiện hơn.

Mỗi PR ghi commit, phần đã thực thi, tests pass/fail/skipped, fixture còn dùng và công việc tiếp theo. Cập nhật CURRENT_STATE khi runtime thay đổi. Không tự đánh dấu hoàn tất từ việc route tồn tại hoặc test in-memory pass; Emulator và live cần bằng chứng riêng.
