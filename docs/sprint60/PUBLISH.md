# Lấy kế hoạch chung và ghép qua Git remote

Ba máy, ba clone. Không worktree. Những lệnh thực thi dưới đây là hướng dẫn cho nhóm; soạn kế hoạch không tự khởi chạy sprint.

## 1. Phát hành tài liệu

Bộ tài liệu nằm trên nhánh kế hoạch hiện có `demo90/plan`, trong `docs/sprint60/`. Chỉ commit/push Markdown của bộ mới; giữ nguyên `docs/sprint90/PLAN.md` để truy vết, không push main. Nếu tài liệu đã commit/push thì bỏ qua bước này, không tạo commit rỗng.

```sh
git status --short --branch
git branch --show-current
git add -- docs/sprint60
git diff --cached --check
git diff --cached --name-status
git commit -m "docs: plan mandatory mission and Nano Banana demo for three machines"
git push origin demo90/plan
git rev-parse HEAD
```

Chỉ chạy khi đang ở `demo90/plan`, mọi thay đổi staged đều là `docs/sprint60/*.md`, không có thay đổi khác. Gửi cả nhóm **SHA commit kế hoạch vừa push**; đó là PLAN_SHA cho các bước sau. Không dùng main cũ làm baseline thực thi và không dùng nhánh kế hoạch90 trước khi có sprint60.

## 2. Khởi tạo từng máy

Mỗi máy kiểm `git status` đầu tiên. Nếu dirty thì dừng để chủ máy xử lý; không stash/reset tự động. Clone chưa có thì dùng remote repo hiện hữu; không clone đè thư mục có công việc.

```sh
git status --porcelain=v1
git fetch origin
git show origin/demo90/plan:docs/sprint60/PLAN.md
git rev-parse origin/demo90/plan
```

So SHA remote với SHA kế hoạch nhóm nhận. Gán PLAN_SHA bằng hash thật, không giữ nguyên dấu `<...>`:

```sh
PLAN_SHA=<SHA_COMMIT_KE_HOACH_DA_XAC_MINH>
git merge-base --is-ancestor dd69975afbce05c8bd58fac36e0ac143ace22673 "$PLAN_SHA"
```

Mỗi máy chọn **một** lệnh ứng với vai trò của mình:

```sh
# Máy A
git switch -c demo60/ai "$PLAN_SHA"
# Máy B
git switch -c demo60/infra "$PLAN_SHA"
# Máy C
git switch -c demo60/mobile "$PLAN_SHA"
```

Nếu branch đã tồn tại local/remote, dừng rà owner/base/lịch sử trước khi dùng; không `switch -C`, `checkout -B`, reset hoặc force push. Không chạy cả ba lệnh trên cùng máy. Các nhánh demo90 cũ không dùng cho việc mới.

Sau khi mở Antigravity tại repo, dán đúng một câu sau cho máy tương ứng (agent sẽ đọc prompt đầy đủ trong repo):

- Máy A: **Đọc AGENTS.md, docs/sprint60/COMMON_PROMPT.md, PLAN.md, CONTRACT.md và A_BACKEND_AI.md; thực hiện vai trò A trong timebox 60 phút theo các file đó, bắt đầu bằng git status.**
- Máy B: **Đọc AGENTS.md, docs/sprint60/COMMON_PROMPT.md, PLAN.md, CONTRACT.md và B_FIREBASE_IMAGE.md; thực hiện vai trò B trong timebox 60 phút theo các file đó, bắt đầu bằng git status.**
- Máy C: **Đọc AGENTS.md, docs/sprint60/COMMON_PROMPT.md, PLAN.md, CONTRACT.md và C_MOBILE.md; thực hiện vai trò C trong timebox 60 phút theo các file đó, bắt đầu bằng git status.**

Các tên PLAN.md/CONTRACT.md/prompt riêng trong ba câu đều thuộc `docs/sprint60/`. Một người điều phối đặt mốc T0 chung khi cả ba đã đọc, xác nhận phân vai và có cùng PLAN_SHA; không đếm 60 phút riêng lệch nhau.

## 3. Push và đọc hợp đồng sớm

A commit contract riêng trước phút8; chỉ push `demo60/ai`. B/C fetch để đọc bằng `git show`, không merge branch A vào branch mình:

```sh
git fetch origin demo60/ai:refs/remotes/origin/demo60/ai
git show origin/demo60/ai:contracts/openapi.yaml
```

Mỗi người push đúng nhánh mình sau khi kiểm allowlist, không `git add .`, không push --all/--mirror, không force push. Cả ba báo SHA handoff tại phút35.

## 4. A ghép phút35–45

Working tree A sạch. A nhận AI_SHA/INFRA_SHA/MOBILE_SHA bằng hash handoff thật; fetch ba nhánh để có objects:

```sh
git fetch origin demo60/ai:refs/remotes/origin/demo60/ai demo60/infra:refs/remotes/origin/demo60/infra demo60/mobile:refs/remotes/origin/demo60/mobile
git rev-parse origin/demo60/ai origin/demo60/infra origin/demo60/mobile
```

Đối chiếu SHA, ancestor PLAN_SHA và `git diff --name-only PLAN_SHA SHA` theo bảng owner. Không merge remote tip mới nếu chưa bàn giao. Tạo integration từ PLAN_SHA đã chốt, **không dùng main**:

```sh
git switch -c demo60/integration "$PLAN_SHA"
git merge --no-ff <AI_SHA> -m "Merge demo60/ai"
git merge --no-ff <INFRA_SHA> -m "Merge demo60/infra"
git merge --no-ff <MOBILE_SHA> -m "Merge demo60/mobile"
```

Thay `<..._SHA>` bằng hash thật trước khi chạy. Nhánh integration đã tồn tại cần kiểm lịch sử, không ghi đè. Conflict thì abort merge, owner sửa ở nhánh riêng và push, A fetch/merge lại. Contract/source mismatch cũng do owner sửa, không chỉ ưu tiên ours/theirs.

Kiểm validator, backend tests/regression/Emulator và typecheck/lint; chạy script B và luồng native trên môi trường demo đã chốt. Các lệnh mới như `scripts/demo/start.sh` và `smoke_firebase.py` là việc B phải tạo, **hiện chưa tồn tại lúc soạn kế hoạch**, không trình bày như đã chạy.

Một backend/worker demo chung với cloud Firebase giúp điện thoại dùng đúng dữ liệu. Ba máy phát triển riêng không có nghĩa dựng ba backend production/cloud project. Unit/Emulator có thể riêng từng máy; không trộn chúng với cloud smoke.

Sau kiểm, A ghi evidence/CURRENT_STATE, commit trên integration và chỉ push rõ `origin demo60/integration`. Không merge/push main. Artifact chạy phải trùng SHA code/image digest đã smoke; commit tài liệu evidence sau build ghi riêng để không nói sai artifact.
