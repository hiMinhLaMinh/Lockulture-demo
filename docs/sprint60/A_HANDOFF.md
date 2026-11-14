# A handoff — mission, GPS, AI jobs

Ngày 14/11/2026. Nhánh `demo60/ai`; chỉ phạm vi A. Chưa ghép B/C, chưa deploy.

- PLAN_SHA: `c1e1738e2ac73a85fc5917d6a866ded09e7cb282` (local remote-tracking baseline; người dùng xác nhận được tạo nhánh từ SHA này khi fetch bị chặn).
- Contract SHA: `12d65ec9f75180911056d22a6bbe9fb6489ff1de` — đã push riêng trước runtime.
- Runtime/tests SHA: `4083a2efc94bbfa23ccc112be103429d4340df52`.
- Commit chứa tài liệu này là handoff tip; code artifact vẫn là runtime SHA ở trên.
- Ancestor `dd69975afbce05c8bd58fac36e0ac143ace22673` đã kiểm. Không worktree, agent phụ, merge B/C hoặc push main.

## Đã triển khai

Sáu operation mission dùng Firebase Auth/owner, search job/outbox, quota và idempotency,
active search/mission CAS; hints/answer không gọi provider. Search dùng Places REST và
Gemini JSON, counters trước call, checkpoint dưới lease, lọc radius/candidate/era trên
server. `no_result` giữ mission cũ. Catalog 10 era của baseline được giữ nguyên.

Submission nhận GPS mới và consent/portrait; gate 150m/50m/60s/+5s tại intake,
snapshot gắn asset/submission/mission-version/config. Worker recheck snapshot theo
thời điểm intake trước vision và trước thưởng, không coi inference lâu là GPS stale.
Free vẫn +20, mission +100, mảnh cap3. Vision dùng ảnh bytes cùng session, criteria
mission và previous instruction; output validate bằng schema cũ, budget1.

Completion transaction ghi discovery/ledger/progress, mission completed, badge UUID
xác định, completion, và optional souvenir job/outbox. Reads-before-writes được kiểm
bằng double và Emulator. Claim/recovery phân loại submission/mission_search/souvenir;
job cũ không có kind được hiểu là submission. SDK contention hết retry được chuyển
thành lỗi hạ tầng 503 để queue redeliver, không gắn nhãn provider failure.

Souvenir reserve image1/job; gọi helper B ngoài transaction, upload path chứa job/lease,
track orphan trong asset_uploads, checkpoint/finalize dưới lease. Ảnh thất bại giữ
thưởng/badge. Completion GET owner-only; asset private attached, URL qua API hiện có.

## B/C cần nối

B cung cấp đúng keyword-only interfaces trong CONTRACT, không cần đổi signature:

```python
load_owned_image(*, actor_id: str, asset_id: str) -> bytes
put_private_image(*, object_path: str, image_bytes: bytes, mime_type: str) -> dict
generate_souvenir(*, evidence_images: list[bytes], portrait: bytes | None,
                  place_context: dict, timeout_s: float) -> tuple[bytes, str]
```

`place_context`: name, place_id, era_id, motif, summary. B chịu kiểm ảnh có người/consent,
không bịa ngoại hình, request image model đúng một lần, timeout <=60s, trả bytes mới.
Storage helper phải trả đúng object_path đã nhận và metadata theo CONTRACT. A chỉ import
helper lúc execution; thiếu helper ra job failed, không fallback fixture. B gửi dependency
nếu cần; A chưa thêm dependency vì REST dùng standard library.

C đọc contract tại SHA trên hoặc handoff tip: gửi capture_location ở mọi submission
mission, giữ idempotency key khi retry mạng, rồi poll celebration sau completed. Lấy
ảnh từ souvenir.asset_id qua signed URL mới. Không tự cộng XP hoặc fake ảnh quà.

## Cấu hình live và dữ liệu nguồn

Server cần ASSESSMENT_PROVIDER=gemini, GEMINI_API_KEY, GEMINI_MODEL,
GOOGLE_MAPS_API_KEY; B cung cấp GEMINI_IMAGE_MODEL, Firebase project/private bucket,
ADC, STORAGE_TYPE=firebase và queue/OIDC hoặc runner demo theo kế hoạch.

Thêm `MISSION_SOURCE_CONTEXT_FILE`: đường dẫn server-local tới JSON array do operator
đối chiếu nguồn thật. Mỗi record có:

- place_id thật lấy từ Places; verified=true sau đối chiếu.
- era_id canonical phù hợp niên đại công trình; summary, fun_facts (list không rỗng), motif.
- sources: list không rỗng gồm title và HTTPS url nguồn quản lý/bảo tàng/du lịch đã xác minh.

Không có nguồn mẫu live được bundle. Không fetch URL từ client/model. Thiếu/không hợp lệ
thì search preflight trả503; candidate không có source snapshot phù hợp không được chọn.
Cần nhóm xác nhận địa điểm gần người thử rồi cung cấp snapshot này trước live smoke.

## Kiểm thử

Môi trường thực tế: Python 3.11, dependencies backend có sẵn ở
`/tmp/lockulture-phase-b-deps`, pytest/validator ở `/tmp/lockulture-merge-venv`.
Không gọi provider live trong tests.

```sh
/tmp/lockulture-merge-venv/bin/python scripts/contract/validate.py
PYTHONPATH=/tmp/lockulture-phase-b-deps ENV=test \
  /tmp/lockulture-merge-venv/bin/python -m pytest backend/tests -q
```

- Contract PASS: 44 operations, 44 HTTP + 7 AI examples, 40 acceptance cases.
- Không Emulator: 58 passed, 23 skipped (Emulator và các suite cần backend tương ứng).
- Emulator regression tại runtime SHA: **81 passed, 0 skipped**, 33.62s, hai warning
  deprecation/Firestore positional filter; exit0. Project demo-lockulture-a; cấu hình
  tạm ở /tmp/lockulture-a-firebase.json, port Firestore18081/Auth19099/Storage19199,
  hub14400/logging14500/websocket19150. Cổng8081 đã bận nên không dùng/dừng service đó.
- git diff --check PASS; diff với PLAN_SHA chỉ thuộc allowlist A.

Lệnh Emulator thực tế (chạy từ /tmp để logs không vào repo):

```sh
/tmp/lockulture-phase-b-tools/node_modules/.bin/firebase emulators:exec \
  --config /tmp/lockulture-a-firebase.json --project demo-lockulture-a \
  --only firestore,auth,storage \
  'cd /Users/vohoangminh/Mini_hackathon_2026/Lockulture && PYTHONPATH=/tmp/lockulture-phase-b-deps ENV=test FIREBASE_PROJECT_ID=demo-lockulture-a /tmp/lockulture-merge-venv/bin/python -m pytest backend/tests -q'
```

Các ca A gồm GPS invalid/biên/time, reject intake không ghi dữ liệu, exact mission/version,
wrong photo, một mission inflight, reward concurrency, stale lease, crash-budget,
checkpoint không gọi lại provider, souvenir refusal/timeout/Storage failure, ACL,
search thật về mặt orchestration với provider doubles, source validation, hints CAS,
no_result và completion transaction trên Firestore Emulator. Cloud Tasks delivery
đồng thời được mô phỏng bằng threads + redelivery khi hạ tầng trả lỗi retryable.

## Giới hạn và yêu cầu owner

- Chưa chạy Places/Gemini text/vision hoặc Nano Banana live; chưa có model/call latency
  thực, địa điểm/ảnh được đồng ý và source snapshot được nhóm xác nhận.
- Chưa có helper B trong nhánh A; chưa xác minh private cloud Storage, signed URL expiry,
  restart/read-back cloud, Cloud Tasks deployment hoặc native GPS/camera/animation C.
  Emulator pass không chứng minh các mục này; full demo vẫn PARTIAL/BLOCKED.
- GET /api/v1/health của baseline vẫn báo contract_version=1.0.0 (route/test nằm ngoài
  allowlist A); OpenAPI info và config là1.1.0. YÊU CẦU OWNER: đồng bộ marker health và
  test khi tích hợp; hiện không dùng marker đó để kết luận artifact hỗ trợ sprint60.
- Mission cũ thiếu heritage/badge phải search mới. Drain inflight cũ trước đổi phiên bản;
  submission cũ thiếu GPS snapshot không được thưởng mission theo luật mới. Không tự
  migrate/reset dữ liệu thật hoặc đổi catalog để demo.
- COMMON_PROMPT/CONTRACT/PLAN/PUBLISH, mobile, Firebase helpers, media, environment.example,
  CURRENT_STATE và EVIDENCE không bị sửa. Nhánh integration và live evidence là bước sau.
