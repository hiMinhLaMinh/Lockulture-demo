# B — Firebase/private media handoff

**PARTIAL / live BLOCKED — chưa hoàn thành demo.**
Nhánh `demo60/infra` tạo từ `origin/main` tại `a3179a5` theo yêu cầu mới của người dùng; main đã chứa kế hoạch và phần B baseline. Commit gốc `dd69975afbce05c8bd58fac36e0ac143ace22673` là ancestor. Không merge/cherry-pick A/C, không push main. Mobile không bị sửa.
Code kiểm cuối: `a0d391a10ef9b2f32f05fe3b9babf73083c2b61c`; commit báo cáo sau đó không đổi artifact code.
Contract A đã đọc bằng `git show`: `12d65ec9f75180911056d22a6bbe9fb6489ff1de` (`origin/demo60/ai`, OpenAPI 1.1.0). Chưa có A_HANDOFF/runtime mission ở SHA đó.

## Mốc / bằng chứng

| Mục | Kết quả | Commit/lệnh và output |
| --- | --- | --- |
| Preflight live + startup | BLOCKED đúng cấu hình, chưa có provider call | `8b640de`; `backend/.venv/bin/python scripts/demo/preflight.py --live` exit 1, từng nhóm text/vision/image/maps BLOCKED; `scripts/demo/start.sh` exit 1 |
| Private adapters + env/start bàn giao sớm | PASS kiểm cú pháp, đã push | `8b640de`; compileall/bash -n exit 0; không có cloud image |
| F1 storage/restart | BLOCKED, chưa ghi cloud | `a99ebb5`; `scripts/smoke/smoke_firebase.py --phase storage` và `restart_firebase.py` exit 1 tại cloud preflight |
| Tests cuối | PASS unit/regression, không phải cloud | `a0d391a`; `backend/.venv/bin/python -m pytest backend/tests -q`: **44 passed, 22 skipped, 24 subtests passed**, 1 Starlette/anyio deprecation warning; exit 0 |
| Signed URL expiry/refresh | PASS test cô lập; cloud chưa chạy | `a0d391a`; smoke storage sẽ chờ URL hết hạn thật, kiểm HTTP 403 rồi Auth refresh/download; unit kiểm cả trường hợp URL hết hạn vẫn tải được phải fail |
| Compose / syntax | PASS | `docker compose config --quiet`, `bash -n scripts/demo/start.sh`, `python -m compileall -q backend/src/media scripts/demo scripts/smoke`, `git diff --check`: exit 0 |
| Contract validator | FAIL baseline ngoài B | `backend/.venv/bin/python scripts/contract/validate.py`: AssertionError `mobile/README.md` → `../legacy/flutter` không tồn tại; không sửa file C |
| Cloud F1, cloud/native E2E, restart worker/app | BLOCKED / NOT RUN | Chưa có ID asset/job/discovery cloud hợp lệ để báo; không seed XP/discovery để lấp bằng chứng |

22 skipped gồm các ca cần Emulator; không khởi chạy Emulator và không gọi đó là cloud production. Tests mới chỉ dùng doubles trong `backend/tests/`, không đi vào runtime. Đã cài công cụ kiểm thử vào `.venv` local: pytest 9.2.0, httpx 0.28.1, PyYAML 6.0.3, openapi-spec-validator 0.7.2. Không sửa requirements của A; media adapters dùng stdlib + Pillow/Firebase SDK đã có.

## Blocker xác minh trên máy

- `backend/.env`: **không có** GEMINI_API_KEY, GOOGLE_MAPS_API_KEY, GEMINI_MODEL, GEMINI_IMAGE_MODEL; root `.env` cũng không có key thật. Không đoán image model và không thể gọi provider khi thiếu key.
- GOOGLE_APPLICATION_CREDENTIALS đã đặt nhưng là đường dẫn tuyệt đối tới file **không tồn tại**; `backend/service-account.json` cũng chưa có. Không tự tạo credential/project cloud.
- FIREBASE_PROJECT_ID có; project nhóm hiển thị trước đó là `lockulture-f9c7d`. STORAGE_BUCKET thiếu; STORAGE_TYPE đang là **local**, không có Emulator host. Không tự đổi local sang firebase để báo PASS.
- Thiếu verified acceptance ID token, outsider token, ảnh bằng chứng/portrait được phép, consent, tọa độ thật và grounded place-context file. Không đọc database người dùng hàng loạt hay lấy token từ app.
- Chưa xác minh queue/OIDC/worker live. Baseline worker còn gọi fixture adapter; cấu hình gemini không biến baseline đó thành live worker. A phải tích hợp provider/job kind trước nghiệm thu.

## Modules để A tích hợp

Giữ đúng keyword-only signatures trong CONTRACT:

```python
from backend.src.media.storage import load_owned_image, put_private_image
from backend.src.media.souvenir import generate_souvenir, MediaProviderError

load_owned_image(*, actor_id: str, asset_id: str) -> bytes
put_private_image(*, object_path: str, image_bytes: bytes, mime_type: str) -> dict
generate_souvenir(*, evidence_images: list[bytes], portrait: bytes | None,
                  place_context: dict, timeout_s: float) -> tuple[bytes, str]
```

Trong package chạy bằng `src.main`, import tương ứng `src.media.*`.

- `load_owned_image`: owner/state check trước Storage; chỉ object path private, tải theo generation cố định, giới hạn bytes/pixels, kiểm decode/MIME/sha256. Outsider không tải bytes.
- `put_private_image`: MIME/decode/size/hash, upload create-only `if_generation_match=0`, không overwrite. Trả object_path/sha256/mime_type/byte_size/width/height; không ghi metadata asset/reward/ledger. `MediaStorageError` có message sạch.
- `generate_souvenir`: đúng một POST generateContent, explicit GEMINI_IMAGE_MODEL, không SDK retry/fallback/redirect mang key; bỏ arbitrary context fields, nhận `place_name`, `place_id`, `era_id`, `motif`, `summary`. Không nhận URL input. Từ chối response text-only/refusal/ảnh lỗi/ảnh giống bytes input; chỉ trả bytes decode được. HTTP error/timeout được đổi thành `MediaProviderError.code` provider_failed/deadline_exceeded, không lộ provider body/key/token.
- A phải xác minh consent + owner, bảo đảm có ảnh người dùng/portrait thích hợp, reserve image budget trước helper, giữ lease/checkpoint/job/outbox, theo dõi cleanup object thừa và attach metadata dưới lease còn hiệu lực. Helper không tự chứng minh ảnh có người; prompt yêu cầu model từ chối khi không thấy người, không bịa diện mạo.
- A truyền object path chứa job/lease riêng; không gọi model lại khi có checkpoint/asset và không tăng budget sau crash. Ảnh lỗi không hoàn tác thưởng.

## Chạy khi đã có cấu hình thật

Từ repo root, điền `backend/.env` theo `backend/.env.example` (ngoài Git). Dùng đường dẫn credential tuyệt đối, STORAGE_TYPE=firebase, bucket thật, ASSESSMENT_PROVIDER=gemini, model IDs được operator chọn và smoke. Điền queue/OIDC hiện có; không để secret trong mobile.

```bash
backend/.venv/bin/python scripts/demo/preflight.py --live
scripts/demo/start.sh
```

Preflight `--live` có thể gọi tối đa 1 request cho mỗi nhóm text/vision/image/maps; không retry. Ảnh preflight không lưu thành quà/discovery và không tái dùng cho lượt thưởng. Start không tự gọi provider để tránh lặp call. Compose cũng dùng `src.media.start` kiểm cấu hình trước HTTP; đã bỏ việc compose ghi đè keys bằng root env hoặc ép STORAGE_TYPE=local. Không sửa main.py; chạy uvicorn trực tiếp sẽ không đi qua demo startup checks này.

Cloud preflight đọc canon era, bucket-level IAM; F1 kiểm trực tiếp anon/authenticated rules, composite indexes deployed READY so với file repo, owner metadata, normalized JPEG hash và signed download. Không chứng minh mọi inherited IAM grant/ACL path; A/B vẫn phải rà IAM cấp project và nghiệp vụ.

### F1 storage trước rewards, tự restart API riêng

Trong backend/.env hoặc environment ngoài Git, cung cấp:

- SMOKE_ID_TOKEN: ID token Firebase account nghiệm thu đã verified.
- SMOKE_OTHER_ID_TOKEN: token verified của account khác để chứng minh outsider404.
- SMOKE_TEST_ACCOUNT_CONFIRMED=1, SMOKE_IMAGE_CONSENT=1.
- SMOKE_IMAGE_PATH: ảnh thật được phép; SMOKE_PLACE_CONTEXT_FILE: JSON tên/place_id/era/motif/summary đã đối chiếu nguồn, dùng cho image preflight.
- SMOKE_LATITUDE/SMOKE_LONGITUDE: vị trí thật cho Maps smoke, không log ra báo cáo.
- SMOKE_STATE_FILE: đường dẫn mới ngoài repo, ví dụ `/tmp/lockulture-f1-storage.json` (file 0600, không chứa token/URL/ảnh).

```bash
backend/.venv/bin/python scripts/smoke/restart_firebase.py --port 18080
```

Runner từ chối cổng đã dùng, chỉ tạo/dừng hai process API riêng mà nó sở hữu. Storage phase upload + replay cùng key → kiểm normalized hash/object/URL → chờ URL hết hạn thật (khoảng 60s), kiểm403 và refresh → kiểm rules/indexes/outsider → dừng API riêng → khởi động API mới → GET ảnh cũ và so hash. Không restart tiến trình backend hiện có, không gọi worker/provider, không tạo discovery/XP giả. Chạy local API với cloud persistence **không phải** kiểm deployment Cloud Tasks hoặc restart worker/app.

Manual phases (chỉ khi đã biết PID tiến trình API demo được phép restart):

```bash
backend/.venv/bin/python scripts/smoke/smoke_firebase.py --phase storage
# Sau khi người vận hành restart API demo, cập nhật SMOKE_BACKEND_PID:
backend/.venv/bin/python scripts/smoke/smoke_firebase.py --phase verify
```

State giữ PID + process starttime và verify từ chối cùng tiến trình/tiến trình cũ còn chạy. Entry point `scripts/demo/smoke_firebase.py` là alias theo tên kế hoạch.

### F1 completion sau A ghép

Sau một mission thật completed và ảnh souvenir succeeded: đặt SMOKE_DISCOVERY_ID, dùng SMOKE_STATE_FILE mới và chạy:

```bash
backend/.venv/bin/python scripts/smoke/restart_firebase.py --phase completion --port 18080
```

Script chỉ đọc record thật: mission/submission/discovery/ledger +100/badge/completion/souvenir job + purpose= souvenir, state=attached; đối chiếu celebration, nguồn có mặt, ảnh output khác input và owner ACL, rồi đọc lại sau restart API. Có nguồn trong snapshot không tự chứng minh chất lượng lịch sử; A phải giữ evidence đối chiếu nguồn. Không tự redeliver job để tạo dữ liệu; A kiểm replay/concurrent ledger/badge/job/call counters riêng. Không gọi storage smoke PASS là full F1/rewards PASS.

## Chỗ lệch / YÊU CẦU CHO NGƯỜI KHÁC

- **A:** contract SHA `12d65ec` và CONTRACT sprint60 vẫn dùng GET celebration + opt-in lúc submission, kind souvenir và queued/running/succeeded/failed. Chưa có POST `/missions/{mission_id}/rewards/cartoon`, enum pending/ready, SVG badge hoặc `rewards.build_reward`/`geo_ip.check`. Theo ưu tiên CONTRACT, B không invent route/schema hoặc kho thưởng thứ hai. Nếu cần các yêu cầu đó, A chốt contract/schema/examples/acceptance đồng bộ rồi bàn giao interface. SVG danh mục/claim địa danh chưa triển khai; không hardcode lịch sử thay nguồn thật.
- **A:** bổ sung worker live/job kind/reservation/checkpoint/atomic badge+souvenir+outbox và ceremony route; gọi helpers ở execution time. Baseline worker còn fixture; không báo live chỉ vì ASSESSMENT_PROVIDER đã đổi.
- **A:** startup hook dùng `media.config.live_errors` nếu cần chặn raw uvicorn/Cloud Run trực tiếp; B chỉ sửa entry point demo/Compose trong allowlist, không sửa main.py. Cấu hình Tasks/Scheduler và xác nhận worker restart/readback trên đúng artifact ghép.
- **A/C:** sửa link baseline `mobile/README.md` → `../legacy/flutter` để contract validator chạy toàn bộ. B không sửa mobile.
- **Owner project/B/operator:** cấp credential file đúng/ADC, bucket cloud private và billing khả dụng; cấu hình key, explicit model, queue/OIDC, token account nghiệm thu, ảnh có consent và context nguồn. Không gửi key/token/JSON lên chat/Git. Thiếu các đầu vào này thì live vẫn BLOCKED, ETA phụ thuộc cấp cấu hình.
- **C/người thử:** sau ghép kiểm ảnh thật trên điện thoại, app restart lấy URL mới; B không có device evidence và không sửa mobile.
- Prompt cho phép cắt ảnh ở phút45 khác CONTRACT bắt buộc ảnh để PASS: giữ tiêu chí CONTRACT, báo PARTIAL/BLOCKED thay vì cắt rồi nói hoàn thành.
- Sở hữu assets_routes/award và rewards/geo khác nhau giữa prompt và file role; câu “nếu file kế hoạch không ghi khác” + CONTRACT giữ ownership A. Không sửa các file đó, contracts, worker/missions hoặc mobile. `scripts/smoke/**` là bổ sung được yêu cầu trực tiếp ở lượt này.

Không có backup/restore evidence; không chạy export hoặc reset dữ liệu thật. Không public bucket, bypass Auth hay chuyển Emulator/local để lấp bằng chứng cloud. Khi chưa có pipeline ảnh có người → image model → private Storage → API → mobile và restart thật, toàn demo vẫn **chưa PASS**.

Nguồn API đã đối chiếu cho adapter/preflight: [Gemini generateContent](https://ai.google.dev/api/generate-content), [image generation/editing](https://ai.google.dev/gemini-api/docs/image-generation), [Places Nearby Search](https://developers.google.com/maps/documentation/places/web-service/nearby-search). Model ID phải do operator cung cấp/smoke, không suy từ tên Nano Banana.
