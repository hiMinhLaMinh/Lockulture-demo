# Phân công và bàn giao Lockulture

Chốt ngày 12/11/2026. Nhóm 3 người; triển khai theo thứ tự **thành viên 1 (Minh) → thành viên 3 → thành viên 2**, sau đó nghiệm thu chung. Việc rà soát contract diễn ra trước khi lập trình; không yêu cầu cả nhóm cùng triển khai ngay.

Stack: React Native/Expo, FastAPI trên Cloud Run, Firebase Auth/Firestore/Cloud Storage. Tài liệu này quy định trách nhiệm và thứ tự bàn giao; luật sản phẩm/API theo [implementation pack](implementation/README.md).

## 1. Thống nhất trước khi bắt đầu

Cả ba đọc [quyết định](implementation/DECISIONS.md), [OpenAPI](../contracts/openapi.yaml), [mô hình dữ liệu](implementation/DATA_TRANSACTIONS.md) và [quyền](implementation/AUTH_PERMISSIONS.md). Thống nhất các interface dưới đây trước khi thành viên 1 viết sâu. Không cần chờ Firebase hoặc AI thật mới bắt đầu.

- Actor context: UUID nội bộ do backend xác định; không nhận user ID tự khai từ request làm danh tính.
- Social repositories: users, friend requests/pairs, groups/memberships, posts/grants, reactions/comments; thao tác ghi cần atomicity được diễn đạt thành method nghiệp vụ, không chỉ CRUD từng document.
- Discovery reader: đọc discovery/asset của owner để publish, không phụ thuộc cách AI sinh kết quả.
- Asset access: xác thực owner hoặc Post context rồi cấp URL; UI không coi local URI là ảnh đã upload.
- Assessment result writer: nhận kết quả đã validate, lưu discovery/XP/mảnh một lần; AI không tự cấp thưởng.

Thành viên 1 đề xuất interface Python cụ thể và tests; thành viên 3 rà khả năng thực hiện bằng Firestore; thành viên 2 rà schema đầu vào/đầu ra nhiệm vụ và đánh giá. Thay contract phải cập nhật schema/examples/tests liên quan trong cùng PR.

## 2. Giai đoạn A — Thành viên 1: frontend và social backend

**Phạm vi:** hoàn thiện giao diện, nối HTTP services; viết routes và nghiệp vụ friends, friend requests, groups, members, posts/shares, feed, reactions và comments. Làm lần lượt quan hệ bạn bè → nhóm → publish/quyền đọc → feed → tương tác.

**Dùng tạm:** repository in-memory cho test/dev; actor fixture A/B/C; discovery/asset fixture; bộ cấp URL giả. Chỉ thay dịch vụ chưa có, không bỏ kiểm quyền/validation/luật nghiệp vụ. Adapter giả phải cấu hình rõ, mặc định không hoạt động trong môi trường live; không fallback sang fixture khi Firebase lỗi.

**Không thuộc phạm vi chính:** cấu hình Firebase, Admin JWT verifier, truy vấn/index Firestore, upload Storage thật, transaction XP và worker AI thật. Minh vẫn phụ trách nối frontend khi các phần này được bàn giao sau.

**Cổng bàn giao A:**

- API social chạy qua HTTP, đúng OpenAPI; frontend gọi được API thay vì chỉ sửa Zustand trực tiếp.
- Tests cho đúng/sai actor, người nhận ngoài audience, thành viên mới, leave/rejoin, nhiều nguồn quyền, đăng trùng, replay idempotency, validation và pagination.
- Interface và contract tests có thể chạy với repository khác; test doubles mô phỏng được lỗi và pending. Ghi rõ concurrency/độ bền chưa được chứng minh bằng in-memory.
- Có lệnh chạy, fixture reset, danh sách endpoint và các điểm còn giả lập. Không coi social đã tích hợp live ở mốc này.

## 3. Giai đoạn B — Thành viên 3: Firebase và nền tảng nghiệp vụ

**Phạm vi:** Firebase staging, Auth middleware và mapping UID→UUID; Firestore model/seed/indexes; repositories thật cho social đã bàn giao; Storage/upload/URL ký; hồ sơ, discoveries, timeline và leaderboard; transaction cấp XP/mảnh; hạ tầng job/outbox, lease và deploy Cloud Run/Tasks/Scheduler.

**Trách nhiệm tích hợp:** giữ routes/DTO và interface đã thống nhất. Nếu Firestore cần thay interface, trao đổi và sửa tests cùng thành viên 1, không tạo một backend social thứ hai. Backend Admin SDK tự kiểm ACL; deny Security Rules không thay kiểm quyền server.

**Chuẩn bị cho AI:** dựng worker adapter trả kết quả fixture theo schema để kiểm đường đi submission→job→discovery/XP. Đây là adapter thử nghiệm, không phải bản AI thật hay phương án fallback live.

**Cổng bàn giao B:**

- Chạy lại tests giai đoạn A với repository thật; thêm Emulator tests cho transaction, contention, idempotency, snapshot và quyền.
- Đăng nhập thật → upload thật → đánh giá fixture → lưu discovery/XP thật → frontend hiển thị được. Retry không thưởng trùng.
- Hai tài khoản gửi/nhận bài đúng quyền; ảnh private và URL ký hoạt động trên staging; tài khoản ngoài audience bị từ chối cả qua raw HTTP.
- Bàn giao env template không secrets, seed/index/rules, cách deploy và phục hồi, trạng thái job và hàm lưu kết quả cho thành viên 2. Minh nối Auth và API tiến trình vào frontend ở giai đoạn này.

## 4. Giai đoạn C — Thành viên 2: nhiệm vụ và AI

**Phạm vi:** Maps/Gemini adapters; tìm nhiệm vụ theo GPS/manual và era; mật thư/3 hints/tiêu chí ảnh; đổi nhiệm vụ; đánh giá free/mission và ảnh bổ sung; logic worker, budgets, timeout/checkpoint và lỗi provider.

**Ranh giới:** dùng job/outbox và transaction kết quả từ thành viên 3; không viết kho dữ liệu hoặc luật XP riêng. Gọi phương thức hoàn tất kết quả, không tự tăng XP hoặc auto-post. Bốn agent là vai trò trong backend, không bắt buộc bốn dịch vụ riêng.

**Cổng bàn giao C:**

- Fixture tests bao phủ các verdict, no_result, wrong era/place, budget và provider failure; live smoke với Maps/Gemini thật.
- Mission thành công phát hành đúng địa điểm/era; thất bại giữ mission cũ. Gợi ý đã tạo không gọi AI thêm.
- Free/mission tạo kết quả qua cùng đường lưu dữ liệu đã kiểm ở giai đoạn B. Không còn fixture trong luồng live.
- Ghi model/config, latency/call counts, giới hạn chất lượng và lỗi còn lại; không ghi secrets/ảnh người dùng vào Git.

## 5. Bàn giao chung và tránh sửa chồng

| Thành phần dùng chung | Người chủ trì | Người phối hợp |
|---|---|---|
| OpenAPI, DTO và social interfaces | Thành viên 1 | Thành viên 3 rà lưu trữ, thành viên 2 rà AI |
| Social routes/services và frontend | Thành viên 1 | Thành viên 3 triển khai repository |
| Auth, Storage, Firestore, XP và hạ tầng queue | Thành viên 3 | Thành viên 1 nối UI; thành viên 2 dùng interfaces |
| Mission/evaluation và worker AI | Thành viên 2 | Thành viên 3 hỗ trợ transaction/deploy |

Mỗi người dùng branch riêng từ commit bàn giao đã thống nhất, PR theo chức năng nhỏ. Không sửa lại module người khác âm thầm để chữa contract lệch. Nếu gặp lỗi ở phần đã bàn giao, báo reproduction/test fail và sửa cùng người phụ trách; không chờ tới cuối mới xử lý.

Mỗi lần bàn giao ghi: commit, endpoint/module đã làm, lệnh chạy và test, pass/fail/skipped, fixture còn dùng, env cần cung cấp và việc tồn đọng. Cập nhật [CURRENT_STATE](CURRENT_STATE.md); không đưa secrets vào tài liệu.

## 6. Nghiệm thu cuối

Cả nhóm chạy [acceptance](implementation/ACCEPTANCE.md): hai thiết bị/tài khoản, login→mission/free→capture→upload→AI→XP→share→reaction/comment, restart app, lỗi mạng, retry và mất quyền đọc. Minh chủ trì trải nghiệm mobile, thành viên 3 kiểm dữ liệu/quyền, thành viên 2 kiểm AI.

Thứ tự tuần tự có thể làm tổng thời gian dài hơn và phát hiện hạn chế AI muộn. Dành một mốc tích hợp/sửa lỗi sau giai đoạn C; không coi ngày bàn giao AI là ngày hoàn thành demo. Nếu cần thay schema do thử AI, cập nhật đồng bộ thay vì tự diễn giải kết quả cho UI.
