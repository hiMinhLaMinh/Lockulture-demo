# Máy A — Backend/AI, contract và ghép cuối

Dán [COMMON_PROMPT.md](COMMON_PROMPT.md) trước nội dung dưới; hoặc yêu cầu Antigravity đọc cả hai file trước khi thực hiện.

```text
VAI TRÒ A. Nhánh demo60/ai. Bạn sở hữu backend nghiệp vụ, contract và integration.
60phút gồm cả ghép/nghiệm thu; không dùng toàn bộ giờ để viết thêm feature.
Ảnh Nano Banana là tiêu chí bắt buộc như mission/GPS/badge, không được cắt bỏ.

ALLOWLIST:
backend/src/main.py
backend/src/jobs.py
backend/src/award.py
backend/src/assets_routes.py
backend/src/worker/**
backend/src/missions/** (mới)
backend/requirements.txt
contracts/** TRỪ contracts/environment.example (B sở hữu)
docs/implementation/{DECISIONS,AI_JOBS,API_RULES,DATA_TRANSACTIONS,ACCEPTANCE,TASKS}.md
backend/tests/test_demo60_mission.py (mới)
backend/tests/test_demo60_jobs.py (mới)
docs/sprint60/A_HANDOFF.md (mới)
Chỉ trên integration, sau có bằng chứng runtime:
docs/CURRENT_STATE.md, docs/sprint60/EVIDENCE.md (mới).

CẤM sửa mobile/, Firebase/Auth/Storage helper B, backend/src/media/, tests B/C,
contracts/environment.example, tài liệu kế hoạch sprint60 và mọi file ngoài allowlist.
Không sửa helpers B để né interface; báo reproduction cho B.

0–5 PHÚT: KIỂM ĐIỂM NGHẼN
- Đọc code thật. main.py đã include routers; jobs.py intake đang fixture-only;
  worker/http.py claim/process_delivery/recover đang giả định submission/session.
  Sáu mission endpoints trong OpenAPI chưa có runtime; phải triển khai, không chỉ
  nối mobile vào route tưởng đã tồn tại. award_result hiện tại giữ XP/mảnh.
- Smoke Places và Gemini text/vision với key server. B chịu image model/cloud.
  Chọn một địa điểm thật gần điện thoại C; không mặc định Cầu Rồng nếu không ai ở đó.
- Đối chiếu nguồn du lịch chính thức/đơn vị quản lý/bảo tàng phù hợp địa điểm;
  cung cấp source context thật cho model tạo câu đố, fun fact và era/motif.

5–8 PHÚT: HỢP ĐỒNG ĐI TRƯỚC
- Chuyển docs/sprint60/CONTRACT.md thành OpenAPI/DTO/schema/examples/acceptance và
  config/version; cập nhật docs luật mission GPS thay quyết định cũ có chủ ý.
- Thêm capture_location, souvenir_opt_in, portrait_asset_id, location_check;
  Mission arrival_radius_m/badge_design/heritage; endpoint celebration như hợp đồng.
- Giữ JSON model free/mission assessment hiện có, vision budget1. Thêm image budget1
  ở job souvenir riêng, không dùng GEMINI_FALLBACK_MODEL hay retry ngầm.
- Commit riêng phần contract, chạy validator bằng Python có jsonschema/yaml phù hợp,
  push demo60/ai; gửi B/C SHA contract. Không đợi backend xong mới công bố DTO.

8–25 PHÚT: MISSION + VISION + GPS
- Triển khai sáu operation đã có, base /api/v1. Search POST202/job/outbox, GET job,
  mission active/null, mission detail, hints và answer không gọi model thêm.
- Giữ idempotency/quota/inflight/active mission CAS. No_result không xóa mission cũ.
  Search worker dùng lease/checkpoint/budget <=2Maps/3Gemini, kiểm place candidate,
  distance và era filter. Không sinh tọa độ/năm/triều đại từ trí tưởng tượng.
- Backend Google Places Text Search field mask tối thiểu; lọc radius server.
  Model vision nhận ảnh bytes thật qua B load_owned_image, criteria mission thật,
  bằng chứng cùng session, instruction trước. Schema validate trước checkpoint.
- GPS gate tại intake: native sample hợp lệ, <=150m, accuracy<=50m, age<=60s,
  future<=5s. Tọa độ mission server; ngoài vùng không gọi vision/không thưởng.
  Persist location snapshot; worker recheck snapshot/version, không coi inference
  lâu là GPS lúc intake hết hạn. Không khẳng định chống giả GPS/hiện diện tuyệt đối.
- Gỡ gate fixture-only và thay provider đúng nhánh live. Preflight fail rõ khi key
  thiếu/provider không đúng; đừng khóa import/test fixtures của regression unit tests.

25–35 PHÚT: HOÀN THÀNH + HUY HIỆU + JOB ẢNH QUÀ
- Mở rộng award_result hiện có, đọc đủ tài liệu trước mọi write. Completed cần
  vision completed + GPS pass + mission/version active + lease/deadline hợp lệ.
- Cùng transaction: discovery/ledger/+100/mảnh/mission completed, badge UUID xác
  định, mission_completions và souvenir job/outbox nếu opt-in. Idempotent replay
  và concurrent completion không tạo thưởng/job mới. Badge không thêm XP.
- Worker phân loại submission/search/souvenir, recovery/counters/quota theo kind;
  không để image job truy cập job['submission_id'] hay session không tồn tại.
- Reserve call trước network dưới lease, vision1/submission, image1/souvenir job.
  A gọi B generate_souvenir rồi put_private_image ngoài transaction; checkpoint
  và publish asset/celebration metadata chỉ dưới lease hiện hành. Object chứa
  job+lease để tránh ghi đè, orphan được theo dõi. Không public ảnh.
- GET /discoveries/{id}/celebration owner-only, không sinh job khi GET. URL ảnh
  qua /assets/{id}/url; asset attached/purpose souvenir không bị cleanup nhầm.
- B báo dependency để bạn thêm requirements một nơi duy nhất. Import media helper
  lúc execution để contract/tests không cần nhánh B ngay từ đầu.
- Thêm tests cần thiết cho geofence, wrong-photo, retry/concurrency, lease cũ,
  loại job mới, image refusal/timeout/crash-budget. Doubles chỉ trong test.
- Push SHA bàn giao cùng A_HANDOFF trước phút35; ghi tests pass/fail/skipped.

35–45 PHÚT: GHÉP TRÊN MÁY A
- Working tree sạch, fetch origin demo60/ai, demo60/infra, demo60/mobile.
  Đối chiếu SHA handoff/allowlist/baseline, không merge phần chưa bàn giao.
- Tạo demo60/integration từ đúng SHA origin/demo90/plan chứa sprint60.
  Merge --no-ff lần lượt AI_SHA → INFRA_SHA → MOBILE_SHA. Không đụng main.
- Conflict: abort merge, owner sửa nhánh mình/push, bạn fetch lại; không ours/theirs
  toàn file, không cùng sửa với owner. Lỗi API/import/script cũng gửi đúng owner.
- Contract validator, tests backend phù hợp và regression/Emulator; mobile typecheck/
  lint do C cung cấp rồi kiểm bản ghép. Start/preflight B, không dựng cloud mới.

45–60 PHÚT: TOÀN LUỒNG VÀ CHỐT
- Native GPS→Places→mission→ảnh đúng→completion→badge/animation→ảnh Nano Banana mới
  thật sự về mobile. Kiểm ảnh sai/GPS sai, retry không thêm reward/image call.
- B xác minh Firestore/Storage cloud và restart read-back; C mở lại completion để
  thấy ảnh quà qua URL mới. Có ảnh sinh trước preflight không thay ảnh của lượt demo.
- Ghi EVIDENCE với SHA nguồn/integration, model/call count/latency, project/bucket,
  lệnh/kết quả đã che secrets và ca chưa kiểm. Cập nhật CURRENT_STATE theo bằng chứng.
- Push chỉ demo60/integration khi reviewable và ghi trạng thái thật, không main.
  Nhánh feature chỉ push demo60/ai. Deploy chỉ môi trường staging/demo có sẵn được
  nhóm thống nhất; không tự mở production hoặc xóa dữ liệu để thử lại.

XONG KHI: đủ cả mission/GPS/vision/badge/kiến thức/animation/ảnh quà cloud mới và
read-back sau restart; checks có bằng chứng. Thiếu ảnh quà hoặc tới nơi chưa thật
thì PARTIAL/BLOCKED, không tuyên bố thành công trong60phút.
```
