# Sprint demo 90 phút — kế hoạch đã duyệt

Ngày chốt: 14/11/2026 (Asia/Ho_Chi_Minh). Ba người, **ba máy khác nhau**, mỗi máy một clone riêng; bàn giao qua remote Git `origin`. Không dùng worktree, không dùng thư mục làm việc chung.

## 1. Mốc xuất phát và phạm vi

- Main gốc: `dd69975afbce05c8bd58fac36e0ac143ace22673`.
- Remote: `origin` → `git@github.com:hiMinhLaMinh/Lockulture.git`.
- Nhánh tài liệu: `demo90/plan`; lần chốt này chỉ thêm file Markdown này, commit và push nhánh kế hoạch. Không triển khai nghiệp vụ, tạo nhánh thực thi, deploy hoặc push main trong lần chốt.
- Sprint triển khai bên dưới là công việc sau khi nhận kế hoạch. Nhánh thực thi cùng xuất phát từ main gốc; nhánh integration xuất phát từ commit kế hoạch đã push để giữ tài liệu trong bản ghép.
- Repo đã có tham chiếu local `demo90/ai`, `demo90/infra`, `demo90/mobile`, `demo90/integration`. Không thao tác checkout khác, không reset/xóa/ghi đè các nhánh đó. Trên từng máy, kiểm tra nhánh local/remote trước khi dùng; nếu có lịch sử khác baseline thì dừng để chủ nhánh xử lý, không force push.

Nguồn chuẩn: [implementation pack](../implementation/README.md), [quyết định](../implementation/DECISIONS.md), [TASKS](../implementation/TASKS.md), [CURRENT_STATE](../CURRENT_STATE.md), [handoff B](../implementation/PHASE_B_HANDOFF.md), [transactions](../implementation/DATA_TRANSACTIONS.md), [Firebase](../../firebase/README.md), [OpenAPI](../../contracts/openapi.yaml), [AI schemas](../../contracts/ai/README.md), [acceptance](../../contracts/acceptance.json), [design system](../DESIGN_SYSTEM.md).

Phân công A/B/C dưới đây là nhãn người trong sprint này, không phải tên giai đoạn A/B/C trong tài liệu cũ. Sprint tiếp tục baseline đã có Firebase/Expo; không làm lại social backend hoặc repository. Tài liệu hiện trạng báo local/Emulator đã kiểm, nhưng staging, Docker và camera native còn thiếu bằng chứng; phải kiểm lại artifact định demo.

**Đường demo ưu tiên:** hai tài khoản nghiệm thu trên hai thiết bị → Auth → chụp free → upload private → Gemini đánh giá → discovery/XP/mảnh do backend lưu → chọn người nhận và chia sẻ → thiết bị nhận refresh, reaction/comment → người gửi refresh. Kiểm thêm người ngoài audience bằng raw HTTP và retry không thưởng trùng.

Maps/tìm nhiệm vụ live chỉ đưa vào demo nếu đã có bằng chứng và không ảnh hưởng đường ưu tiên; không cam kết hoàn thành cả task AI trong 90 phút. Không dựng mission giả trong dữ liệu thật để chứng minh mission live. Không hồi sinh anti-spoof, auto-post, Co-op, XP150; không viết lại UI sang Flutter/web. Không mở rộng schema/API/luật trong sprint này.

## 2. Bảng phân công và quyền sửa file

Danh sách dưới đây là allowlist; ngoài danh sách của mình đều không được sửa. `**` là toàn bộ file trong thư mục tương ứng. Mỗi người dành đủ 90 phút gồm triển khai, bàn giao và hỗ trợ nghiệm thu; đây không phải 270 phút chạy tuần tự.

| Người / nhánh / máy | Công việc | File được sửa | File KHÔNG được sửa | Phút | Phụ thuộc | Tiêu chí xong |
| --- | --- | --- | --- | --- | --- | --- |
| **A — infra và điều phối ghép**; `demo90/infra`; máy A | Nối provider vào worker/intake; budget, lease, checkpoint; đọc ảnh private phía server; cấu hình staging và deploy; giữ result writer/ACL; ghép ba nhánh | `backend/src/jobs.py`, `backend/src/worker/http.py`, `backend/src/firebase.py`, `backend/src/image_upload.py`, `backend/src/main.py`, `backend/requirements.txt`, `backend/Dockerfile`, `backend/Dockerfile.dockerignore`, `backend/tests/conftest.py`, `backend/tests/test_platform.py`, `backend/tests/test_firebase_emulator.py`, `backend/tests/test_local_assets.py`, `backend/tests/test_worker_provider.py` (mới), `firebase/**`, `contracts/environment.example`, `docs/sprint90/A_HANDOFF.md` (mới). Chỉ trên integration sau ghép: `docs/CURRENT_STATE.md`, `docs/sprint90/DEMO_EVIDENCE.md` (mới) | `mobile/**`, `backend/src/ai/**`, tests AI của B, `backend/src/award.py`, `backend/src/firestore_repo.py`, `backend/src/social/**`, `backend/src/platform_routes.py`, `backend/src/assets_routes.py`, các contract/schema bị đóng băng và mọi file ngoài allowlist | 0–10 chốt; 10–50 nối/kiểm infra; 50–60 bàn giao; 60–70 ghép/deploy; 70–90 nghiệm thu/chốt = **90** | Interface B chốt phút 10; staging billing/IAM/bucket; nhánh B và C có SHA bàn giao | Contract + backend regression/Emulator pass; provider thật không fallback; replay/redelivery không gọi/thưởng lặp; ảnh private/ACL đúng; bản deploy có SHA + digest + rollback đã ghi. Thiếu môi trường ghi blocked, không tuyên bố live pass |
| **B — AI**; `demo90/ai`; máy B | Gemini assessment free/mission theo schema; prompt, validation, lỗi provider; kiểm verdict và ảnh bổ sung; bàn giao adapter thuần cho A | `backend/src/ai/**` (mới), `backend/tests/test_ai_provider.py` (mới), `backend/tests/test_ai_assessment.py` (mới), `docs/sprint90/B_HANDOFF.md` (mới) | `mobile/**`, `firebase/**`, `backend/requirements.txt`, `backend/src/jobs.py`, `backend/src/worker/**`, `backend/src/award.py`, repositories/routes/Auth, các contract/schema bị đóng băng và mọi file ngoài allowlist | 0–10 interface; 10–35 adapter; 35–50 tests/smoke; 50–60 bàn giao; 60–90 hỗ trợ ghép/đánh giá = **90** | Schemas baseline; A cung cấp bytes ảnh và runtime secrets; A sở hữu dependency manifest | Schema-valid free/mission; phân biệt ảnh mờ/không nhận diện/ngoài phạm vi/không khớp; không tự XP/post; một lần gọi mỗi invocation; provider lỗi không trả fixture; ghi model, latency, call count và phần live chưa kiểm |
| **C — mobile**; `demo90/mobile`; máy C | Nối adapter/hook API có sẵn; Auth, capture/polling/result/share/feed; xử lý lỗi và cache theo account; giữ UI | `mobile/**`, `docs/sprint90/C_HANDOFF.md` (mới) | Toàn bộ `backend/**`, `firebase/**`, `contracts/**`, docs dùng chung và mọi file ngoài allowlist | 0–10 xác nhận DTO; 10–40 nối luồng; 40–50 kiểm thiết bị; 50–60 bàn giao; 60–90 hỗ trợ smoke/rehearsal = **90** | OpenAPI/DTO baseline; A bàn giao HTTPS URL + Firebase public config; kết quả AI chỉ qua backend | Typecheck/lint pass; camera trên native; loading/error/terminal failed đúng; refresh token một lần; polling dừng nền; kết quả/XP từ server; hai thiết bị gửi–nhận; logout không lộ cache account cũ |

**File đóng băng cho cả ba:** `contracts/openapi.yaml`, `contracts/ai/**`, `contracts/examples/**`, `contracts/fixtures/**`, `contracts/acceptance.json`, `mobile/src/shared/theme/tokens.ts` (không cần đổi thiết kế), `docs/sprint90/PLAN.md`, `legacy/**`, lockfile/config root và các tài liệu luật chung. Allowlist rộng hơn không được vượt danh sách đóng băng. A có thể ghi tên biến không bí mật vào `contracts/environment.example`, không đổi contract nghiệp vụ.

Nếu phát hiện lỗi bắt buộc sửa file đóng băng hoặc luật/transaction hiện hành: ghi reproduction và owner, dừng phần bị chặn, dùng kill switch. Không sửa lén schema; thay API/luật sau sprint phải cập nhật contract, schema, examples và acceptance đồng bộ.

## 3. Hợp đồng giao tiếp

### 3.1 Mobile ↔ FastAPI

- Giữ nguyên `/api/v1`, field/type/nullability/enum và HTTP status theo OpenAPI; lấy UUID nội bộ từ backend, không dùng Firebase UID làm resource ID.
- Mobile chỉ gọi Firebase trực tiếp cho Auth; ID token trong `Authorization: Bearer`. Backend xác minh token và email verified, mapping actor; client không tự khai owner/XP/ACL.
- Mỗi mutation giữ `Idempotency-Key` UUID cho cùng thao tác/retry mạng; body khác phải key mới. 401 refresh một lần, gửi lại cùng key. Không POST mới để thay GET polling.
- Submission nhận 202 rồi GET theo ID; terminal failed vẫn HTTP 200 với `error: ErrorDetail | null` trong resource. HTTP lỗi dùng envelope Error; tôn trọng `retryable` và `Retry-After`, không lồng thêm lớp error.
- Poll 2 giây trong 10 giây đầu, 3 giây tới 30 giây, 5 giây tới 120 giây; sau đó cho biết còn xử lý và tiếp tục GET khi quay lại. Dừng polling lúc app background.
- Ảnh upload qua FastAPI, không đưa local URI vào live post; URL đọc ký 60 giây qua backend sau kiểm quyền. UI dùng discovery/XP/mảnh trả về từ server và refresh các query liên quan.
- Không chọn sẵn người nhận; publish bắt buộc audience, không auto-post. Refresh feed/reaction/comment giữa hai thiết bị; không yêu cầu realtime/push trong sprint.

### 3.2 B ↔ A: adapter nội bộ phải chốt ở phút 10

Module mới `backend/src/ai/assessment.py` do B sở hữu, export:

```python
def assess(*, mode: str, images: list[bytes], mission: dict | None,
           previous_instruction: str | None, era_ids: list[str],
           timeout_s: float) -> dict: ...

class ProviderError(Exception): ...
```

- `images` là 1–4 ảnh JPEG đã chuẩn hóa, thứ tự bằng chứng trong cùng session, do A đọc bằng quyền server; `mission` là context authoritative hoặc null ở free. Không nhận URL tùy ý do client gửi, không ghi ảnh/token vào log/Git.
- Kết quả là object đúng `free-assessment.schema.json` hoặc `mission-assessment.schema.json`, không thêm XP/discovery/post. A validate lại schema trước persist. B không truy cập Firestore/Storage và không tự thưởng.
- B định nghĩa `ProviderError.code` thuộc `provider_failed` hoặc `deadline_exceeded`, thông báo đã bỏ thông tin nhạy cảm. A quyết định retryable dựa trên checkpoint/counters/deadline; lỗi provider không biến thành verdict hoặc kết quả fixture.
- Một invocation tối đa một Gemini request, không có SDK retry ngầm hoặc vòng sửa JSON. A dự trữ `gemini_calls` trong transaction dưới lease **trước** call; B không gọi provider khi timeout không còn. Submission budget 1 Gemini; giới hạn attempts/deadline theo config hiện hành.
- A giữ claim/generation/lease, đọc ảnh, lưu checkpoint và gọi `award_result(job_id, lease_token, assessment)` hiện có. Không gọi network trong Firestore transaction; checkpoint có sẵn thì finalize, không gọi Gemini lại. Crash sau call trước checkpoint không được gọi lại khi hết budget.
- A phải xử lý cả gate hiện tại trong `intake_submission` (đang chỉ cho `fixture`) lẫn lựa chọn adapter trong worker; chỉ đổi worker không đủ cho live. Giữ nguyên policy fixture allowlist riêng.
- Cấu hình dự kiến: `ASSESSMENT_PROVIDER=gemini`, `GEMINI_API_KEY`, `GEMINI_MODEL` do A đưa vào runtime/Secret Manager; B báo dependency + version để A sửa duy nhất `backend/requirements.txt`. Không đưa khóa vào Expo hay Git. Model và timeout cụ thể ghi trong handoff, không mặc định một tên model chưa smoke.
- Không thay chữ ký muộn bằng sửa file người khác: báo lỗi tại mốc bàn giao; A/B thống nhất trước khi merge. Live thiếu key/model/quyền phải thất bại rõ, không fallback fixture.

### 3.3 Git và bàn giao giữa ba máy

Mỗi người fetch `origin`, xác minh main gốc, tạo nhánh mình từ hash baseline trong clone của mình. Đọc kế hoạch bằng nhánh `origin/demo90/plan`; không merge nhánh người khác vào nhánh thực thi. Không dùng worktree. Trước push, mỗi người kiểm status và diff theo allowlist rồi push đúng nhánh mình; không `push --all`, không `--mirror`, không force push, không push main.

Mốc phút 10, 35, 50, 60: báo tiến độ, blocker, thay đổi interface (nếu có), ETA. Handoff trong file riêng A/B/C gồm: SHA commit; file sửa; interface/env names không secrets; lệnh chạy; kết quả pass/fail/skipped; live/emulator/fixture mode; hạn chế và cách tái hiện. Trao thông tin qua kênh nhóm, nội dung cần tái lập phải nằm trong handoff đã commit. Không gửi khóa/tokens trong handoff.

Từ phút 60 đóng băng SHA ba nhánh. Nếu cần sửa sau đó, đúng owner commit trên nhánh mình, push và báo SHA mới; A fetch/merge riêng, kiểm lại phần bị tác động. Không sửa cùng file trên integration để chữa nhanh trong khi owner đang sửa.

## 4. Timeline 90 phút và cổng quyết định

| Phút | A | B | C | Cổng chung |
| --- | --- | --- | --- | --- |
| 0–10 | Xác minh clone/commit/env, billing/IAM, bucket, thiết bị, revision rollback; chốt interface | Chốt assess/ProviderError, model và dependency | Chốt DTO, URL dự kiến, tài khoản/thiết bị | G0: đủ baseline và quyền sở hữu; không bí mật trong Git; thiếu hạ tầng chọn phương án cô lập ngay |
| 10–35 | Nối intake/worker, budget/checkpoint; chuẩn bị staging | Adapter/schema/prompt, tests provider giả lập | Nối capture/result/share và lỗi theo API baseline | 35: mỗi người báo SHA tạm, tests và blocker; không mở scope |
| 35–50 | Emulator/regression, thử private Storage/queue/OIDC | Tests verdict và smoke Gemini với ảnh thử được phép | Typecheck/lint và smoke camera/Auth native | G1 phút 50: live provider + infra đủ thì tiếp tục; thiếu thì bật kill switch, bỏ Maps/mission live trước |
| 50–60 | Hoàn thiện A_HANDOFF, push infra; ghi revision/digest cũ | B_HANDOFF, push ai; chốt model/call count | C_HANDOFF, push mobile; ghi thiết bị/build/env | G2 phút 60: ba SHA và trạng thái test rõ; không merge nhánh không rõ nguồn hoặc ngoài allowlist |
| 60–70 | Fetch ba nhánh; ghép **ai → infra → mobile**; kiểm, build/deploy artifact ghép | Hỗ trợ lỗi adapter ở nhánh mình | Hỗ trợ lỗi client ở nhánh mình | G3 phút 70: có bản chạy xác định được SHA/digest; lỗi build/ACL/XP thì không mở live |
| 70–85 | Chủ trì hai thiết bị, raw HTTP tài khoản ngoài audience, retry/ledger, rollback nếu cần | Quan sát verdict, provider count và lỗi có kiểm soát | Chạy camera→share, refresh và account switch | G4 phút 85: khóa artifact, ghi evidence và checklist; không thêm feature |
| 85–90 | Ghi CURRENT_STATE/evidence đúng thực tế và mode demo | Xác nhận AI thật/fixture, phần chưa kiểm | Rehearsal trên đúng thiết bị/build | Phút 90 dừng sửa; chỉ trình diễn đường đã kiểm, báo giới hạn |

## 5. Kill switch

- **Trigger ngay:** lộ secrets/ảnh/quyền, fixture chạm tài khoản thật ngoài allowlist, XP trùng, vượt tool budget, ACL sai hoặc artifact deploy không xác định được SHA. **Trigger theo mốc:** G1 thiếu provider/hạ tầng, G3 không có bản ghép chạy được, G4 chưa qua kiểm quyền/retry.
- A là người điều phối dừng ghi mới: dừng thao tác từ app, ngừng producer/dispatcher và pause queue + Scheduler đúng môi trường demo; kiểm các job đang chạy vì pause queue không hủy request đã nhận. Chặn ingress nghiệp vụ hoặc đưa service demo về revision đã xác minh an toàn theo runbook nếu cần; không dựa vào đổi UI để chặn worker/XP.
- Với lỗi provider đơn thuần: chặn submission mới và ghi rõ unavailable, không tự bật fixture trên live. Giữ checkpoint/counters để không redelivery gọi lặp; không reset ledger hoặc xóa key để “thử lại”.
- Thứ tự cắt phạm vi: Maps/mission live → đường phụ/UI phụ → dừng đường ghi live. Giữ bằng chứng những phần đã qua kiểm, không công bố hoàn tất toàn acceptance khi mới demo free.
- Demo dự phòng dùng **môi trường riêng** local/Emulator với project `demo-lockulture`, fixture bật tường minh và nhãn demo giả lập rõ; không dùng ADC/project/bucket live, không đồng bộ XP/posts ra staging. Nếu không chứng minh cô lập, chỉ trình bày tài liệu/bằng chứng đã ghi và phần chỉ đọc đã kiểm.
- Trước deploy A ghi revision/image digest/env mode an toàn để rollback. Revert revision không hoàn tác dữ liệu; ghi lại ID tài nguyên phát sinh và xử lý theo owner/runbook, không bulk delete hoặc reset dữ liệu thật. Khóa lộ phải thu hồi/rotate; kiểm bằng smoke an toàn trước khi mở lại.

## 6. Rủi ro dữ liệu thật và biện pháp bắt buộc

| Rủi ro | Biện pháp / bằng chứng cần có |
| --- | --- |
| Nhầm project, bucket hoặc tài khoản người dùng | A kiểm `FIREBASE_PROJECT_ID`, tên bucket thật, revision và danh sách UUID nghiệm thu trước thao tác; staging `lockulture-f9c7d` không mặc nhiên là môi trường dùng fixture an toàn |
| Mock/fixture tạo XP/posts thật | Không import AsyncStorage/fixtures lên API; không seed discovery/reward vào account thật; fixture chỉ trong môi trường riêng hoặc phiên nghiệm thu được allowlist tường minh theo policy hiện hành, ghi rõ mode |
| Admin SDK vượt Security Rules | Backend giữ ACL/owner checks; thử người ngoài audience qua HTTP, deny truy cập client Firestore/Storage. Không lấy rules deny-all làm bằng chứng ACL server |
| Ảnh, vị trí, token hoặc khóa bị lộ | Ảnh mẫu có quyền sử dụng, hạn chế dữ liệu cá nhân; Storage private, URL ký 60 giây, không log URL/token/ảnh; secrets chỉ phía server; không commit `.env`, JSON service-account hoặc dump DB |
| Retry/redelivery tăng XP hoặc tốn tiền lặp | Giữ idempotency, reward ledger và transaction; reserve tool budget trước call, kiểm lease/checkpoint; test concurrent/replay và crash mất checkpoint. Free +20/subject/ngày Việt Nam, mission +100 một lần; mảnh unique subject cap 3 |
| Chia sẻ sai người/khôi phục quyền nhóm cũ | Audience bắt buộc, all-or-nothing, snapshot membership incarnation; kiểm outsider, join mới/leave-rejoin và overlap direct/group theo acceptance |
| Cache account cũ và URL hết hạn | C kiểm logout/account switch xóa cache/draft, dừng polling; URL hết hạn lấy lại qua API kiểm quyền, không lưu URL công khai lâu dài |
| Rollback app nhưng dữ liệu đã đổi | Ghi tài nguyên nghiệm thu và revision; không coi rollback code là rollback Firestore/Storage; không chạy cleanup xóa account hoặc dữ liệu ngoài phạm vi thử |

## 7. Quy trình merge qua origin — A thực hiện trên máy A sau sprint

**Đây là hướng dẫn cho mốc 60–70, không phải lệnh cần chạy khi chốt kế hoạch.** Nhánh làm việc mỗi người phải sạch trước fetch/checkout/merge. Nếu có thay đổi chưa commit thì dừng; không stash/reset tự động.

1. A nhận ba SHA bàn giao đã push và kết quả test. Fetch đúng ba nhánh từ remote; fetch nhánh kế hoạch để tạo integration chứa kế hoạch:

   ```sh
   git fetch origin demo90/ai:refs/remotes/origin/demo90/ai demo90/infra:refs/remotes/origin/demo90/infra demo90/mobile:refs/remotes/origin/demo90/mobile
   git fetch origin demo90/plan:refs/remotes/origin/demo90/plan
   git rev-parse origin/demo90/ai origin/demo90/infra origin/demo90/mobile
   ```

2. Đối chiếu từng SHA với handoff; dùng `git merge-base --is-ancestor dd69975afbce05c8bd58fac36e0ac143ace22673 <SHA>` và `git diff --name-only dd69975afbce05c8bd58fac36e0ac143ace22673 <SHA>` để kiểm baseline/allowlist. Kiểm lịch sử không kéo theo commit ngoài scope; nếu remote tiến thêm chưa được duyệt thì dừng để owner chốt lại SHA.
3. Trong clone riêng của A, tạo `demo90/integration` từ `origin/demo90/plan`. Nếu nhánh đã có, kiểm nguồn/lịch sử và trạng thái trước khi tiếp tục; không dùng `switch -C` hoặc force reset. Không thao tác thư mục làm việc của máy khác.
4. Merge lần lượt đúng các **SHA đã xác minh**, không đổi thứ tự:

   ```sh
   git switch -c demo90/integration origin/demo90/plan
   git merge --no-ff <AI_SHA> -m "Merge demo90/ai"
   git merge --no-ff <INFRA_SHA> -m "Merge demo90/infra"
   git merge --no-ff <MOBILE_SHA> -m "Merge demo90/mobile"
   ```

   Các token `<..._SHA>` phải được thay bằng hash bàn giao thật trước khi chạy. Mỗi merge kiểm diff/status. Có conflict thì `git merge --abort`, gọi đúng owner sửa trên nhánh của mình rồi fetch lại; không chọn ours/theirs toàn bộ để bỏ qua contract. Nếu baseline/allowlist đúng mà conflict vẫn xuất hiện, rà lại ranh giới trước khi tiếp tục.

5. Chạy contract validator (`python scripts/contract/validate.py`; dùng `python3` nếu máy không có alias `python`), tests AI mới, toàn suite backend với Auth/Firestore/Storage Emulator theo handoff B, `npm run typecheck`, `npm run lint` trong `mobile/`. Build Docker từ root và smoke `/health`; chạy checklist native/live bên dưới. Emulator pass không thay cho staging, web/export không thay cho native camera.
6. A ghi `DEMO_EVIDENCE.md` và cập nhật `CURRENT_STATE.md` **chỉ theo runtime đã kiểm**, gồm pass/fail/skipped, ba SHA nguồn, integration SHA chứa code, image digest/revision, app build và env/provider mode. Nếu commit bằng chứng sau build, ghi riêng SHA tài liệu; artifact vẫn phải chỉ đúng SHA đã build và kiểm.
7. Chỉ sau các cổng, A push rõ `origin demo90/integration` và deploy đúng artifact cho staging demo; không merge/push main. B/C nhận integration qua origin để chạy cùng backend/build. Giữ revision an toàn để rollback; phút 85 trở đi khóa artifact.

Lần chốt kế hoạch hiện tại **chỉ push `demo90/plan`**. Các push nhánh thực thi/integration và deploy ở trên thuộc giai đoạn triển khai sau, không được chạy kèm lần chốt này.

## 8. Checklist đúng 10 điểm trước demo

Mỗi điểm cần người xác nhận + kết quả/bằng chứng trong `DEMO_EVIDENCE.md`; ô chưa đạt giữ trống và ghi giới hạn hoặc kích hoạt kill switch, không tự đánh dấu từ tài liệu kế hoạch.

1. [ ] **Nguồn và artifact — A:** ba SHA đúng baseline/allowlist, merge ai → infra → mobile; biết integration SHA, app build, image digest/revision và chế độ demo; không có thay đổi main.
2. [ ] **Kiểm tự động — A/B/C:** contract validator, AI tests, backend regression/Emulator, mobile typecheck/lint, Docker build và health smoke có kết quả; pass/fail/skipped được tách rõ.
3. [ ] **Auth và account switch — C/A:** login email verified trên hai thiết bị, refresh 401 một lần, logout xóa cache/draft và không lộ account trước; token sai/hết hạn bị từ chối (API-02, LIVE-01).
4. [ ] **Ảnh private và native — C/A:** camera native → upload JPEG qua API, signed URL hết hạn đúng, client không đọc trực tiếp Firestore/Storage; outsider không lấy ảnh (API-07/08, INV-12, LIVE-04).
5. [ ] **AI và mode — B/A:** ảnh rõ/mờ/ngoài phạm vi cho verdict/schema đúng, lỗi provider không giả thành thành công; ghi model/latency/call count, không fallback fixture. Mission/Maps chưa live ghi rõ phần LIVE-03 chưa đạt (INV-05, LIVE-03).
6. [ ] **Job, lỗi mạng và retry — A/C:** queued/running/failed hiển thị đúng; polling dừng nền; replay cùng key, redelivery, lease hết và crash trước checkpoint không tạo call vượt budget (API-09/10, INV-07/08/10).
7. [ ] **XP/mảnh authoritative — A/C:** kết quả khớp `/me`, timeline và leaderboard; retry/concurrency không thưởng trùng, daily gate ngày Việt Nam và cap 3 đúng; mobile không tự cộng (API-03/20, INV-03/09).
8. [ ] **Chia sẻ và ACL — C/A:** chọn recipient bắt buộc; thiết bị nhận thấy ảnh, outsider bị chặn raw HTTP; người mới/rejoin không thấy bài nhóm cũ, direct grant hợp lệ vẫn giữ quyền (API-15/16, INV-01/02, LIVE-02).
9. [ ] **Tương tác và UI — C:** reaction/comment qua hai thiết bị và refresh, counts đúng, không XP; loading/empty/error có đường phục hồi, giữ design system và kiểm màn hình native (API-18/19, LIVE-02).
10. [ ] **Dữ liệu và phục hồi — A/B/C:** chỉ tài khoản/ảnh thử được phép, không secrets/mock import, project/bucket đúng, revision rollback đã ghi và thao tác kill switch sẵn sàng; hạn chế live/nghiệm thu chưa chạy được công bố trước demo.

Kế hoạch được chốt không có nghĩa đã đạt runtime, staging hoặc toàn bộ acceptance. Lần thay đổi này không cập nhật CURRENT_STATE vì chưa triển khai feature nào.
