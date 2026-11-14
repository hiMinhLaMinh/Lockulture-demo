# Demo nhiệm vụ 60 phút — kế hoạch chung cho ba máy

Chốt ngày 14/11/2026, Asia/Ho_Chi_Minh. Người dùng đã yêu cầu **ảnh Nano Banana bắt buộc** và đồng ý chọn địa điểm gần người thử sau preflight. Bộ này thay phạm vi sprint 90 phút cho lần triển khai mới; không sửa hay coi kế hoạch cũ là bằng chứng runtime.

## Mục tiêu và giới hạn thời gian

Một luồng duy nhất, một địa điểm thật, một phiên Firebase đã đăng nhập:

**GPS hiện tại → Places tìm địa danh thật → Gemini tạo câu đố/nhiệm vụ → mở Maps → người thử tới nơi → chụp ảnh đúng cảnh/người → backend kiểm GPS + Gemini vision → hoàn thành đúng một lần → huy hiệu + animation chúc mừng + kiến thức có nguồn → Nano Banana tạo ảnh hoạt hoạ → lưu Firebase → mở lại vẫn xem được.**

Ảnh Nano Banana là ảnh tĩnh phong cách hoạt hoạ. Animation chúc mừng do React Native chạy riêng, không yêu cầu dựng video bằng AI. Ảnh quà chạy bằng job riêng sau hoàn thành, không giữ transaction thưởng chờ model. Demo đầy đủ chỉ PASS khi ảnh quà đã tạo thật, lưu thật và hiển thị lại được.

60 phút là timebox triển khai/nghiệm thu, không bảo đảm hoàn thành nếu thiếu key, billing, môi trường native hoặc API nhiệm vụ. Không biến ảnh quà thành phần tuỳ chọn để báo PASS. Nếu chưa đủ toàn luồng ở phút 60, ghi PARTIAL/BLOCKED và phần đã có bằng chứng; không giả kết quả.

Không xây đăng nhập/đăng ký/quên mật khẩu; dùng phiên đã có. Không tháo Auth backend, không dùng token giả. Không làm feed/share/friends/leaderboard, nhiều địa danh, chat, refactor lớn hoặc chuyển framework. Bốn vai trò AI là các bước trong cùng backend, không dựng bốn dịch vụ/agent độc lập.

## Hiện trạng đã đối chiếu trong repo

- Main gốc: `dd69975afbce05c8bd58fac36e0ac143ace22673`; remote `origin`, `git@github.com:hiMinhLaMinh/Lockulture.git`.
- Có Auth Firebase, upload private, submissions, worker/outbox/lease và result writer XP; chưa có bằng chứng staging live từ lần soạn tài liệu này.
- `backend/src/jobs.py:intake_submission` vẫn ép `ASSESSMENT_PROVIDER=fixture`; `backend/src/worker/http.py:process_delivery` vẫn gọi `fixture_assessment`.
- Sáu route mission/search/hint/answer có trong OpenAPI nhưng chưa thấy được triển khai trong backend hiện tại. `mobile/src/services/index.ts` còn `apiMissionService.search = notIntegrated`.
- Mobile đã có `expo-location`, camera và UI nhiệm vụ; chưa cần thêm SDK bản đồ. Dùng API Places phía server và mở Google Maps qua link/place ID.
- Chưa có huy hiệu, kiểm GPS tại lúc chụp hoặc pipeline ảnh quà. Đây là feature mới, phải cập nhật contract/schema/examples/acceptance khi triển khai.
- Bản prompt cũ trong tệp đính kèm yêu cầu free-only, bỏ Maps/mission và tăng vision budget lên 2; các điều đó **không áp dụng** cho sprint này.

## Cách dùng bộ prompt

1. Đọc [hợp đồng chung](CONTRACT.md); cả ba đọc cùng một bản từ Git remote.
2. Máy A nhận [prompt A](A_BACKEND_AI.md), máy B nhận [prompt B](B_FIREBASE_IMAGE.md), máy C nhận [prompt C](C_MOBILE.md). Mỗi người dùng Antigravity riêng, clone riêng; không worktree, không cùng thư mục.
3. Dán [khối chung](COMMON_PROMPT.md) trước prompt riêng. Agent mỗi máy tự làm phần mình, không tạo thêm agent hoặc sửa file người khác.
4. [PUBLISH.md](PUBLISH.md) ghi cách lấy đúng commit kế hoạch, tạo nhánh, ghép và chia sẻ. Nhánh kế hoạch vẫn là `demo90/plan` đã được phép push trước đó; nhánh thực thi mới dùng `demo60/*` để tránh đụng nhánh cũ.

## Chia việc không chồng file

Nhãn A/B/C ở đây theo prompt người dùng đính kèm: **A backend/AI và integration, B Firebase/ảnh quà, C mobile**. Khác nhãn A/B của tài liệu sprint90; không trộn hai bảng.

| Người / nhánh | Việc chính | File được sửa | File không được sửa | Phút / phụ thuộc / xong khi |
| --- | --- | --- | --- | --- |
| A / `demo60/ai` | Contract, Places + mission/vision, GPS gate, thưởng/huy hiệu, job ảnh quà, ghép | `backend/src/main.py`, `jobs.py`, `award.py`, `assets_routes.py`, `backend/src/worker/**`, `backend/src/missions/**` mới, `backend/requirements.txt`, `contracts/**`, `docs/implementation/DECISIONS.md`, `AI_JOBS.md`, `API_RULES.md`, `DATA_TRANSACTIONS.md`, `ACCEPTANCE.md`, `TASKS.md`, `docs/sprint60/A_HANDOFF.md`; tests mới `backend/tests/test_demo60_mission.py`, `test_demo60_jobs.py`. Chỉ sau ghép: `docs/CURRENT_STATE.md`, `docs/sprint60/EVIDENCE.md` | `mobile/**`, các module Firebase/ảnh của B, tests của B/C, docs kế hoạch và mọi file ngoài allowlist | 0–8 contract; 8–25 mission/vision; 25–35 transaction/jobs; 35–45 ghép; 45–60 E2E. Phụ thuộc B bytes/model/Storage. Xong khi đủ đường mission→thưởng→image job, regression và contract pass |
| B / `demo60/infra` | Smoke lưu cloud Firebase, đọc ảnh, Nano Banana adapter, upload ảnh quà, môi trường chạy | `backend/src/firebase.py`, `auth.py`, `firestore_repo.py`, `image_upload.py`, `backend/src/media/**` mới, `firebase/**`, `scripts/demo/**` mới, `firebase.json`, `compose.yaml`, `.env.example`, `backend/.env.example`, `contracts/environment.example`, tests mới `backend/tests/test_demo60_media.py`, `test_demo60_firebase.py`, `docs/sprint60/B_HANDOFF.md` | `mobile/**`, `main.py`, `jobs.py`, `award.py`, `assets_routes.py`, `worker/**`, `missions/**`, `backend/requirements.txt`, mọi contract khác, docs luật chung và ngoài allowlist | 0–5 key/cloud; 5–20 persistence + Nano Banana; 20–35 bàn giao adapter/start/smoke; 35–60 hỗ trợ E2E. Phụ thuộc A contract/dispatch. Xong khi ảnh đầu vào/đầu ra cloud đọc lại qua API, model gọi thật, restart vẫn đọc được |
| C / `demo60/mobile` | API nhiệm vụ, GPS lúc chụp, result + badge + animation + gallery ảnh quà | `mobile/**` trừ hệ màu chung, `docs/sprint60/C_HANDOFF.md` | `backend/**`, `firebase/**`, `contracts/**`, docs chung; không đổi `mobile/src/shared/theme/tokens.ts` | 0–8 native/phiên; 8–25 service/GPS; 25–35 result/ảnh quà; 35–60 thiết bị/E2E. Phụ thuộc A DTO, B API URL. Xong khi người dùng đi hết luồng, ảnh quà vẫn xem được sau restart, typecheck/lint pass |

Ngoại lệ duy nhất trong `contracts/**`: `contracts/environment.example` thuộc B; A không sửa file đó. Test fixtures được phép trong unit/Emulator tests tách biệt, không đi vào demo live. Mọi file ngoài allowlist đều không được sửa; yêu cầu owner khi bị chặn. A là người duy nhất thay schema/contract/luật, B là người duy nhất thay Firebase rules/index, C là người duy nhất thay mobile package/lockfile.

## Hợp đồng và thay đổi luật

[CONTRACT.md](CONTRACT.md) là thiết kế được chốt cho sprint, A phải chuyển thành OpenAPI/schema/examples/acceptance trong 8 phút đầu; tài liệu này không tự làm runtime có tính năng. GPS check mission là yêu cầu mới có chủ ý, thay phần "không GPS proof" của luật cũ trong phạm vi nhiệm vụ. Không phục hồi anti-spoof, auto-post, Co-op hoặc XP150. Mission vẫn +100 một lần; free +20 và cap 3 mảnh không đổi. Vision vẫn 1 call/submission; ảnh quà có budget riêng 1 call/job, không tăng vision lên 2.

GPS dùng bán kính đến nơi mặc định **150 m**, accuracy tối đa **50 m**, mẫu không cũ hơn **60 giây tại intake**. Đây là giá trị cấu hình sprint, không phải độ chính xác đảm bảo hay chống giả vị trí. IP chỉ tham khảo khu vực nếu có nguồn phù hợp, không bắt buộc để thưởng. Người thử phải thật sự ở nơi demo; nhập tay tọa độ chỉ để tìm kiếm, không dùng làm bằng chứng đến nơi.

Chỉ chọn một địa danh thật gần người thử; Cầu Rồng là ví dụ, không mặc định nhóm đang ở Đà Nẵng. Nếu không có người ở điểm thật thì không có bằng chứng live cho geofence. Không gán công trình hiện đại vào một triều đại cổ để có nội dung/huy hiệu; chọn era đúng catalog, nguồn không đủ thì bỏ claim, báo no_result nếu không có mission hợp lệ.

## Timeline 60 phút

| Phút | A | B | C | Cổng |
| --- | --- | --- | --- | --- |
| 0–5 | Rà sáu route thiếu; smoke Places + vision; chốt địa điểm gần người thử và nguồn lịch sử | Xác nhận cloud project/bucket/IAM; gọi Nano Banana thật với ảnh được phép | Mở app native, xác nhận phiên đã login, quyền camera/GPS | G0: key/model/Places/cloud/điện thoại và địa điểm đều sẵn hoặc báo BLOCKED ngay |
| 5–8 | Push commit contract riêng; công bố SHA và DTO | Chốt interface bytes/image + biến môi trường; đề nghị dependency cho A | Đọc contract từ remote; không tự định nghĩa API khác | G1: một contract, ranh giới file cố định |
| 8–25 | Mission search/commit, vision, geofence và route đã có trong contract | Smoke upload→download checksum; ảnh Nano Banana→Storage private; viết adapter và start/preflight | API mission, mở Maps, capture + GPS mới, giữ ảnh/idempotency | G2 phút 25: mỗi nhánh có smoke nhỏ thật; B đã có ảnh trả về từ model |
| 25–35 | Atomic reward/badge + enqueue souvenir; worker phân loại job | Bàn giao module image/storage và smoke script; xác nhận môi trường dispatch | Result/badge/animation, poll ảnh quà, refresh URL | G3 phút 35: push ba SHA, khóa API/file; không mở scope |
| 35–45 | Fetch, merge ai → infra → mobile; import/start/contract/regression | Hỗ trợ model/Storage/runner từ nhánh mình | Sửa adapter/UI từ nhánh mình | G4 phút 45: bản ghép chạy được; còn 15 phút dành cho toàn luồng |
| 45–55 | Kiểm đúng/sai GPS và ảnh, replay, đọc Firestore ledger/badge/job | Kiểm ảnh đầu vào/đầu ra cloud, URL TTL, restart đọc lại | Chạy mission→ảnh→huy hiệu→animation→ảnh quà trên điện thoại | G5 phút 55: đủ evidence; ảnh quà không được bỏ |
| 55–60 | Khóa artifact; ghi evidence + CURRENT_STATE theo thực tế | Xác nhận persistence/model/bucket, runbook/rollback | Rehearsal đúng build/thiết bị | 60: PASS toàn luồng hoặc PARTIAL/BLOCKED có danh sách thiếu |

## Smoke Firebase: lưu bền vững khác backup

B viết `scripts/demo/smoke_firebase.py` và ghi lệnh chạy thực tế. Chế độ cloud phải fail preflight nếu có bất kỳ host Emulator nào hoặc `STORAGE_TYPE=local`. Dùng tài khoản nghiệm thu hiện hữu, ID token giữ trong biến môi trường/tiến trình, không đưa token vào command output hoặc Git.

1. Gọi `/me` để bootstrap/mapping; ghi nhận project và bucket thật, không in bí mật.
2. Upload ảnh thử hợp lệ qua API, đọc asset metadata trong Firestore bằng server Admin để đối chiếu owner/object path/checksum; GET URL rồi tải lại và so checksum **JPEG chuẩn hóa đã lưu**, không so ảnh gốc đã bị re-encode.
3. Chạy mission thành công thật; đọc lại mission/discovery/reward_ledger/earned_badges/souvenir job và metadata asset ảnh quà. Chỉ record nghiệm thu, không scan/dump database người thật.
4. Dừng/mở lại app và restart backend/worker test dùng cho demo (không restart dịch vụ production chung); lấy URL mới qua API và tải lại cả ảnh gốc lẫn ảnh quà. Dữ liệu còn đúng, không chỉ cache RAM/AsyncStorage.
5. Replay đúng key/redeliver job: discovery, reward, badge, souvenir job vẫn duy nhất; không phát thêm provider call khi đã có checkpoint/result.
6. Actor khác không lấy được completion/asset private; URL hết TTL không dùng lại, client xin URL mới qua Auth.

Nếu fail: xác định tầng Auth/mapping, IAM/project/bucket, upload bytes, metadata transaction, signed URL hay client cache; B sửa trong file sở hữu, lỗi A/C gửi reproduction cho owner. Chạy lại ca fail và regression liên quan. Không chữa bằng public bucket, bypass Auth hoặc đổi sang local rồi báo Firebase cloud PASS.

Đây là smoke persistence/read-back, **không chứng minh đã có backup/restore thảm hoạ**. Backup policy/export/restore Firestore/Storage là hạng mục riêng nếu người dùng yêu cầu sau; không tự chạy export toàn dữ liệu thật trong sprint.

## Kill switch và nghiệm thu

- Phút 5 thiếu image model/Places/cloud/GPS native: báo blocker cùng bằng chứng, xử lý cấu hình trước. Không dùng ảnh tạo sẵn, output viết tay, mock actor hoặc hardcode câu chuyện để thay live.
- Phút 25 Nano Banana vẫn chưa trả ảnh thật hoặc Places chưa tìm được điểm: dồn hỗ trợ vào blocker, giữ đầy đủ tiêu chí bắt buộc; có thể cắt danh sách nhiều điểm, selfie phụ, hiệu ứng phụ, không cắt ảnh quà/mission/GPS/huy hiệu.
- Phút 45 chưa chạy bản ghép: dừng thêm feature; phút 60 không đủ thì ghi PARTIAL/BLOCKED. Không tự tăng radius đến mức người ở xa cũng pass.
- Sai ACL, trùng XP, lộ key, vượt budget: dừng producer, pause dispatch/queue/Scheduler môi trường demo, kiểm job đang chạy; rollback revision/code đã ghi. Pause queue không huỷ request inflight; rollback code không hoàn tác Firestore/Storage.
- Ảnh quà lỗi không thu hồi XP/badge đã thưởng, UI báo lỗi thật. Điều đó vẫn khiến **demo đầy đủ chưa PASS**. Không tự gọi lại provider khi hết budget để đẹp demo.
- Không dùng ảnh người khác không được phép. Nếu ảnh cảnh không có người dùng, hỏi/chụp thêm ảnh chân dung được đồng ý; không bịa diện mạo. Chỉ lưu ảnh private, không auto-post. Huy hiệu có motif được xác minh phù hợp địa điểm, không gọi trang trí AI là hiện vật lịch sử.

Checklist trước tuyên bố PASS:

1. [ ] Ba máy cùng SHA kế hoạch; ba nhánh đúng owner, chỉ nhánh integration chứa bản ghép; main không đổi.
2. [ ] Contract/schema/examples/acceptance và docs luật được A cập nhật đồng bộ; validator pass.
3. [ ] Places thật trả place ID/toạ độ; nhiệm vụ/câu đố Gemini sinh thật đúng điểm và era, không bịa địa chỉ.
4. [ ] GPS native thật trong radius và ảnh đúng mới hoàn thành; sai radius/accuracy/age hoặc ảnh sai không thưởng.
5. [ ] XP +100/badge/discovery/mission completion và souvenir job được persist idempotent; retry không nhân đôi.
6. [ ] Huy hiệu/title/motif đúng địa điểm, kiến thức/fun fact có URL nguồn phù hợp; không gán sai triều đại.
7. [ ] Animation chỉ chạy sau server xác nhận; reduced motion và trạng thái lỗi/chờ không che kết quả thật.
8. [ ] Nano Banana gọi thật từ ảnh có người dùng/portrait được phép; bytes ảnh mới hiển thị trên mobile, không placeholder.
9. [ ] Firestore + private Storage cloud read-back cả ảnh gốc/ảnh quà sau restart; actor khác bị chặn, URL TTL/refresh đúng.
10. [ ] Backend regression/Emulator, mobile typecheck/lint và live smoke có pass/fail/skipped; ghi SHA/build/mode/model/latency/call counts và phần chưa kiểm.

Tham chiếu acceptance hiện có: API-05/06/07/08/09/10, INV-03/04/05/06/07/08/10, LIVE-03/04. A bổ sung ca GPS/badge/souvenir/persistence mới; chạy một ca không đồng nghĩa toàn bộ nhóm acceptance đã pass.

## Nguồn kỹ thuật đã đối chiếu

- [Google Geolocation](https://developers.google.com/maps/documentation/geolocation/requests-geolocation): IP là fallback ước lượng; backend gọi API bằng IP máy chủ không tự đại diện vị trí điện thoại.
- [Places Text Search](https://developers.google.com/maps/documentation/places/web-service/text-search): server tìm địa danh, chọn field mask tối thiểu; lọc khoảng cách lại thay vì tin location bias như geofence.
- [Expo Location](https://docs.expo.dev/versions/latest/sdk/location/): lấy vị trí/accuracy/timestamp từ thiết bị; không thêm dịch vụ IP thay GPS.
- [Gemini Nano Banana](https://ai.google.dev/gemini-api/docs/image-generation): chọn model image-generation/editing thực sự truy cập được bằng key. `GEMINI_IMAGE_MODEL` là cấu hình riêng với model vision/text; không chốt tên model chưa smoke.

Lần soạn bộ prompt chỉ kiểm tài liệu/code và Git; chưa chạy các smoke live nêu trên, chưa có bằng chứng feature đã triển khai.
