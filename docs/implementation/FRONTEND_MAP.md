# Bản đồ nối frontend

[Chỉ mục](README.md). Giữ phong cách UI và route hiện tại; thay nguồn dữ liệu qua service/hook. Target DTO ở OpenAPI snake_case; chỉ mapper đổi camelCase.

| UI/feature hiện tại | Service/endpoint mục tiêu | Mutation xong refresh |
|---|---|---|
| Auth/login/register/forgot (còn scaffold) | Firebase SDK + GET /me | Clear cache khi identity đổi |
| Profile/edit (edit còn scaffold) | GET/PATCH /me | me, feed author, leaderboard |
| Explore/timeline | GET /timeline, /missions/active | timeline, activeMission |
| Missions search | POST/GET /mission-searches | mission và active khi ready |
| Mission detail | GET /missions/{id}, POST hints, PUT answer | mission cùng ID |
| Camera/preview | POST /assets → POST /submissions → GET | submission/session |
| Result/collection | GET /submissions/{id}, /discoveries | discoveries, timeline, me, leaderboard, activeMission |
| Compose | friends/groups queries → POST /posts | feed, group feeds/counts |
| Feed/post detail (detail còn scaffold) | GET /posts, /posts/{id}, /assets/{id}/url | posts/by-ID |
| Friends/profile | users/friends/friend-requests | friends, requests, user relation, leaderboard |
| Groups/detail/create | groups/members, post shares | groups, members, group feed/count |
| Reactions/comments | reaction PUT/DELETE, comments GET/POST/DELETE | post counts, comments |
| Leaderboard | GET /leaderboard | khi XP/friendship thay đổi |

## State cần refactor

- app-store: bỏ mockUser auth, XP/active mission authoritative; giữ selectedEra và UI draft. Session SDK riêng. Không trộn identities trong query keys.
- capture-store: local draft/file/upload state; server trả discovery/XP/fragment. Xóa logic client settle cấp thưởng khi API mode. Mỗi draft giữ upload idempotency key, submission key, server IDs để resume, không sinh key mới khi retry.
- social-store: mock adapter riêng; API mode mọi CRUD là mutation có pending/error, không đổi local trước server mà không rollback.
- feed-interaction-store: chỉ mock; API mode dùng server my_reaction/counts và comments. Fixture Minh An chỉ mock, không xuất hiện API mode.
- Domain MissionSearchInput thêm location_source/expected_active_mission_id; CaptureDraft không gửi owner/mission snapshot làm sự thật. API không nhận scenario.
- AsyncStorage query cache và drafts theo user; signout xóa bộ nhớ và drafts nhạy cảm. Không migrate demo posts/XP lên account thật.

## UI lỗi/chờ/khôi phục

Mọi mutation có loading/disabled tránh double tap, nhưng server vẫn idempotent. Lỗi giữ draft; thành công mới clear. Lost response replay POST cùng key để lấy ID nếu chưa nhận được; đã có ID thì GET resource, không đoán thành công. Không có endpoint tra cứu arbitrary key. 401 refresh một lần; 409 mission/session đưa về đúng mục tiêu hoặc mở kết quả cũ; 429 hiển thị thời gian retry; 404 quyền bài thay đổi thì bỏ cache bài/ảnh.

Render signed image bằng asset_id → URL query, cache không quá expires_at; file local để preview trước upload. Không persist URL có hạn như ảnh vĩnh viễn. Khi app background dừng camera/poll; foreground lấy lại trạng thái thay vì bắt đầu job mới.

## Những màn hình cần hoàn thiện thêm

Auth forms/callback, edit profile, discovery detail, post detail và trạng thái paginated feed chưa hoàn chỉnh trong scaffold. Agent không được coi “route tồn tại” là feature đã hoàn thành. Điều hướng giữ ba tab và bottom bar Friends/Groups/Leaderboard; không đưa thanh tab vào camera.

Nội dung giới thiệu/câu chuyện của era có thể giữ catalog tĩnh trên mobile theo era ID; trạng thái/mảnh/XP luôn lấy API. Không coi narrative tĩnh là tiến trình đã mở khóa.
