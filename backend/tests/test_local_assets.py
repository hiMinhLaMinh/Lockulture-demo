from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image

from backend.src.assets_routes import MAX_BYTES
from backend.src.image_upload import normalize_image
from backend.src.main import create_app
from backend.src.platform_routes import require_actor


def photo_bytes(color="red"):
    output = BytesIO()
    Image.new("RGB", (1200, 600), color).save(output, format="PNG")
    return output.getvalue()


def test_normalizes_actual_image():
    data, width, height = normalize_image(photo_bytes(), 20_000_000)
    assert (width, height) == (1080, 540)
    with Image.open(BytesIO(data)) as image:
        assert image.format == "JPEG"
        assert not image.getexif()


def test_rejects_corrupt_and_oversized_upload(monkeypatch, tmp_path):
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("STORAGE_TYPE", "local")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path))
    app = create_app()
    app.dependency_overrides[require_actor] = lambda: str(uuid4())
    with TestClient(app, raise_server_exceptions=False) as client:
        headers = {"Idempotency-Key": str(uuid4())}
        corrupt = client.post("/api/v1/assets", headers=headers, files={"photo": ("photo.jpg", b"fake")})
        oversized = client.post("/api/v1/assets", headers=headers,
                                files={"photo": ("photo.jpg", bytes(MAX_BYTES + 1))})
    assert corrupt.status_code == 415
    assert oversized.status_code == 413
    assert list(tmp_path.iterdir()) == []
