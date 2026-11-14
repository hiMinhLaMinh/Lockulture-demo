# C Mobile — sprint60 handoff

Trạng thái tổng: **PARTIAL / native + integration BLOCKED**. Không tuyên bố hoàn thành demo.
Chỉ sửa `mobile/**`, giữ nguyên `src/shared/theme/tokens.ts`. Không thêm dependency.
Baseline kế hoạch: `c1e1738`; ancestor `dd69975afbce05c8bd58fac36e0ac143ace22673` đã kiểm.
Nhánh thực thi/push duy nhất: `demo60/mobile`. Không merge/cherry-pick nhánh khác.
Không tạo `docs/sprint60/C_HANDOFF.md` vì yêu cầu trực tiếp giới hạn chỉ sửa mobile.

## Mốc và bằng chứng

| Mục | Kết quả | Commit / bằng chứng |
| --- | --- | --- |
| Mission HTTP + native GPS | PASS kiểm tĩnh; live BLOCKED | `d19a758`; typecheck/lint pass |
| Celebration + consent/portrait/souvenir | Đã triển khai; lint tại mốc này FAIL, đã sửa ở mốc sau | `0275883`; không dùng mốc này làm artifact nghiệm thu |
| Khóa API thật, retry/GPS tests | PASS kiểm tĩnh/unit | `b7868e3`; `npm run check` exit 0; `node --test tests/sprint60.test.cjs`: 11 pass, 0 fail |
| Code handoff | PASS typecheck/lint + 11 tests | `5948373475b571eedf9b2a79af82c16af874fa83`; `npm run check` exit 0; `node --test tests/sprint60.test.cjs`: 11 pass, 0 fail |
| Android export cuối | PASS đóng gói, không phải native evidence | Code `5948373`; `npx expo export --platform android --output-dir /tmp/lockulture-demo60-mobile-final-export` exit 0; 1984 modules, Hermes 5.5 MB |
| Backend local | BLOCKED | `curl --max-time 3 ... http://127.0.0.1:8080/health`: connection refused, HTTP 000 |
| A/B/integration | BLOCKED | `git fetch origin`, `git ls-remote --heads origin demo60/ai demo60/infra demo60/integration`: chưa có các refs ở lần kiểm này |
| Thiết bị/build native | BLOCKED | Không có `adb`/`xcrun` trong PATH; chưa có điện thoại/phiên verified/địa điểm thật được xác nhận; không có screenshot native |

## Đã triển khai

- Sáu mission operations theo OpenAPI + sprint60 CONTRACT: search POST/job GET/mission GET/active GET/hints POST/answer PUT. Runtime DTO validation, không fixture fallback. Search retry giữ key/body; đã biết job thì tiếp tục GET. Server `no_result` giữ mission cũ. Stage hiển thị từ Job; dừng search khi app xuống nền.
- Era/timeline và active mission lấy server, không dùng era fixture trong search. Maps link dùng tọa độ/place ID server. Không chốt địa danh ví dụ.
- Camera lấy foreground permission và GPS native; accuracy null, không finite, >50 m, tuổi >60s hoặc tương lai >5s báo lỗi. Tọa độ nhập tay chỉ tìm kiếm. Giữ ảnh khi GPS/HTTP fail. Lấy mẫu mới trước intent gửi đầu tiên; sau đó đóng băng GPS/body/key khi retry mạng. Chỉ sau intake từ chối rõ ràng mới cho lấy GPS và tạo intent mới.
- `/assets` multipart field `photo`; submission JSON gồm sáu field cũ và `capture_location`, `souvenir_opt_in`, `portrait_asset_id`. Không tự POST mới sau timeout. Refresh Auth 401 vẫn do HTTP client hiện có, giữ key.
- Verdict completed/accepted/retake_required/unidentified/not_matched/out_of_scope và các nhãn wrong_subject/out_of_radius/location_unverified có UI riêng; GPS intake 409 `location_out_of_range` và 422 có hướng khắc phục, giữ ảnh. Client không quyết định within-radius hoặc thưởng.
- Nút ảnh hoạt hoạ riêng mở consent native trước upload/gọi submission; opt-in mặc định false. Có camera portrait riêng khi ảnh cảnh thiếu người, upload riêng owner/session; không thay evidence. Body/consent không đổi dưới key đã gửi.
- Celebration chỉ mở từ completed + discovery server; đọc `/discoveries/{id}/celebration`, title/motif/era/summary/facts/source URLs từ server. Animation native tôn trọng reduced motion. Profile/timeline/active mission được invalidate, không cộng XP/mảnh/huy hiệu local.
- Souvenir queued/running/succeeded/failed/not_requested lấy celebration thật. Poll chỉ khi app foreground và route focus. Failed không xóa discovery/thưởng; không retry image provider từ client. Thành công lấy signed URL qua API, có nhãn AI, refresh khi hết hạn; không ảnh input/placeholder thay ảnh quà.
- Collection discovery detail tải celebration và URL mới khi mở lại. Chưa kiểm restart thật.
- API mode mặc định và từ chối cấu hình mock hoặc social fixture. `captureStore.settle` bị chặn trong API mode; result route API đọc discovery server, không đọc reward mock đã persist.

## Quét trước push

Chạy `rg -l 'fixture|mock|GEMINI_API_KEY|GOOGLE_MAPS_API_KEY|private_key' mobile --glob '!package-lock.json' --glob '!*.tsbuildinfo'` và rà diff.
Không thêm response mẫu/runtime fixture/câu chuyện/địa danh/ảnh quà mẫu vào code live. Doubles nằm riêng `tests/sprint60.test.cjs`, không được app import, không gọi provider.
**Repo baseline vẫn có thư mục mocks và các màn mock lịch sử**; grep toàn mobile không bằng 0. Sprint này khóa chúng khỏi cấu hình live, không tuyên bố đã xóa toàn bộ code mock lịch sử. Tọa độ điền sẵn/nút mẫu ở LocationInput đã xóa. Không tìm thấy server/admin secret marker trong phần triển khai mới.

## Chỗ lệch và YÊU CẦU CHO NGƯỜI KHÁC

- **A:** push SHA contract/OpenAPI 1.1 tương ứng sprint60, sáu mission routes, GPS intake và celebration. Chưa có SHA A để xác minh; adapter hiện theo `docs/sprint60/CONTRACT.md` và baseline OpenAPI (không tự sửa contract). ETA: cần trước khi nối API thật.
- **A:** CONTRACT giữ verdict `not_matched`, GPS ngoài radius là lỗi intake HTTP 409 `location_out_of_range`, GPS không hợp lệ là 422; không có ba verdict mới trong enum hiện hành. Mobile diễn giải các lỗi đó, đồng thời có nhãn UI nếu DTO trả tên người dùng yêu cầu; không đổi luật server.
- **A:** badge contract chỉ có id/title/motif/era/earned_at, không `svg_url`/`svg` hoặc title resource riêng. UI hiện dựng card huy hiệu từ nội dung server; yêu cầu SVG chính xác vẫn BLOCKED contract. Nếu cần SVG, A bổ sung đồng bộ schema/examples/acceptance rồi báo C.
- **A:** chỉ có GET celebration, không có route tạo ảnh sau completion. Mobile opt-in trước submission; nút riêng đặt consent trước request. Không tự invent POST souvenir. Nếu muốn opt-in muộn cần operation do A chốt.
- **B:** cung cấp một API URL demo điện thoại truy cập được, Firebase public app config và build/phiên verified được phép dùng; cloud private Storage + image model/worker thật. Không gửi server secrets cho C. ETA: trước native smoke.
- **Người thử/A/B:** cần điện thoại ở địa danh thật, quyền camera/GPS, ảnh có người dùng/portrait được phép; chạy đúng/sai ảnh/GPS, denied/accuracy/stale, retry mạng, background/foreground, reduced motion và restart app/backend đọc lại cả ảnh gốc/ảnh quà. Không tăng radius để vượt gate.
- **A integration owner:** cập nhật CURRENT_STATE/EVIDENCE sau nghiệm thu thực; C không sửa docs chung theo giới hạn người dùng.

Chưa chạy: Firebase/Emulator, Places/Gemini/Nano Banana thật, transaction/replay/ACL phía server, signed URL TTL trên cloud, native camera/GPS/geofence, screenshot và restart read-back. Unit tests/export không thay các bằng chứng này. Demo đầy đủ chưa PASS; ảnh Nano Banana vẫn là tiêu chí bắt buộc.

Artifact Android cuối (không phải APK/device build): `entry-e34fe10b0e2e4b594854b1fe88d42e42.hbc`; SHA256 `bef24972233a823370ce5efd41407ebfe5dd5ecfd09b25cd218f1566a6456119`. Commit báo cáo sau code không đổi artifact.
