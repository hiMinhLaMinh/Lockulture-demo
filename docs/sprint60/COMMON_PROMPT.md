# Dán khối này trước prompt A/B/C trên từng máy

```text
Bạn đang triển khai Lockulture bằng Antigravity trên một trong BA MÁY RIÊNG.
Sprint 60 phút, repo React Native/Expo mobile/ + FastAPI backend/ + Firebase.
Chỉ thực hiện vai trò được giao ở prompt riêng. Không worktree, không tạo agent
phụ, không sửa file của người khác. Ghép qua remote origin, không push main.

ĐỌC TRƯỚC KHI SỬA:
AGENTS.md; docs/implementation/{README,DECISIONS,TASKS,DATA_TRANSACTIONS}.md;
docs/CURRENT_STATE.md; firebase/README.md; contracts/acceptance.json;
docs/sprint60/{PLAN,CONTRACT}.md và prompt vai trò của bạn.
Nếu tài liệu cũ mâu thuẫn: yêu cầu người dùng mới đã chốt GPS arrival mission,
huy hiệu, fun fact và ảnh Nano Banana BẮT BUỘC. A phải cập nhật contract/schema/
examples/acceptance/docs luật đồng bộ; B/C không tự đổi luật hoặc DTO.

LUỒNG DUY NHẤT:
GPS → Places thật → Gemini sinh nhiệm vụ cho địa danh gần người thử → mở Maps →
tới nơi/chụp → GPS trong150m + ảnh đúng cảnh → server hoàn thành một lần →
huy hiệu/animation/kiến thức có nguồn → Nano Banana ảnh hoạt hoạ người dùng tại
địa điểm → private Storage + Firestore → mở lại vẫn xem ảnh quà được.
Ảnh Nano Banana không được cắt khỏi tiêu chí PASS. Ảnh quà là job riêng, không
chặn transaction thưởng. Không yêu cầu AI video, animation chúc mừng là UI native.

KHÔNG LÀM:
Không xây login/signup/reset-password; dùng phiên Firebase hiện có. Không bỏ Auth,
không dev actor/token ở live. Không social/feed/share/leaderboard/refactor.
Không fixture fallback, ảnh quà tạo sẵn, câu chuyện/địa danh/XP viết tay, không
upload mock store vào cloud. Test doubles chỉ trong unit/Emulator suite riêng.
Không anti-spoof, auto-post, Co-op, XP150. Giữ UI theo DESIGN_SYSTEM.

GPS không phải IP: lấy vị trí native mới lúc chụp. Bán kính150m, accuracy<=50m,
age<=60s ở intake, tương lai<=5s theo CONTRACT. IP chỉ tham khảo/unknown,
không chặn thưởng chỉ vì VPN/IP và không nhận IP máy backend là vị trí người dùng.
Chỉ nhập tay toạ độ để tìm, không giả hiện diện. Chọn một điểm thật gần người thử
trong5phút đầu; nếu không có người ở đó, ghi live geofence BLOCKED.

Địa danh hiện đại không gán vào triều đại cổ. Claim lịch sử phải có nguồn được
đối chiếu; không bịa URL. Ảnh cảnh thiếu người phải xin ảnh người dùng được đồng ý,
không bịa diện mạo. Không log/commit key, token, mật khẩu, GPS/ảnh/dump người thật.

GIT:
git status trước. Dirty ngoài tài liệu kế hoạch/việc của mình thì dừng báo rõ,
không reset/stash. Nhánh xuất phát cùng commit docs trên origin/demo90/plan
chứa sprint60, KHÔNG từ main cũ: A=demo60/ai, B=demo60/infra, C=demo60/mobile.
Xác minh main gốc dd69975afbce05c8bd58fac36e0ac143ace22673 là ancestor.
Nếu nhánh tên đó đã tồn tại/lịch sử khác thì dừng, không checkout -B/force push.
Push chỉ nhánh mình ít nhất mỗi10–15phút, báo SHA. Không merge/cherry-pick nhánh
người khác vào nhánh thực thi; git fetch + git show để đọc contract từ A là đủ.
A ghép trên demo60/integration, thứ tự ai → infra → mobile, đúng SHA bàn giao.

MỐC:
0–5 preflight/key/cloud/native/địa điểm. 5–8 A push contract; B/C đọc cùng SHA.
8–25 làm và smoke từng phần. 25–35 nối phần mình, push handoff.
35–45 A ghép, cả nhóm sửa blocker đúng owner. 45–55 E2E+restart/read-back.
55–60 khóa artifact và evidence. Đến60phút chưa đủ thì PARTIAL/BLOCKED, không giả PASS.

Chỉ sửa allowlist của mình. File thiếu hoặc tên khác phải đọc code thật trước,
ghi YÊU CẦU CHO OWNER nếu cần đổi ngoài phạm vi. Dependency Python gửi A;
dependency mobile chỉ C. Không cả hai cùng sửa schema/env/worker.

Báo ở phút5/8/25/35/45/55/60:
PASS/FAIL/BLOCKED từng mục | commit SHA | lệnh + evidence đã che secrets |
chưa kiểm | YÊU CẦU CHO OWNER + ETA.
Test phù hợp thay đổi, không gọi provider live trong test suite mặc định.
Contract validation/Emulator pass không thay bằng chứng cloud/native.
Không nói Firebase backup xong nếu mới chứng minh write/read sau restart.
```
