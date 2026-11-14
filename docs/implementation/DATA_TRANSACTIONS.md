# Firestore: collections và transaction

[Quyết định](DECISIONS.md) · [Firebase](../../firebase/README.md). Timestamp lưu Firestore Timestamp, API trả ISO UTC. Tài nguyên API dùng UUID nội bộ; Auth UID được mapping theo AUTH_PERMISSIONS. Mọi document có schema_version=1.

## Mô hình document

| Collection | ID và nội dung chính |
|---|---|
| auth_identities | SHA256 Firebase UID → user_id; chỉ server đọc |
| profiles, usernames | profiles/{UUID}: tên, username,bio,xp_total,active_mission_id,active_search_id; usernames/{name}: owner_id |
| eras | Canonical era ID, name,period,sort_order,fragment_goal |
| friend_pairs | hash của hai UUID đã sort: users,status,pending_request_id; điểm tranh chấp chung của mọi thay đổi quan hệ |
| friend_requests | UUID, sender_id,recipient_id,status,created_at |
| groups | UUID, owner_id,name,deleted_at,members map user_id → membership UUID; tối đa20 |
| missions | UUID, toàn Mission DTO + owner_id,search_id,created_at |
| assets | UUID,owner_id,object_path,sha256,mime_type,byte_size,width,height,state,created_at |
| evaluation_sessions | UUID,owner_id,mode,mission_id,status,evidence_count,last_submission_id,expires_at |
| submissions | UUID, owner_id,session_id,asset_id,job_id,sequence,status,verdict,knowledge,instruction,discovery_id,error |
| jobs, job_outbox | UUID: input,status,stage,counters,attempts,deadline,lease,checkpoint; outbox cùng ID có generation,delivered_at,dispatch_after |
| discoveries | UUID, owner_id,submission_id,asset_id,mission_id,mode,subject_key,era_id,knowledge,reward_reason,fragment_added |
| reward_ledger | SHA256(owner_id + reward_key),discovery_id,xp,created_at |
| era_progress | SHA256(owner_id + era_id), subject_keys tối đa3, discovery_ids,fragment_count |
| posts | UUID,discovery_id,author_id,asset_id,caption,created_at,deleted_at; direct_user_ids và group_grants map group_id → snapshot membership IDs |
| published_discoveries | discovery UUID → post_id; unique reservation không xóa khi soft-delete bài |
| reactions | SHA256(post_id+user_id),reaction,updated_at |
| comments | UUID,post_id,author_id,text,created_at,deleted_at |
| idempotency_keys | SHA256(actor+operation+key),request_hash,response,status_code,expires_at,upload reservation lease |
| rate_windows | SHA256(actor+operation+UTC hour),used |

Hash composite phải dùng encoding JSON array chuẩn, không nối chuỗi mơ hồ. Backend validate fields theo OpenAPI; Firestore không tự enforce FK/schema/unique. Lưu discovery UUID bằng submission UUID để chống worker tạo bản thứ hai; mission completion đọc/ghi mission trong cùng transaction.

## Transaction bắt buộc

Tất cả read trước write; callback có thể chạy lại, không gọi AI/Maps/Storage/Tasks bên trong. SDK retry contention có giới hạn; hết retry trả lỗi có thể thử lại với cùng idempotency key. [Quy tắc Firestore](https://firebase.google.com/docs/firestore/manage-data/transactions).

- Intake: đọc idempotency/quota/profile/session/asset/mission; kiểm owner,mode,version,expiry,expected previous; ghi submission/job/outbox/session/quota và response đồng thời. Một inflight/session; session giữ last_submission_id. Profile giữ active search để chặn tìm đồng thời.
- Search commit: đọc profile và expected active mission, không thay mission đang được đánh giá; old→replaced, new→active và profile/job cùng transaction. no_result giữ mission cũ.
- Award: đọc job lease,session,mission,discovery,ledger,profile,era_progress trước ghi. Thưởng free20 một lần/subject/ngày Việt Nam theo submission.created_at; mission100 một lần. Ledger document xác định chống trùng; chỉ tăng xp_total khi tạo ledger mới. Fragment unique subject, cap3. Lưu discovery, đóng session/mission và job cùng transaction.
- Canonical subject: mission place:<Maps ID>; free category + tên chuẩn NFKD bỏ dấu/lowercase/collapse spaces, street thêm locality. Đây là heuristic MVP, không bảo đảm định danh toàn cầu.
- Publish: đọc friend_pairs và groups để xác thực toàn bộ recipients; snapshot members map tối đa10nhóm×20người trong một Post, direct tối đa50. Ghi post + published_discoveries + idempotency đồng thời. Membership thay đổi làm transaction retry; không fan-out hàng trăm document trong transaction.
- Read ACL: group_grants phải chứa user với membership UUID đúng groups.members hiện tại; group chưa xóa. Direct grant hoặc author độc lập. Thêm group đã có là no-op, không mở rộng snapshot cũ.
- Quản lý bạn/nhóm: mọi friend request/accept/remove cùng sửa friend_pairs; group membership changes cùng sửa groups. Kiểm owner, accepted friends và giới hạn20 dưới transaction.
- Reaction/comment ghi cùng kiểm quyền post; counters tổng hợp phải transaction trên post hoặc tính từ records. Không cộng XP. Leaderboard dùng xp_total được duy trì cùng ledger, kiểm đối soát khi test.

## Query và pagination

MVP có thể quét posts theo created_at DESC/document ID DESC rồi lọc ACL server theo từng batch đến khi đủ page hoặc hết dữ liệu; cursor chứa vị trí scan cuối, không chỉ bài cuối thấy được. Không trả counts/cursor nội dung bí mật. Đây là lựa chọn đơn giản cho demo, cần tối ưu khi dữ liệu lớn. Friends/requests/groups query theo actor; tìm tên dùng normalized fields và lọc server cho dữ liệu MVP; không giả Firestore có full-text search/SQL JOIN.

Thành viên dữ liệu phải tạo firestore.indexes.json từ query thực tế (owner+created_at, post+created_at, participant/status, job status/deadline), kiểm Emulator và staging, commit indexes cùng query. Chưa có bộ index được kiểm chứng ở đợt tài liệu này.

Cleanup đánh dấu asset deleting dưới transaction, xóa object ngoài transaction rồi đánh dấu deleted. Không xóa asset gắn discovery. TTL xóa trễ nên mọi read/retry phải tự kiểm expires_at; không dựa vào TTL để thu hồi quyền hoặc đóng session đúng hạn.


## Sprint60 — contract 1.1.0

Mission requires native capture GPS at intake: radius 150m, accuracy <=50m, age <=60s, future <=5s. This supersedes the previous no-GPS mission rule; it is not anti-spoof protection. Free mode is unchanged. Persist the immutable location/config/mission-version snapshot; inference latency does not age it again.

Completion atomically writes the existing +100 ledger/discovery/progress, deterministic earned badge, mission_completions and optional souvenir job/outbox. Read all reservations before writes. Souvenir reserves one image call separately from vision1; checkpoint and asset publication require the current lease. Image failure keeps rewards. Owner-only GET celebration never creates jobs; private attached assets use existing 60s signed URLs.

Search/submission/souvenir workers share dispatch, leases and recovery, with kind-specific counters. Live uses real providers without fixture fallback. See [sprint contract](../sprint60/CONTRACT.md); cloud/native verification remains separate from unit/Emulator checks.
