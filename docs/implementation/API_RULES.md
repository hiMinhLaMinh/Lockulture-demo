# Quy ước HTTP và semantics bổ sung

[OpenAPI v1](../../contracts/openapi.yaml) là nguồn field/type/required/null/status thành công. Base `/api/v1`; health cũng nằm dưới prefix này trong target, giữ /health cũ làm alias khi migrate.

## Validation và lỗi

Trim tên/username/caption/comment; username ASCII lowercase; độ dài tính Unicode code points như Python (backend), frontend dùng Array.from để kiểm tra (JS .length là UTF-16). Empty PATCH /me -> 422. UUID/enum/field thừa bị từ chối, tọa độ NaN/Infinity không hợp lệ. Không tự đổi thời kỳ, đảo tọa độ hoặc im lặng bỏ recipient sai.

| HTTP | error.code | retryable |
|---|---|---|
| 401 | unauthorized | false; refresh token ở client một lần |
| 403 | forbidden | false |
| 404 | not_found | false |
| 409 | conflict, idempotency_conflict, mission_inactive, session_closed | false |
| 422 | validation_error | false |
| 413/415 | asset_invalid | false |
| 429 | rate_limited | true, Retry-After seconds |
| 502/503 | provider_failed | true |
| 504 | deadline_exceeded | true |
| 500 | internal_error | false, request_id để tra log |

Với lỗi nằm trong Job/Submission, retryable còn phụ thuộc attempts/deadline/tool budget hoặc checkpoint: provider_failed có thể false nếu không còn cách retry an toàn. Upload reservation đang có lease trả409 conflict retryable=true và Retry-After2; đây là ngoại lệ conflict ở bảng trên.

Không trả stack trace/secret. FastAPI RequestValidationError và HTTPException phải map về Error schema, không để default `detail` lẫn schema. GET job/submission terminal failed vẫn 200 với error trong resource; không nhầm với lỗi GET transport.

## ID, idempotency và pagination

- Idempotency-Key UUID bắt buộc trên mutation, kể cả DELETE/PUT. Scope `(actor,operationId,key)`, hash canonical body và path params; multipart hash normalized image bytes. Đọc key document, kiểm tra rồi ghi response trong cùng transaction. Request song song tranh chấp cùng document; Firestore retry transaction rồi đọc response cũ. Body khác -> 409. 204 lưu JSON null và status 204 trong DB; lúc trả HTTP không có body.
- Cache kết quả thành công và terminal business conflict; rollback key đối với lỗi transient trước commit. Job enqueue và outbox cùng transaction. Job POST replay trả response đã lưu rồi client GET để lấy trạng thái mới.
- Sau 7 ngày key có thể hết hạn nhưng unique mission completion/post discovery vẫn chống lặp lâu dài.
- Pagination mặc định 20, max 50, cursor opaque base64url JSON chứa last sort tuple + hash filter; reject cursor sai/filter khác -> 422. Feed/comment/discovery/group/request sort created_at DESC,id DESC. Users/friends sort username ASC,id ASC. Timeline trả cả 10, next_cursor null; leaderboard trả toàn scope theo XP DESC,username ASC,id ASC (MVP, không pagination).
- GET /users yêu cầu query >=2 ký tự sau trim, tìm tên bỏ dấu hoặc username; loại actor. Public XP được xem trong profile của người dùng tìm thấy; không lộ email.

## Quan hệ và nhóm

- Cross friend request khi đã có pending ngược: 409, client hướng đến tab lời mời, không tự accept. Accepted friendship exists -> 409. Terminal request không tái sử dụng; gửi lại tạo request mới.
- DELETE friendship không xóa nhóm hoặc direct grants. Idempotent nếu đã xóa. Accept transaction cập nhật request và upsert canonical low/high pair.
- Group create bao gồm owner và tối đa 19 friend IDs. Add member yêu cầu owner, mọi target là accepted friend, distinct union <=20. Add existing member là no-op. Không chuyển owner. Nonowner chỉ DELETE chính mình; owner DELETE mình -> 409.
- Group delete soft-delete; giữ posts/discoveries, group grant vô hiệu. Group list/count chỉ active membership và nhóm chưa xóa. post_count đếm theo quyền actor, không tổng bí mật.

## Bài và phản hồi

- POST /posts cùng discovery khác key sau khi đã đăng -> 409; client mở post cũ. Author chọn đủ recipient ban đầu, không API bổ sung direct recipient sau xuất bản trong MVP.
- /shares chỉ thêm nhóm chưa có; nhóm đã chia sẻ không tạo lại snapshot kể cả member mới. Không khôi phục quyền cũ khi rejoin.
- `audience` trả IDs thực tế chỉ cho author; các viewer khác nhận null. Những ID lịch sử không còn hoạt động có thể vẫn có trong audience của author, backend không cấp quyền chỉ dựa vào field này.
- DELETE Post/comment soft-delete, lần hai trả 204 cho owner. Comment deletion cho author kể cả mất quyền đọc bài. Counts chỉ gồm comments chưa xóa; reaction counts tính theo các hàng hiện có, giữ phản hồi cũ khi một người rời nhóm (không tự xóa lịch sử).
- XP trong User response phải lấy từ ledger cùng nguồn với /me/leaderboard. Chia sẻ/comment/reaction không ảnh hưởng ledger.

Job/Submission dùng field `error: ErrorDetail | null` trực tiếp, không lồng `{error:{error:...}}`. HTTP lỗi bên ngoài dùng envelope Error. getActiveMission trả200 JSON null khi không có; không dùng404. Job.resource_id khi search succeeded là mission ID; no_result không có ID, UI dùng thông báo không tìm được nhiệm vụ. GET users/friends không trả email hay quan hệ suy đoán; UI kết hợp friends/request collections để hiển thị nút quan hệ, tải đủ trang cần thiết.
