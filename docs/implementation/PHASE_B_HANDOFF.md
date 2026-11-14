# Bàn giao giai đoạn B

Staging dùng project `lockulture-f9c7d`. Bản triển khai sử dụng Firebase Auth, Firestore và Storage private. Luồng chụp ảnh API dùng assessment fixture bật tường minh và giới hạn bằng UUID nội bộ của tài khoản nghiệm thu.

## Local và Emulator

Từ repo root, cài `backend/requirements.txt`, pytest, Firebase CLI và JDK phù hợp với Emulator. Dùng project demo để cô lập dữ liệu. Firebase CLI truyền host Emulator cho tiến trình kiểm thử.

```sh
FIREBASE_PROJECT_ID=demo-lockulture ENV=test \
  firebase emulators:exec --project demo-lockulture --only auth,firestore,storage \
  'python -m pytest -q backend/tests'
docker build -f backend/Dockerfile -t lockulture-backend:b .
docker run --rm -p 8080:8080 lockulture-backend:b
```

Kiểm `curl -fsS http://localhost:8080/health` trong terminal khác. Chạy `npm ci`, `npm run typecheck` và `npm run lint` trong mobile với Node 24. Dev social fixture dùng `LOCKULTURE_SOCIAL_FIXTURES=1` và là chế độ riêng với luồng Firebase.

## Staging

1. Xác nhận billing, vùng Firestore và quyền deploy trong project. Bật Auth Email/Password, xác minh email, Firestore Native, Firebase Storage private, Cloud Run, Artifact Registry, Cloud Build, Cloud Tasks, Scheduler và IAM Credentials. Tạo bucket qua Firebase và lấy tên bucket thực. Bật uniform access và public access prevention.
2. Tạo ba service account riêng cho runtime, task và scheduler. Runtime cần `roles/datastore.user` trên project, `roles/storage.objectUser` trên bucket, quyền `iam.serviceAccounts.signBlob` trên danh tính ký, `roles/cloudtasks.enqueuer` và quyền actAs danh tính task. Để runtime tự ký, cấp `roles/iam.serviceAccountTokenCreator` cho runtime trên chính service account đó. Giữ các service agent mặc định của Cloud Tasks và Scheduler. Người deploy cần quyền actAs các danh tính mà mình gắn vào Cloud Run/Scheduler.
3. Chạy `firebase deploy --project lockulture-f9c7d --only firestore,storage`. Đợi indexes sẵn sàng. Dùng ADC đã cấu hình để chạy `FIREBASE_PROJECT_ID=lockulture-f9c7d python scripts/seed_eras.py`.
4. Build image từ root bằng Dockerfile ở bước local, push Artifact Registry và deploy theo digest. Cloud Run dùng runtime service account, timeout 180 giây, HTTPS và public ingress cho API mobile. Các route `/internal/*` tự xác thực OIDC và giới hạn danh tính theo chức năng. Cấu hình `ENV=staging`, `FIREBASE_PROJECT_ID=lockulture-f9c7d`, `STORAGE_TYPE=firebase`, `STORAGE_BUCKET`, `STORAGE_SIGNING_SERVICE_ACCOUNT`, `TASK_QUEUE_PATH`, `TASK_SERVICE_ACCOUNT`, `SCHEDULER_SERVICE_ACCOUNT` và `INTERNAL_AUDIENCE` theo URL Cloud Run. Không dùng file service-account trên Cloud Run.
5. Tạo queue ở vùng Cloud Run, `TASK_QUEUE_PATH=projects/lockulture-f9c7d/locations/<region>/queues/lockulture-jobs`. Tạo hai Scheduler HTTP jobs chạy mỗi phút, POST JSON `{}` tới `/internal/dispatch` và `/internal/maintenance`, dùng OIDC của scheduler và audience chính xác bằng URL dịch vụ. Cấu hình task HTTP timeout 180 giây do dispatcher gửi.
6. Tạo tài khoản thử và xác minh email. Dùng `GET /api/v1/me` lấy UUID nội bộ trước khi bật `ASSESSMENT_PROVIDER=fixture` và `FIXTURE_ACTOR_IDS` theo danh sách UUID phân cách dấu phẩy. Cấu hình Expo API mode với Firebase app config và HTTPS API. Tắt fixture sau nghiệm thu nếu môi trường được mở cho người dùng.

Ví dụ lệnh cho bước 4–5 sau khi đã tạo Artifact Registry, các service account và cấp IAM. Chạy từ repo root với các biến `REGION`, `REPOSITORY`, `BUCKET`, `RUNTIME_SA`, `TASK_SA`, `SCHEDULER_SA` đã điền.

```sh
PROJECT=lockulture-f9c7d
SERVICE=lockulture-staging
TAG=$(git rev-parse --short HEAD)
IMAGE="$REGION-docker.pkg.dev/$PROJECT/$REPOSITORY/backend:$TAG"
gcloud auth configure-docker "$REGION-docker.pkg.dev"
docker build -f backend/Dockerfile -t "$IMAGE" .
docker push "$IMAGE"
DIGEST=$(gcloud artifacts docker images describe "$IMAGE" --project "$PROJECT" \
  --format='value(image_summary.digest)')
gcloud tasks queues create lockulture-jobs --project "$PROJECT" --location "$REGION"
QUEUE="projects/$PROJECT/locations/$REGION/queues/lockulture-jobs"
gcloud run deploy "$SERVICE" --project "$PROJECT" --region "$REGION" \
  --image "${IMAGE%:*}@$DIGEST" --allow-unauthenticated --timeout 180 \
  --service-account "$RUNTIME_SA" \
  --set-env-vars "ENV=staging,FIREBASE_PROJECT_ID=$PROJECT,STORAGE_TYPE=firebase,STORAGE_BUCKET=$BUCKET,STORAGE_SIGNING_SERVICE_ACCOUNT=$RUNTIME_SA,TASK_QUEUE_PATH=$QUEUE,TASK_SERVICE_ACCOUNT=$TASK_SA,SCHEDULER_SERVICE_ACCOUNT=$SCHEDULER_SA"
URL=$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format='value(status.url)')
gcloud run services update "$SERVICE" --project "$PROJECT" --region "$REGION" \
  --update-env-vars "INTERNAL_AUDIENCE=$URL"
for endpoint in dispatch maintenance; do
  gcloud scheduler jobs create http "lockulture-$endpoint" --project "$PROJECT" --location "$REGION" \
    --schedule='* * * * *' --time-zone=Etc/UTC --http-method=POST \
    --uri="$URL/internal/$endpoint" --message-body='{}' --headers='Content-Type=application/json' \
    --oidc-service-account-email="$SCHEDULER_SA" --oidc-token-audience="$URL"
done
```

Với queue hoặc Scheduler job đã có, kiểm tra cấu hình hiện hành và dùng lệnh update tương ứng. Sau khi xác minh tài khoản, dùng `gcloud run services update` với `--update-env-vars "^|^ASSESSMENT_PROVIDER=fixture|FIXTURE_ACTOR_IDS=$ACTORS"`, trong đó `ACTORS` chứa các UUID phân cách bằng dấu phẩy.

## Phục hồi và giao diện cho C

- Outbox lưu generation và thời điểm có thể dispatch. Khi tạo task thành công nhưng mất phản hồi, dispatcher thử lại cùng tên và chấp nhận AlreadyExists. Scheduler tìm job hết lease để tạo generation mới hoặc đánh dấu failed. Khi debug, đối chiếu submission ID, job ID và generation trong Firestore/Cloud Logging. Dùng Scheduler Run now để chạy lại dispatcher và maintenance. Dùng API retry cho submission failed còn retryable.
- Worker nhận assessment theo schema `free-assessment.schema.json` hoặc `mission-assessment.schema.json`. Sau claim, adapter C dùng lease để dự trữ provider budget trước call, lưu checkpoint hợp lệ rồi gọi `award_result(job_id, lease_token, assessment)`. Result writer trả true khi commit thành công. Worker chỉ ghi checkpoint hoặc kết quả dưới lease hiện hành.
- Xác minh hai tài khoản thật trên hai thiết bị và tài khoản ngoài audience qua raw HTTP. Ghi commit/image digest, kết quả URL trước/sau hạn và ca phục hồi qua Scheduler trước khi xác nhận cổng B.

Xem [hiện trạng kiểm chứng](../CURRENT_STATE.md).
