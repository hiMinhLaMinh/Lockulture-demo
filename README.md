# Lockulture

Ứng dụng khám phá lịch sử và văn hóa qua hai chế độ: **chụp tự do** và **nhiệm vụ địa điểm**. Người chơi thu thập mảnh ghép trên timeline, nhận XP và chủ động chia sẻ với bạn bè/nhóm.

Dự án của nhóm **3 thành viên**, tham gia Mini Hackathon GDG miền Trung 2026, chủ đề DevFest “Learn Beyond Limits”.

## Tài liệu hiện hành

Bắt đầu tại [docs/README.md](docs/README.md). Bộ tài liệu đã được tổ chức lại ngày 11/11/2026, phân biệt quyết định sản phẩm, hiện trạng code, luồng UI và [gói triển khai Firebase](docs/implementation/README.md).

- [Luật sản phẩm đã chốt](docs/PROJECT_SPECIFICATION.md)
- [Hiện trạng frontend/backend](docs/CURRENT_STATE.md)
- [Kế hoạch tích hợp](docs/integration/PLAN.md)
- [Hướng dẫn chạy mobile](mobile/README.md)

Frontend chính là React Native/Expo. Xem [bàn giao giai đoạn B](docs/implementation/PHASE_B_HANDOFF.md) để chạy Firebase Emulator, cấu hình luồng chụp ảnh API và triển khai staging.

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

Cần Node 24 LTS và Expo Go tương thích SDK 58 hoặc development build; web preview dùng `npm run web`. API mode dùng camera và assessment fixture qua FastAPI. Mock mode phục vụ xem trước các luồng trên thiết bị. Nghiệm thu staging cần chạy riêng trên hai thiết bị.

## Cấu trúc hiện có

```text
Lockulture/
├── docs/                 # Đặc tả, luồng UI, kiến trúc và API
├── mobile/src/           # React Native/Expo, routes, features, services và mock
├── backend/src/main.py   # FastAPI với GET /health
├── backend/Dockerfile
├── backend/requirements.txt
├── contracts/            # OpenAPI, schema, ví dụ và acceptance
├── firebase/             # Cấu hình và quy tắc truy cập Firebase
├── scripts/              # Công cụ kiểm tra contract
├── compose.yaml
└── .env.example
```

Đích triển khai backend vẫn là Docker trên **Google Cloud Run**. Firebase Auth/Firestore/Cloud Storage đã chốt. Model cụ thể và secrets môi trường phải cấu hình, kiểm thử khi triển khai; chưa có URL production được xác nhận.
