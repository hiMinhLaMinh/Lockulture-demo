# Hợp đồng duy nhất — sprint60

Thiết kế đầu vào để A triển khai; không mô tả API đã chạy. A là owner OpenAPI/schema/examples/acceptance, B/C chỉ đọc. Chốt bản contract trước phút 8; từ đó thay đổi cần báo cả nhóm và cập nhật đồng bộ. Giữ enum/field hiện có nếu không liệt kê thay đổi ở đây.

## 1. Nguyên tắc

- FastAPI kiểm Firebase ID token và owner; mobile chỉ dùng Firebase SDK cho Auth. Giữ phiên đã có, không thêm giao diện Auth hay bypass backend.
- Public API `/api/v1`; resource IDs là UUID nội bộ. Mutation dùng `Idempotency-Key` UUID, cùng intent/network retry giữ key; body khác dùng key mới. Refresh token 401 một lần giữ key.
- HTTP error envelope và `ErrorDetail` trong job/resource theo API_RULES; không đặt `error.error`. Job terminal failed được GET HTTP 200 với error, không giả lỗi transport.
- No fixture fallback trong demo live. Unit/Emulator tests được dùng doubles rõ ràng. Cloud smoke phải xác nhận cloud và không trộn Emulator/local.
- A cập nhật version contract/config phù hợp (dự kiến 1.1.0) cho GPS, badge và souvenir; không đổi luật thưởng cũ ngoài việc mission yêu cầu GPS mới. Không tự tăng budget vision từ 1 lên 2 như prompt90 cũ.

## 2. Nhiệm vụ và kiến thức

Triển khai sáu operation đã có trong `contracts/openapi.yaml`: `startMissionSearch`, `getMissionSearch`, `getActiveMission`, `getMission`, `revealHint`, `revealAnswer`. Không đổi tên path hoặc tạo backend thứ hai. Job search phải hoạt động qua outbox/lease/recovery như submission, không gọi model trong request rồi giả job.

`POST /mission-searches` trả 202 Job; poll GET job, succeeded lấy `resource_id` để GET Mission. `no_result` giữ mission cũ; active mission chưa có trả 200 null. Một search inflight/actor; hints/answer dùng dữ liệu đã sinh, không gọi model thêm. Giữ active mission/version và CAS khi đổi/hoàn thành; không replace nhiệm vụ đang đánh giá.

Giữ Mission hiện có và thêm:

- `arrival_radius_m: integer` (mặc định 150, do server/config cấp, client không chọn).
- `badge_design: {title: string, motif: string, era_id: EraId}`: motif có căn cứ từ địa điểm/nguồn, UI dựng huy hiệu; không nhận XP/badge từ model làm quyền thưởng.
- `heritage: {summary: string, fun_facts: string[], era_id: EraId, sources: [{title: string, url: string}]}`. Ít nhất một nguồn được đối chiếu cho claim lịch sử; không xem Places address là nguồn lịch sử. Lưu snapshot nguồn đã rà để UI không phải scrape.

A tra nguồn du lịch chính thức/bảo tàng/đơn vị quản lý phù hợp địa điểm trong preflight và cung cấp context thật cho Gemini. Không để model tự bịa URL/năm/triều đại; fetch nguồn chỉ qua danh sách URL/host do operator xác minh, không tải URL tuỳ ý từ client/model. Nếu nguồn không xác nhận được claim thì bỏ claim hoặc no_result khi không đủ nhiệm vụ hợp lệ.

Search <=2 Maps và <=3 Gemini, reserve trước call; lấy candidate có place ID từ Places, đo khoảng cách server theo radius search hiện hành, không phát hành địa điểm ngoài danh sách/era filter. Model tạo clue, ba hints và photo_requirements đúng candidate. Địa danh hiện đại dùng era hiện đại/đương đại đúng catalog, không ép triều đại cổ.

## 3. Submission, GPS và ảnh

Giữ nguyên sáu field SubmissionInput hiện tại, thêm:

```text
capture_location: null | {
  latitude: number [-90,90], longitude: number [-180,180],
  accuracy_m: finite number >=0,
  captured_at: ISO-8601 UTC,
  source: "gps"
}
souvenir_opt_in: boolean          # mặc định false, demo đầy đủ chọn true
portrait_asset_id: UUID | null    # ảnh chân dung phụ khi ảnh cảnh không có người
```

Mode mission bắt buộc capture_location; free cho phép null và không có location gate mới. Portrait phải là asset ready của cùng owner; không thay asset bằng chứng mission và không tự tạo discovery/XP. Người dùng đồng ý tạo ảnh trước upload chân dung/gửi model. Nếu ảnh bằng chứng đã có người dùng thì dùng ảnh đó, không cần portrait phụ. Không bịa ngoại hình khi cả hai đều không có người; yêu cầu ảnh thích hợp, không báo đủ tiêu chí ảnh chân dung.

Mobile lấy GPS mới khi chụp/nộp ảnh; không dùng location của search hay tọa độ nhập tay làm mẫu arrival. Server kiểm tại intake: finite/range, `accuracy_m <= 50`, timestamp không cũ quá 60 giây và không tương lai quá 5 giây. Server tự đo Haversine tới toạ độ mission authoritative, gate `distance_m <= arrival_radius_m`. Giá trị 150/50/60/5 là cấu hình được A version hóa và thêm acceptance biên.

Outside radius trả 409 `location_out_of_range`; mẫu thiếu/kém chính xác/cũ trả 422 `validation_error` với thông điệp có thể khắc phục. Không gọi vision/không thưởng nếu intake fail. Mẫu hợp lệ được gắn bất biến vào submission/asset/mission-version; worker kiểm snapshot gate + version, không đo lại tuổi mẫu theo lúc model hoàn thành.

GPS check chỉ xác nhận tính nhất quán của mẫu vị trí client khai, không chống giả GPS hoặc chứng minh tuyệt đối hiện diện. IP không phải gate: nếu có nguồn IP đáng tin từ proxy được cấu hình, có thể ghi tín hiệu khu vực/unknown; không tin X-Forwarded-For tùy ý, không dùng IP Cloud Run/máy backend làm IP điện thoại. Không tích hợp thêm dịch vụ IP nếu không có sẵn.

Vision giữ schema `mission-assessment.schema.json` hiện hành và `free-assessment.schema.json`, không thêm confidence/coordinates/badge/image vào JSON model. Mission completed chỉ khi ảnh khớp photo_requirements của địa danh + location gate pass + mission/version còn hiệu lực. Ảnh mờ→retake_required, không rõ→unidentified, sai công trình→not_matched; không nhận một cây cầu bất kỳ là Cầu Rồng. 1 vision call/submission, tối đa4 bằng chứng/session như baseline.

Submission DTO thêm `location_check: null | {within_radius: boolean, distance_m: number, radius_m: integer, accuracy_m: number, checked_at: ISO-UTC}`. Không cần thêm tool_status/stage mới cho submission trong timebox; dùng status hiện có và Job trạng thái thật cho ảnh quà.

## 4. Atomic completion, badge và job ảnh quà

A mở rộng result writer hiện có, không viết kho XP thứ hai. Trong cùng transaction completion: đọc đủ job lease/session/mission/discovery/ledger/profile/progress và reservation badge/souvenir trước mọi write; sau đó ghi discovery, ledger/XP/mảnh, completed mission, earned_badge, completion và (nếu opt-in) souvenir job + outbox. Không network trong transaction, không ghi Firestore rồi mới cố enqueue ngoài transaction làm mất job.

- `earned_badges`: owner, mission_id, place_id, title, motif, era_id, earned_at. Badge resource UUID xác định theo owner+mission; retry không tạo badge mới. Không có XP riêng cho badge/ảnh quà.
- `mission_completions/{discovery_id}`: owner, mission_id, badge_id, heritage snapshot, souvenir_job_id|null, portrait/evidence asset refs và consent. Giữ UUID resource cho HTTP.
- Souvenir job ID UUID xác định theo completion; `kind="souvenir"`, owner_id, discovery_id, counters/lease/checkpoint/deadline. Reservation 1image call/job; outbox/generation và OIDC giữ nguyên. Claim/dispatch/recovery phải phân loại job; không giả định mọi job đều có submission/session như worker hiện tại.
- Có checkpoint/asset thành công thì chỉ finalize, không gọi model lại. Crash sau image call trước checkpoint mà budget đã hết thì failed trung thực, không reset counter. Ảnh lỗi không hoàn tác XP/badge đã commit; ghi trạng thái ảnh lỗi nhưng toàn demo vẫn chưa PASS.
- Output upload vào private Storage trước, dùng object path chứa job/lease để worker cũ không ghi đè object của lease mới; persist metadata/attach asset chỉ dưới lease hợp lệ. Object thừa phải được theo dõi cleanup, không công khai. Asset ảnh quà `purpose="souvenir"`, state attached, owner và discovery link; không bị cleanup orphan24h quét nhầm.

Endpoint mới duy nhất để mobile đọc quà/kiến thức/huy hiệu:

```text
GET /discoveries/{discovery_id}/celebration -> 200 (owner-only)
{
  discovery_id: UUID,
  badge: {id: UUID, title: string, motif: string, era_id: EraId, earned_at: ISO-UTC},
  heritage: {summary: string, fun_facts: string[], era_id: EraId,
             sources: [{title: string, url: string}]},
  souvenir: {
    job_id: UUID|null,
    status: "not_requested"|"queued"|"running"|"succeeded"|"failed",
    asset_id: UUID|null,
    error: ErrorDetail|null
  }
}
```

Owner khác/không có completion trả404; GET không tạo job/provider call. Asset succeeded dùng GET `/assets/{asset_id}/url` hiện có, ký60s sau Auth/ACL, không trả image base64 hay public download URL. Mở lại app lấy completion và URL mới, không phụ thuộc cache URI.

## 5. A ↔ B: interface Python chốt trước phút 8

B tạo modules mới, giữ signature sau; A import ở execution time để nhánh A có thể chạy contract tests trước khi nhận B.

```python
# backend/src/media/storage.py — B
def load_owned_image(*, actor_id: str, asset_id: str) -> bytes: ...
def put_private_image(*, object_path: str, image_bytes: bytes,
                      mime_type: str) -> dict: ...

# backend/src/media/souvenir.py — B
def generate_souvenir(*, evidence_images: list[bytes], portrait: bytes | None,
                      place_context: dict, timeout_s: float) -> tuple[bytes, str]: ...
class MediaProviderError(Exception): ...
```

- `load_owned_image` kiểm owner + asset state, đọc bytes JPEG thật bằng Firebase Admin; không nhận URL tuỳ ý. Không log bytes/tokens.
- `put_private_image` chỉ upload/kiểm ảnh và trả object_path, sha256, mime_type, byte_size, width,height; A ghi metadata asset/attach/lease. Không ghi ledger/badge trong helper B.
- `generate_souvenir` đúng một request tới image model thực tế qua `GEMINI_IMAGE_MODEL`; không SDK retry ngầm/fallback. Trả bytes ảnh mới + MIME hợp lệ, không trả ảnh input hay text URL làm success. Gặp safety refusal/không image parts/timeout thì raise lỗi đã bỏ secrets.
- `MediaProviderError` có `code` (`provider_failed` hoặc `deadline_exceeded`) và message an toàn. A quyết định retryability từ budget/checkpoint/deadline, không để exception tự tạo thưởng.
- A reserve image_calls trước invocation dưới lease. Timeout provider <=60s, job deadline600s/attempt<=3 theo baseline; image job khác submission job nên không ăn vision budget. Không gọi song song hai image jobs cho cùng completion.
- `place_context` chứa tên/place_id/era/motif/summary có căn cứ, không arbitrary prompt từ client. Prompt ảnh giữ người và đặc điểm địa danh, hoạt hoạ vui tươi; không tự thêm nhân vật nếu thiếu ảnh người. Cảnh do AI tạo ghi rõ là ảnh minh hoạ.

Backend config: `ASSESSMENT_PROVIDER=gemini`, `GEMINI_API_KEY`, `GEMINI_MODEL` (vision/text), `GEMINI_IMAGE_MODEL` (image editing), `GOOGLE_MAPS_API_KEY`, `FIREBASE_PROJECT_ID`, `STORAGE_TYPE=firebase`, `STORAGE_BUCKET`, env queue/OIDC hiện có nếu dùng Tasks. Secrets chỉ server/Secret Manager; public Expo chỉ Firebase app config + HTTPS/LAN API URL.

B đề nghị dependency/version cho A, A duy nhất sửa `backend/requirements.txt`. B không sửa worker để gọi helper của mình, A không sửa helper B để chữa mismatch; gửi reproduction/owner giải quyết.

## 6. Điều kiện nghiệm thu mới A phải thêm

- Mission mới: source/location/era/candidate hợp lệ, hints không gọi provider lại, no_result giữ mission cũ.
- GPS: thiếu, stale, future, null accuracy, NaN/Infinity, ngoài150m, đúng biên, accuracy>50, tọa độ nhập tay không thay sample arrival; không thưởng trong các ca fail.
- Vision: đúng địa điểm/khác công trình/ảnh mờ; đúng GPS nhưng ảnh sai vẫn fail; ảnh đúng nhưng GPS sai vẫn fail.
- Transaction: duplicate delivery/replay/concurrent completion tạo đúng1 discovery/ledger/badge/souvenir job/outbox; worker lease cũ không finalize; không vi phạm Firestore reads-before-writes.
- Image: request thật trả ảnh mới, refusal/timeout/bytes lỗi/Storage lỗi ra failed rõ; checkpoint recovery không gọi lại; không image call thứ hai sau crash khi đã dùng budget.
- Persistence/ACL: app/backend restart đọc completion và cả hai assets cloud; signed URL TTL/refresh; outsider404; souvenir attached không bị orphan cleanup.
- Native UI: animation sau completion server, reduced motion, giữ ảnh khi lỗi, không fake progress, mất mạng không tự POST mới, ảnh quà bắt buộc để full demo PASS.
