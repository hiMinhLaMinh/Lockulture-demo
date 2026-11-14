# Máy C — Mobile nhiệm vụ, huy hiệu và ảnh quà

Dán [COMMON_PROMPT.md](COMMON_PROMPT.md) trước nội dung dưới; hoặc yêu cầu Antigravity đọc cả hai file trước khi thực hiện.

```text
VAI TRÒ C. Nhánh demo60/mobile. Bạn sở hữu Expo/React Native, không backend.
60phút, chỉ đường nhiệm vụ đã chốt, bắt buộc có ảnh Nano Banana thật cuối luồng.

ALLOWLIST:
mobile/** TRỪ mobile/src/shared/theme/tokens.ts (giữ design system)
docs/sprint60/C_HANDOFF.md (mới)
CẤM sửa backend/, firebase/, contracts/, env backend/docs chung hoặc ngoài allowlist.
Chỉ bạn sửa mobile/package.json và package-lock.json nếu cần dependency thực sự.
Không thêm thư viện bản đồ/animation mới nếu expo-linking/Animated hiện có đủ dùng.

0–8 PHÚT: THIẾT BỊ VÀ HỢP ĐỒNG
- Đọc code thật, app native phải chạy, phiên Firebase verified đã đăng nhập.
  Không viết login/signup/reset, không bỏ route guard hay nhét dev token vào live.
  Nếu thiếu phiên dùng UI Auth hiện có trước demo, báo blocker, không bypass.
- Xác nhận một địa danh gần người thử có thể tới trong giờ. Cầu Rồng chỉ là ví dụ.
  Người thử cần điện thoại ở vị trí thật, không nhập tọa độ mẫu để gọi đó là GPS.
- A push contract phút8: fetch demo60/ai rồi git show file contract/OpenAPI ở SHA
  đã báo để đọc, không merge/cherry-pick cả backend vào nhánh mobile.
- Dùng EXPO_PUBLIC_DATA_SOURCE=api, API URL B cung cấp và Firebase public config.
  Không Gemini/Maps server key hoặc credential Admin trong mobile.

8–25 PHÚT: MISSION API VÀ CAPTURE LOCATION
- mobile/src/services/index.ts apiMissionService.search còn notIntegrated: thêm
  adapter/hook HTTP và DTO validation theo A; giữ screens/theme/router hiện có.
- POST /mission-searches→GET job→GET Mission, render clue/hints/criteria/era/
  arrival_radius_m. Hints/answer gọi API đã có trong OpenAPI, không mock hoặc model.
- Mở Google Maps bằng location/place ID thật qua link, không thêm SDK Maps native
  hoặc API key server vào app. Không coi location bias của search là arrival pass.
- expo-location đã có: xin quyền foreground, lấy location mới lúc chụp/nộp, gồm
  lat/lng/accuracy/timestamp; accuracy null hoặc thiếu quyền phải lỗi rõ, không điền0.
  Tọa độ nhập tay vẫn dùng tìm điểm, không làm capture_location GPS. Hiển thị
  hướng dẫn lấy vị trí tốt hơn nếu kém chính xác/quá cũ, không fake inside-radius.
- Capture camera hiện có, upload ảnh thật /assets rồi submission mode=mission với
  mission ID/version, session và GPS snapshot. Idempotency key ổn định khi retry
  mạng; timeout không tự tạo submission mới. Không đổi body dưới key cũ.
- Opt-in ảnh hoạt hoạ minh bạch trước khi gửi ảnh; đầy đủ demo phải opt-in true.
  Ảnh có người dùng trước địa danh có thể dùng trực tiếp; nếu chỉ có cảnh thì
  cho chụp thêm portrait_asset_id riêng cùng owner. Không bịa diện mạo/nhân vật.

25–35 PHÚT: RESULT, HUY HIỆU VÀ ẢNH QUÀ
- Poll submission theo cadence hiện có, dừng background; failed/error trung thực,
  giữ ảnh khi lỗi. GPS sai/ảnh sai không animation hoặc tự cộng XP.
- Chỉ server verdict completed + discovery có thật mới mở celebration. Refetch
  profile/timeline, không tăng XP/mảnh/badge ở client.
- GET /discoveries/{id}/celebration: render badge title/motif/era từ server. Dùng
  teal/gold hiện có, card huy hiệu đẹp + hiệu ứng scale/confetti gọn qua animation
  sẵn có. Tôn trọng reduced motion, không thêm asset giả để chứng minh badge có thật.
- Hiển thị summary/fun_facts/era và source links của server. Công trình đương đại
  không tô thành triều đại cổ; UI không thêm ngày/năm/claim ngoài dữ liệu đã kiểm.
- Poll souvenir job trạng thái thật qua celebration: queued/running/succeeded/failed.
  Loading nói đang tạo ảnh, không phần trăm/timer giả. Animation chúc mừng có thể
  chạy khi thưởng đã commit nhưng không nói ảnh đã có lúc job còn running.
- Khi succeeded: lấy asset_id→/assets/{id}/url, render ảnh Nano Banana mới + nhãn
  ảnh hoạt hoạ AI. URL60s hết hạn phải lấy lại qua API, không lưu URL public dài hạn.
  Failed hiển thị lỗi; không ảnh input/placeholder thay ảnh quà thành công.
- Quay lại/mở app lấy completion+URL mới từ server. Không chỉ giữ local URI của
  ảnh quà. Có thể mở từ discovery detail hiện có, không làm gallery hệ thống lớn.
- Typecheck/lint, push demo60/mobile + C_HANDOFF trước phút35. Ghi device/build,
  API contract SHA, tests, phần còn blocked, reproduction cho owner A/B.

35–55 PHÚT: KIỂM TRÊN BẢN GHÉP
- Dùng backend integration A/B, không trỏ mỗi bước sang backend khác dữ liệu.
  Nếu cần xem integration, dùng clone mình và chỉ chuyển nhánh lúc sạch;
  sửa code vẫn ở demo60/mobile, không sửa chồng backend/contract trong integration.
- Chạy GPS thật→tìm nhiệm vụ→mở Maps→chụp→completion→badge/animation/fun fact→
  ảnh quà mới; thử denied permission/poor accuracy/out-of-radius/wrong photo,
  retry mạng và app background/foreground. Không cần làm social/login feature.
- B restart tiến trình demo, bạn restart app: tìm discovery/celebration cũ, lấy
  URL mới và hiển thị ảnh quà thật. Ghi evidence trên điện thoại vật lý;
  browser/Expo export không chứng minh native camera/GPS hoạt động.
- Nếu API sai gửi A reproduction/DTO đã che dữ liệu nhạy cảm; ảnh/URL lỗi gửi B.
  Không chữa bằng fixture, hardcode data hoặc đổi schema backend trên nhánh C.

55–60 PHÚT: CHỐT
- Typecheck/lint lại khi có sửa liên quan, ghi output/build/thiết bị và SHA.
  Gửi A kết quả toàn luồng và ảnh quà có đọc lại sau restart không.
- Chưa đủ Nano Banana/GPS thật thì full demo PARTIAL/BLOCKED, không tự cắt ảnh quà
  hoặc chỉ trình diễn animation rồi nói đã sinh ảnh.
- Push chỉ demo60/mobile, không main, không nhánh A/B/integration.

XONG KHI: người dùng đã có phiên đi hết đường nhiệm vụ thật, kết quả/huy hiệu/
kiến thức do server, animation native đẹp và ảnh Nano Banana cloud xem lại được;
typecheck/lint pass, không secrets/mocks trong live và có bằng chứng thiết bị.
```
