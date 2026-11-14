# Bàn giao Giai đoạn A

[Phân công](../TEAM_WORK_PLAN.md) · [OpenAPI](../../contracts/openapi.yaml) · [Hiện trạng](../CURRENT_STATE.md)

## Chạy từ thư mục gốc

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements.txt -r scripts/contract/requirements.txt httpx
ENV=development LOCKULTURE_SOCIAL_FIXTURES=1 \
  python -m uvicorn backend.src.main:app --host 127.0.0.1 --port 8080
```

Chạy một worker. Khởi động lại backend để reset bạn bè, nhóm, bài, bình luận và khóa idempotency. Phiên bản dev lấy danh tính và một discovery của A từ contract. A có sẵn B/C trong danh sách bạn bè và nhóm mẫu có A/B. Các tài khoản B/C/D có bộ sưu tập rỗng, phù hợp để kiểm tra quyền nhận bài.

Dùng Node 24.3 trở lên trong nhánh 24 và npm 11. Chạy Expo từ terminal khác.

```sh
cd mobile
npm ci
EXPO_PUBLIC_DATA_SOURCE=api EXPO_PUBLIC_SOCIAL_FIXTURES=1 \
  EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8080/api/v1 npm run web
```

Chọn A/B/C/D trên màn hình đăng nhập. Đổi tài khoản từ Hồ sơ. Các token dev dạng `lockulture-dev-A` chỉ được bộ xác thực fixture chấp nhận. Backend từ chối khởi động với fixture ở ngoài môi trường development/test. Web dev cho phép CORS từ localhost và 127.0.0.1. Nếu chạy simulator hoặc thiết bị, đặt API base URL theo địa chỉ mà thiết bị truy cập được.

## Endpoint

| Nhóm | Endpoint dưới `/api/v1` |
|---|---|
| Health, hồ sơ, khám phá và hạng fixture | GET `/health`, `/me`, `/discoveries`, `/discoveries/{discovery_id}`, `/leaderboard` |
| Bạn bè và lời mời | GET `/users`, `/users/{user_id}`, `/friends`, `/friend-requests`; POST `/friend-requests`; PATCH `/friend-requests/{request_id}`; DELETE `/friends/{user_id}` |
| Nhóm | GET/POST `/groups`; GET/PATCH/DELETE `/groups/{group_id}`; GET/POST `/groups/{group_id}/members`; DELETE `/groups/{group_id}/members/{user_id}` |
| Bài, feed và ảnh | GET/POST `/posts`; GET/DELETE `/posts/{post_id}`; POST `/posts/{post_id}/shares`; GET `/assets/{asset_id}/url` |
| Tương tác | PUT/DELETE `/posts/{post_id}/reaction`; GET/POST `/posts/{post_id}/comments`; DELETE `/comments/{comment_id}` |

Mọi mutation yêu cầu header `Idempotency-Key` dạng UUID. `GET /health` ngoài prefix vẫn dùng payload cũ.

## Interface cho thành viên 3

- `ActorResolver.resolve(token)` trả UUID nội bộ từ bearer token. `DiscoveryReader` cung cấp discovery của owner, danh sách của owner và owner của asset. `AssetUrlIssuer.issue(asset_id, expires_at)` cấp URL sau bước kiểm quyền. Adapter dev dùng ảnh SVG và URL có chữ ký hết hạn trên backend dev.
- `SocialRepository.read(operation)` đọc nhất quán. `atomic(operation)` thực thi một nghiệp vụ với cùng transaction, gồm cả bản ghi idempotency. Callback có thể chạy lại và phải tránh side effect ngoài lưu trữ. Adapter Firestore cần buffer ghi để các lần đọc trong callback đi trước commit. Các thao tác trên discovery/asset trong publish là đọc dữ liệu đã hoàn tất. Khi ghép với B, kiểm tra invariant owner và trạng thái asset trong cùng transaction nếu dữ liệu có thể thay đổi đồng thời.
- Adapter bộ nhớ quét tập dữ liệu dev. Khi làm Firestore, rà lại truy vấn theo actor, snapshot membership, phân trang và contention trước khi chốt indexes. Nếu cần đổi interface để đáp ứng truy vấn, giữ contract HTTP và chạy lại cùng bộ test. Thay fixture `services` trong test HTTP để dùng adapter khác.
- GET discovery, hồ sơ cá nhân và leaderboard hiện lấy từ seed. Giai đoạn B nối hồ sơ, discovery, XP ledger, Firebase Auth, Storage và Firestore thật. Giai đoạn C nối nhiệm vụ và AI.

## Kiểm thử

```sh
python -m pytest -q backend/tests
python scripts/contract/validate.py
cd mobile && npm run check
```

- Pytest pass 12 bài kiểm HTTP, gồm quyền, snapshot, rollback, replay, validation, phân trang, payload theo contract và tranh chấp giới hạn thành viên trong một tiến trình. Starlette phát cảnh báo deprecation cho HTTPX TestClient.
- Contract validator pass 43 operations, 41 ví dụ HTTP, 7 ví dụ AI và 36 kịch bản acceptance. Đây là kiểm tra tính nhất quán của pack.
- TypeScript/lint pass trên Node 24.22.2. Expo export JS bundle Android và iOS pass.
- Smoke Chromium với Expo web và FastAPI dev pass. A đăng từ bộ sưu tập cho B, B nhận bài và đổi cảm xúc, C không thấy bài trong feed, D nhận 404 qua HTTP. Với lần gửi bình luận có phản hồi bị ngắt sau commit, thao tác thử lại gửi cùng key, GET xác nhận một bản ghi, sau đó B xóa được bình luận.

Emulator, staging, thiết bị vật lý và độ bền nhiều worker cần kiểm thử ở mốc sau. Mốc code để thành viên 3 rà là `72c919e` trên branch `codex/phase-a-social`.
