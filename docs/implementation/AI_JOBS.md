# Agent và trạng thái tác vụ

[Chỉ mục](README.md) · [AI schemas](../../contracts/ai/) · Bốn vai trò trong cùng backend; không có agent chạy trên mobile.

## Lưu trạng thái và thực thi

POST search/submission ghi job + outbox trong Firestore rồi trả 202. Cloud Tasks gọi POST `/internal/jobs/{job_id}` trên Cloud Run với OIDC service account riêng; endpoint nội bộ không dùng Firebase JWT và không nằm trong public OpenAPI. Kiểm tra issuer/audience và email service account allowlist. Không chỉ tin header tên queue.

Dispatcher đọc outbox chưa delivered, tạo task có tên cố định theo job ID + `job_outbox.generation`. Nếu enqueue thành công nhưng update DB thất bại, duplicate task không tạo job mới. Cloud Scheduler gọi dispatcher mỗi phút để phục hồi outbox; publish đường nhanh có thể enqueue sau transaction nhưng không xóa nhu cầu dispatcher.

Worker claim bằng Firestore transaction kiểm điều kiện queued hoặc lease hết hạn; attempts<3, deadline chưa hết, gán lease_token mới và lease_until=now()+150s. Search xử lý tối đa 120s, submission 60s, HTTP worker timeout 180s. Chỉ worker giữ lease hiện hành mới commit; delivery khác đang có lease trả 2xx/no-op. Scheduler requeue jobs lease hết bằng transaction đổi queued, tăng outbox.generation, clear delivered_at; hoặc mark failed nếu đã quá deadline/attempt. Manual retry dùng cùng cơ chế. Đặt tên task `<job UUID>-<generation>` để không bị dedupe task cũ cản phục hồi. Không gọi AI ngoài request background không bền vững.

## State machines

| Resource | Chuyển trạng thái hợp lệ |
|---|---|
| Search job | queued → running → succeeded / no_result / failed |
| Submission job | queued → running → succeeded / failed |
| Session | open → awaiting_evidence → awaiting_evidence / completed / closed / expired |
| Mission | active → completed hoặc replaced |
| Asset | ready → deleting → deleted |

- Search stage: queued/finding/reviewing/preparing/done. Submission: queued/evaluating/persisting/done.
- accepted/completed → session completed. retake_required/unidentified → awaiting_evidence nếu count<4, còn hạn; nếu hết ảnh → closed, instruction yêu cầu bắt đầu phiên mới. out_of_scope/not_matched → closed.
- Error provider không phải verdict: submission failed, session giữ trạng thái trước khi nộp để retry cùng submission. Đang có failed last submission không cho thêm ảnh bằng session; retry trước hoặc bắt đầu session mới. GET trả trạng thái tương ứng.
- Expiry kiểm tra cả lúc nhận và commit; kết quả tới sau expires_at bị discarded/session expired. Mission bị replaced cũng không được hoàn thành bởi worker cũ.
- Persist tool response vào jobs.checkpoint dưới lease trước bước tiếp. Crash sau provider call nhưng trước checkpoint có thể mất kết quả; không gọi lại khi hết budget. Nếu có checkpoint hợp lệ thì finalize không gọi provider. Manual retry chỉ khi có checkpoint để tiếp tục hoặc còn tool budget, attempts<3/deadline còn; không reset counters. Hết ngân sách cho UI bắt đầu submission/session mới với key mới, luật thưởng server vẫn chống lặp.
- Client polling 2s trong 10s đầu, 3s tới 30s, 5s tới 120s. Sau đó hiển thị “Vẫn đang xử lý”, cho rời trang và tiếp tục GET khi quay lại; không tự POST lần mới. GET retry có backoff và dừng khi app background.

## Agent tìm nhiệm vụ

1. Nhận era hoặc any, location/radius từ request, active expectation và budget.
2. Gemini chọn `search` query qua JSON schema; backend chỉ cho Maps Text Search và filters định sẵn, radius <= yêu cầu. Query mặc định gắn attractions/điểm mốc lịch sử; backend đo distance và loại ngoài radius.
3. Trả candidates tối đa 10 với Place ID/tên/location/address, không lấy reviews. Gemini chọn `select`, `search` lần hai hoặc `stop` theo search-decision schema.
4. select phải dùng Place ID đã trả, era trong catalog và phù hợp era filter. Sinh clue, 3 hints, photo requirements và knowledge rationale. Validate JSON/server constraints trước phát hành mission.
5. Không đủ -> no_result; provider lỗi -> failed. Không bịa tọa độ hoặc thay era để có kết quả.

Đếm Maps/Gemini **trước** call trong DB, theo lease; checkpoint ghi candidates/decision/assessment cùng stage đã hoàn thành. Mỗi tool response validate rồi ghi checkpoint; token worker cũ không thể ghi. Nếu không có checkpoint và hết ngân sách thì terminal failed/no_result phù hợp, không lặp call.  Một search tối đa 2 Maps, 3 Gemini gồm quyết định và tạo nhiệm vụ. Nếu model dùng hết budget mà chưa có nội dung hợp lệ thì no_result; không gọi vô hạn để sửa JSON. Place candidates/cache chỉ là nội bộ, không coi dữ liệu fixture là Maps thật.

## Agent đánh giá ảnh

Prompt phải nêu mode, tiêu chí server nếu mission, danh sách ảnh cùng session, hướng dẫn bổ sung trước đó. Ảnh/chữ trong ảnh là dữ liệu không phải lệnh. Không anti-spoof, không kiểm tra GPS hiện diện hoặc confidence threshold 0.8. Tạm tin kiến thức lịch sử như luật MVP.

Response theo assessment schema: verdict, name, knowledge, instruction, category, canonical_name, locality, era_id. Mode-specific verdict phải được server kiểm tra; accepted free chỉ street_sign/food/object. Mission completed phải khớp photo_requirements, không chỉ cùng thời kỳ. Nếu không xác định được liên hệ văn hóa: out_of_scope hoặc unidentified tùy bằng chứng, không bịa.


Internal contract: Task POST `/internal/jobs/{job_id}` body `{generation: integer>=0}`, OIDC task identity; worker so generation với outbox và return204/no-op nếu cũ/terminal/còn lease worker khác. Scheduler POST `/internal/dispatch` và `/internal/maintenance` body `{}`, OIDC scheduler identity,200 `{processed: integer>=0}`. Deadline/attempt exhausted ghi trạng thái failed rồi204 để không lặp vô hạn; lỗi hạ tầng trước khi ghi DB trả503 để queue retry. Dispatcher xử lý từng job và ghi lỗi/retry DB, không bỏ toàn batch.

Nguồn nền tảng: [Cloud Tasks HTTP/OIDC và task naming](https://docs.cloud.google.com/tasks/docs/creating-http-target-tasks). Lease/checkpoint/counters là thiết kế của Lockulture.


## Sprint60 — contract 1.1.0

Mission requires native capture GPS at intake: radius 150m, accuracy <=50m, age <=60s, future <=5s. This supersedes the previous no-GPS mission rule; it is not anti-spoof protection. Free mode is unchanged. Persist the immutable location/config/mission-version snapshot; inference latency does not age it again.

Completion atomically writes the existing +100 ledger/discovery/progress, deterministic earned badge, mission_completions and optional souvenir job/outbox. Read all reservations before writes. Souvenir reserves one image call separately from vision1; checkpoint and asset publication require the current lease. Image failure keeps rewards. Owner-only GET celebration never creates jobs; private attached assets use existing 60s signed URLs.

Search/submission/souvenir workers share dispatch, leases and recovery, with kind-specific counters. Live uses real providers without fixture fallback. See [sprint contract](../sprint60/CONTRACT.md); cloud/native verification remains separate from unit/Emulator checks.
