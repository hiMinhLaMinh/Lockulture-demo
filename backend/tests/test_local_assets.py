import hashlib
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.src import assets_routes
from backend.src.main import create_app


class Snapshot:
    def __init__(self, value):
        self._value = value
        self.exists = value is not None

    def to_dict(self):
        return self._value


class Document:
    def __init__(self, rows, key):
        self._rows = rows
        self._key = key

    def get(self):
        return Snapshot(self._rows.get(self._key))

    def set(self, value):
        self._rows[self._key] = value

    def update(self, values):
        self._rows[self._key].update(values)


class Collection:
    def __init__(self, rows):
        self._rows = rows

    def document(self, key):
        return Document(self._rows, key)


class FakeDb:
    def __init__(self):
        self.assets = {}

    def collection(self, name):
        assert name == "assets"
        return Collection(self.assets)


@pytest.fixture
def local_backend(monkeypatch, tmp_path):
    db = FakeDb()
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("STORAGE_TYPE", "local")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path))
    monkeypatch.delenv("LOCKULTURE_SOCIAL_FIXTURES", raising=False)
    monkeypatch.setattr(assets_routes, "get_db", lambda: db)
    app = create_app()
    app.dependency_overrides[assets_routes._actor] = lambda: "00000000-0000-4000-8000-000000000001"
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client, db


def create_asset(client, content):
    return client.post(
        "/api/v1/assets",
        headers={
            "Authorization": "Bearer lockulture-dev-A",
            "Idempotency-Key": str(uuid.uuid4()),
        },
        json={
            "mime_type": "image/jpeg",
            "byte_size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "width": 1,
            "height": 1,
        },
    )


def test_local_asset_upload_and_private_read(local_backend):
    client, db = local_backend
    content = b"private image bytes"

    created = create_asset(client, content)
    assert created.status_code == 201
    asset_id = created.json()["asset_id"]

    uploaded = client.put(
        created.json()["upload_url"],
        headers={"Authorization": "Bearer lockulture-dev-A", "Content-Type": "image/jpeg"},
        content=content,
    )
    assert uploaded.status_code == 204
    assert db.assets[asset_id]["state"] == "ready"

    signed = client.get(
        f"/api/v1/assets/{asset_id}/url",
        headers={"Authorization": "Bearer lockulture-dev-A"},
    )
    assert signed.status_code == 200, signed.text
    image = client.get(signed.json()["url"])
    assert image.status_code == 200
    assert image.content == content
    assert image.headers["cache-control"] == "no-store"

    tampered = client.get(signed.json()["url"] + "&signature=invalid")
    assert tampered.status_code == 404


def test_local_asset_rejects_mismatched_upload(local_backend):
    client, db = local_backend

    created = create_asset(client, b"expected bytes")
    asset_id = created.json()["asset_id"]
    uploaded = client.put(
        created.json()["upload_url"],
        headers={"Authorization": "Bearer lockulture-dev-A", "Content-Type": "image/jpeg"},
        content=b"different bytes",
    )
    assert uploaded.status_code == 409
    assert db.assets[asset_id]["state"] == "pending"
