# Máy B — Firebase, Nano Banana và smoke persistence

Dán [COMMON_PROMPT.md](COMMON_PROMPT.md) trước nội dung dưới; hoặc yêu cầu Antigravity đọc cả hai file trước khi thực hiện.

```text
VAI TRÒ B. Nhánh demo60/infra. Bạn sở hữu Firebase/Storage, image adapter và smoke.
Ảnh Nano Banana BẮT BUỘC: gọi model thật từ đầu, không chờ phút cuối mới kiểm key.

ALLOWLIST:
backend/src/firebase.py
backend/src/auth.py
backend/src/firestore_repo.py
backend/src/image_upload.py
backend/src/media/** (mới)
firebase/**
scripts/demo/** (mới)
firebase.json, compose.yaml, .env.example, backend/.env.example
contracts/environment.example (ngoại lệ duy nhất B được sửa trong contracts/)
backend/tests/test_demo60_media.py (mới)
backend/tests/test_demo60_firebase.py (mới)
docs/sprint60/B_HANDOFF.md (mới)
Local env/secrets ngoài Git có thể cấu hình, tuyệt đối không commit.

CẤM sửa mobile/, main.py, jobs.py, award.py, assets_routes.py, worker/, missions/,
backend/requirements.txt, mọi contract khác/docs luật chung và ngoài allowlist.
Dependency Python gửi tên/version cho A, không sửa manifest của A.

0–5 PHÚT: PREFLIGHT THẬT
- Đọc PLAN/CONTRACT. Cloud Firebase hiện có: xác minh project, bucket thật,
  Admin IAM, private signed-read và verified account đang dùng. Không tạo cloud mới.
- Chế độ cloud phải phát hiện bất kỳ FIREBASE_*_EMULATOR_HOST/FIRESTORE_EMULATOR_HOST
  hay STORAGE_TYPE=local và báo sai môi trường, không chạy rồi gọi đó là cloud.
- Gọi image model thật bằng GEMINI_IMAGE_MODEL và ảnh được phép, kiểm response có
  bytes ảnh mới. Gemini vision/text không đồng nghĩa key có image-generation quota.
  Tài liệu chính thức hiện hành để chọn model + SDK/REST đúng, ghi tên model thực.
- Báo A/C ngay key/billing/quota/ảnh native/location blockers. Thiếu key thì không
  dựng ảnh minh họa sẵn để thay demo. Preflight ảnh không tái dùng làm quà lượt live.

5–20 PHÚT: STORAGE ROUNDTRIP VÀ NANO BANANA
- Smoke qua API đang có: /me, upload /assets, lấy URL /assets/{id}/url, download.
  Đối chiếu bytes JPEG đã chuẩn hóa với sha256 metadata/object; không so input gốc
  với file đã re-encode. Đọc Firestore record đúng owner/object, không chỉ log200.
- Nếu fail: sửa đúng tầng firebase.py/IAM/bucket/image upload/signed URL trong
  allowlist; lỗi route/DTO thuộc A gửi reproduction. Không public bucket/bypass Auth.
- Tạo backend/src/media/storage.py và souvenir.py với đúng signatures CONTRACT:
  load_owned_image(actor_id,asset_id), put_private_image(object_path,image_bytes,
  mime_type), generate_souvenir(evidence_images,portrait,place_context,timeout_s).
- load_owned_image dùng Admin đọc asset owner/state rồi tải Storage bytes thật;
  không tải URL tuỳ ý. put_private_image chỉ upload+checksum/metadata, A ghi asset
  record/lease; không tạo reward/mission/badge trong helper này.
- generate_souvenir đúng1call, không implicit retry/fallback. Input ảnh người dùng
  + cảnh/portrait được đồng ý, context địa điểm thật; output ảnh hoạt hoạ vui tươi
  giữ đặc trưng địa danh/người, không bịa người nếu thiếu input. Giới hạn timeout60s.
- Từ chối an toàn/provider failure/no image part/bytes không decode được →
  MediaProviderError(code,message sạch). Không trả ảnh gốc làm success.
- Dùng key server, không đưa key vào Expo. Ghi model/latency/call count, không ghi
  bytes ảnh, GPS chi tiết, signed URL hoặc token vào log/Git.

20–35 PHÚT: CHẠY CHUNG VÀ BÀN GIAO
- Push adapter sớm; gửi A SHA/signature/dependencies/env names. A sở hữu job type,
  reserve call/lease/checkpoint/outbox/metadata nên không sửa worker giúp A.
- scripts/demo/start.sh + preflight: nạp env an toàn, kiểm cloud/models/config,
  chạy API và worker bằng hạ tầng đã có; in URL LAN/trạng thái/log đã che secrets.
  Ưu tiên Cloud Tasks/Scheduler hiện hữu. Không mở OIDC endpoints thành public.
- Nếu queue cloud chưa sẵn, cho phép runner nội bộ trên máy backend demo gọi đúng
  process_delivery/recover đã có bằng ADC và DB outbox; không viết worker thứ hai,
  không tắt OIDC routes, không expose runner ra client. Runner chỉ môi trường demo,
  xử lý generation/lease/kind mới theo A và có recovery. Báo đây là local execution
  với cloud persistence, không tuyên bố đã kiểm Cloud Tasks deployment.
- scripts/demo/smoke_firebase.py có phase storage chạy sớm và phase completion chạy
  sau ghép; nhận cấu hình/token qua env, không in bí mật, không raw DB dump.
- Tạo tests media/storage phù hợp, tách live smoke khỏi pytest mặc định. Unit doubles
  không đi vào runtime. Không startup-check live làm mọi unit fixture test hỏng.
- Dùng Firebase test account hiện hữu/đã được nhóm cấp. Không xây login/create user
  UI hoặc bypass email_verified. Gửi C URL API điện thoại truy cập được, Firebase
  public config và cách dùng phiên sẵn; không gửi credential Admin.
- B_HANDOFF gồm command thật, project/bucket/mode, model, SHA, pass/fail/skipped,
  cách xử lý lỗi và module A cần gọi. Push demo60/infra trước phút35.

35–55 PHÚT: CLOUD VÀ RESTART READ-BACK
- Sau A ghép, chạy phase completion trên lượt mission thật: Firestore mission,
  discovery, ledger, badge, completion, job và ảnh Nano Banana mới của lượt đó.
- Cloud Storage chứa ảnh input và output private; đối chiếu owner/hash, GET qua
  signed URL, outsider denied, URL hết hạn và lấy lại qua Auth hoạt động.
- Restart app và tiến trình backend/worker của môi trường demo; không restart
  production dùng chung. Đọc lại completion và bytes qua URL mới để chứng minh
  persistence, không RAM/AsyncStorage. Không gọi lại model khi chỉ xem lại ảnh.
- Replay/redelivery cùng ID không thêm ledger/badge/job/image call. Kiểm souvenir
  asset attached không bị cleanup orphan, lease cũ không publish metadata.
- Nếu lỗi nằm A/C, gửi exact reproduction/ID đã che thông tin nhạy cảm, owner sửa.

55–60 PHÚT: BẰNG CHỨNG
- Ghi lệnh và output đã che bí mật; model/call count/latency, asset/job/discovery IDs,
  project/bucket và checksum, kết quả trước/sau restart, phần chưa kiểm.
- Không nói đã backup/restore Firebase chỉ vì write/read pass. Backup/export toàn
  project không thuộc sprint. Không xóa/reset XP hay dữ liệu thật để diễn lại.
- Không có ảnh quà cloud thật hiển thị lại được thì full demo chưa PASS. Không
  chuyển Emulator rồi gắn nhãn Firebase cloud thành công. Emulator tests vẫn được
  chạy riêng và phải gọi đúng tên, không thay tiêu chí cloud của demo.

XONG KHI: pipeline ảnh có người thật→Nano Banana→private Storage→API→mobile đã chạy,
cloud Firestore/Storage read-back sau restart pass, không rò key/ảnh/quyền và không
provider call lặp. Push chỉ demo60/infra, không main hay nhánh người khác.
```
