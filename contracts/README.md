# Contract Lockulture v1.0.0

Thiết kế đã chốt, chưa phải API runtime. Bắt đầu bằng [implementation pack](../docs/implementation/README.md).

| Artifact | Vai trò |
|---|---|
| [openapi.yaml](openapi.yaml) | OpenAPI3.1: endpoints, request/response, nullable/required/error |
| [fixtures/config.json](fixtures/config.json) | Hằng số luật/quota/retention |
| [fixtures/eras.json](fixtures/eras.json) | Catalog 10 era, IDs giống frontend hiện tại |
| [fixtures/identities.json](fixtures/identities.json) | A/B/C/D tổng hợp cho kịch bản, không tài khoản Auth thật |
| [examples](examples/) | Payload hợp lệ/không hợp lệ dùng test parser/mapper; mỗi file là một ví dụ độc lập |
| [ai](ai/) | Model output schema và prompt/semantic validation |
| [acceptance.json](acceptance.json) | Given/when/then phủ43 operation và bất biến; chưa phải executable HTTP test runner |
| [environment.example](environment.example) | Tên cấu hình mục tiêu, chỉ placeholder |


## Kiểm tra

```bash
python -m pip install -r scripts/contract/requirements.txt
python scripts/contract/validate.py
```

Chạy từ repo root trong venv. Validator kiểm OpenAPI, payloads, AI schemas, operation coverage, catalog/config và liên kết nội bộ. Kiểm thử Emulator cần xây theo [hướng dẫn](../firebase/README.md). Không chạy contract này thay cho backend test hiện hành rồi kết luận handlers đã làm xong.


Thiết kế dữ liệu hiện hành ở [firebase/README](../firebase/README.md). Dữ liệu ví dụ là synthetic; tài khoản staging tạo qua Firebase Auth và map UID sang UUID API. Không áp dụng SQL cũ. Đổi contract phải cập nhật examples, model dữ liệu, rules và acceptance đồng bộ.
