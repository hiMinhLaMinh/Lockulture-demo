# Lockulture

Ứng dụng khám phá lịch sử và văn hóa qua hai chế độ: **chụp tự do** và **nhiệm vụ địa điểm**. Người chơi thu thập mảnh ghép trên timeline, nhận XP và chủ động chia sẻ với bạn bè/nhóm.

Dự án của nhóm **3 thành viên**, tham gia Mini Hackathon GDG miền Trung 2026, chủ đề DevFest “Learn Beyond Limits”.

## Tài liệu hiện hành

Bắt đầu tại [docs/README.md](docs/README.md). Bộ tài liệu đã được tổ chức lại ngày 11/11/2026, phân biệt quyết định sản phẩm, hiện trạng code, luồng UI và [gói triển khai Firebase](docs/implementation/README.md).

- [Luật sản phẩm đã chốt](docs/PROJECT_SPECIFICATION.md)
- [Hiện trạng frontend/backend](docs/CURRENT_STATE.md)
- [Kế hoạch tích hợp](docs/integration/PLAN.md)
- [Hướng dẫn chạy mobile](mobile/README.md)

<<<<<<< HEAD
Frontend React Native/Expo đã có Missions, Capture, Friends/Groups, chia sẻ chọn người nhận, cảm xúc/bình luận và leaderboard bằng mock local. Một số trang auth/chi tiết vẫn scaffold. Backend FastAPI đã có verification gọi Gemini từ main; các luồng khác còn mẫu, chưa Maps/auth/đồng bộ nhiều tài khoản. React Native chưa nối API này; xem docs/integration/UPSTREAM_MERGE.md.
=======
Frontend chính là React Native/Expo. Working tree hiện có luồng Firebase Auth email/password, API client gửi Firebase ID token và backend FastAPI có Firebase Admin/Firestore services cùng social API. Chưa có bằng chứng Emulator/staging cho toàn bộ nghiệp vụ; upload ảnh đang dùng local volume chỉ trong dev vì project hiện chưa có Storage bucket.
>>>>>>> ee57e4c (Khởi tạo tài khoản của firebase và cơ sở hạ tầngd dể kết nối tới firebase)

## Chạy scaffold hiện tại

Từ thư mục gốc repo:

```bash
cp .env.example .env
docker compose up --build -d
docker compose logs -f backend
```

`.env` là cấu hình cục bộ, không commit khóa API hoặc service-account key. Tạo `backend/.env` từ `backend/.env.example`; đặt service account tại `backend/service-account.json`. Backend local: [Swagger](http://localhost:8080/docs), [health](http://localhost:8080/health). Firebase-backed routes yêu cầu tài khoản email đã xác minh.

```bash
cd mobile
nvm use
npm ci
npm run start:go
```

Cần Node 24 LTS và Expo Go tương thích SDK 58 hoặc development build; web preview dùng `npm run web`. Bản frontend có camera live, Missions và đánh giá/thưởng Capture bằng mock; chưa nối AI thật hoặc hoàn thiện toàn bộ nghiệp vụ. Camera/GPS cần kiểm tra trên thiết bị thật; mock không chứng minh agent hoạt động thật.

## Cấu trúc hiện có

```text
Lockulture/
├── docs/                 # Đặc tả, luồng UI, kiến trúc và API
├── mobile/src/           # React Native/Expo, routes, features, services và mock
├── legacy/flutter/       # Scaffold Flutter cũ để tham khảo
├── backend/src/          # FastAPI, schemas và bốn vai trò agent mẫu
├── backend/Dockerfile
├── backend/requirements.txt
├── compose.yaml
└── .env.example
```

Đích triển khai backend vẫn là Docker trên **Google Cloud Run**. Firebase Auth/Firestore/Cloud Storage đã chốt. Model cụ thể và secrets môi trường phải cấu hình, kiểm thử khi triển khai; chưa có URL production được xác nhận.
