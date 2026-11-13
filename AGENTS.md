# Lockulture — hướng dẫn làm việc trong repo

Frontend chính: `mobile/` React Native/Expo. Backend: `backend/` FastAPI. `legacy/flutter/` là code tham khảo được giữ từ upstream, không phải frontend cần tích hợp.

## Đọc trước khi triển khai

1. `docs/implementation/README.md` và `DECISIONS.md` trong cùng thư mục.
2. `docs/CURRENT_STATE.md` để phân biệt đã có/mock/scaffold.
4. Task tương ứng trong `docs/implementation/TASKS.md` và acceptance trong `contracts/acceptance.json`.

Firebase Auth/Firestore/private Storage và FastAPI/Cloud Run đã chốt. Mobile chỉ dùng Firebase trực tiếp cho Auth. Bốn vai trò AI cùng backend; không đưa secrets hoặc quyền thưởng/ACL vào mobile. Quyết định mới bỏ anti-spoof, auto-post, Co-op và XP150; không phục hồi các luật này từ tài liệu/code lịch sử.

## Khi sửa

- Giữ UI theo `docs/DESIGN_SYSTEM.md`; thay nguồn dữ liệu qua adapter/hook, không viết lại frontend sang Flutter/web.
- Đổi API/luật phải cập nhật contract, schema, examples và acceptance cùng thay đổi. Đọc quyền/transaction trước khi viết repository.
- Không trộn fixture vào API live hoặc upload mock XP/posts sang tài khoản thật.
- Báo test đã chạy và giới hạn; tài liệu mục tiêu không phải bằng chứng runtime hoàn thành. Cập nhật CURRENT_STATE sau khi feature thật được triển khai.
- Không có yêu cầu tự động chia nhiều agent; chỉ phân công song song khi người dùng yêu cầu và tránh cùng sửa một schema.

## Kiểm tra pack


## Firebase đã chốt

Đọc `firebase/README.md` và `docs/implementation/DATA_TRANSACTIONS.md`. Không dùng `legacy/supabase-pack/` để triển khai; đó là lịch sử. Backend dùng Firebase Admin, mobile chỉ Auth. Chạy `python scripts/contract/validate.py` kiểm contract; Firebase Emulator và staging cần tests riêng, chưa được thay thế bởi tests SQL cũ.
