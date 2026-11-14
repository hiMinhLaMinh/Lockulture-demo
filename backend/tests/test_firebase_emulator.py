"""Firebase Emulator integration tests — Giai đoạn B.

Yêu cầu: Firebase Local Emulator Suite đang chạy.
Chạy:
  firebase emulators:start --only firestore,auth,storage
  FIRESTORE_EMULATOR_HOST=localhost:8080 FIREBASE_AUTH_EMULATOR_HOST=localhost:9099 \\
  FIREBASE_STORAGE_EMULATOR_HOST=localhost:9199 FIREBASE_PROJECT_ID=lockulture-dev \\
  ENV=test pytest backend/tests/test_firebase_emulator.py -v

Tests này KHÔNG chạy trong CI thông thường; cần Emulator.
Skip tự động nếu FIRESTORE_EMULATOR_HOST chưa set.
"""
import os
import pytest

EMULATOR_HOST = os.getenv("FIRESTORE_EMULATOR_HOST")

pytestmark = pytest.mark.skipif(
    not EMULATOR_HOST,
    reason="FIRESTORE_EMULATOR_HOST not set; skip Emulator tests"
)


@pytest.fixture(scope="module")
def db():
    from backend.src.firebase import get_db
    return get_db()


@pytest.fixture(scope="module")
def repo():
    from backend.src.firestore_repo import FirestoreRepository
    return FirestoreRepository()


def test_emulator_connection(db):
    """Confirm Emulator is reachable."""
    ref = db.collection("_health_check").document("ping")
    ref.set({"ok": True})
    snap = ref.get()
    assert snap.to_dict()["ok"] is True
    ref.delete()


def test_atomic_write_and_read(repo):
    """atomic() writes are visible via read()."""

    collection = "_test_atomic"
    key = "row1"

    def write(tx):
        tx.put(collection, key, {"value": 42})

    repo.atomic(write)

    def read_back(tx):
        return tx.get(collection, key)

    result = repo.read(read_back)
    assert result["value"] == 42

    # Cleanup
    from backend.src.firebase import get_db
    get_db().collection(collection).document(key).delete()


def test_atomic_idempotency(repo, db):
    """Idempotency key stored in Firestore prevents double-write."""
    from uuid import uuid4
    from backend.src.social.core import mutate

    actor = "test-actor-idem"
    key = str(uuid4())
    calls = []

    def operation(tx):
        calls.append(1)
        tx.put("_test_idem", "result", {"done": True})
        return {"result": "ok"}

    result1 = mutate(repo, actor, "testOp", key, ["/test"], None, 200, operation)
    result2 = mutate(repo, actor, "testOp", key, ["/test"], None, 200, operation)

    # Operation should only be called once; second call returns cached result
    assert result1["body"] == result2["body"]
    assert len(calls) == 1

    # Cleanup
    from backend.src.social.core import digest
    db.collection("idempotency_keys").document(digest([actor, "testOp", key])).delete()


def test_transaction_contention(repo):
    """Concurrent atomics on the same key succeed via retry."""
    import threading

    results = []
    errors = []
    collection = "_test_contention"
    counter_key = "counter"

    # Initialize
    repo.atomic(lambda tx: tx.put(collection, counter_key, {"n": 0}))

    def increment():
        from time import sleep

        from backend.src.social.core import SocialError

        def op(tx):
            row = tx.get(collection, counter_key)
            tx.put(collection, counter_key, {"n": row["n"] + 1})

        for attempt in range(3):
            try:
                repo.atomic(op)
                results.append(1)
                return
            except SocialError as exc:
                if exc.status != 503 or attempt == 2:
                    errors.append(exc)
                    return
                sleep(0.05 * (attempt + 1))

    threads = [threading.Thread(target=increment) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Errors: {errors}"
    final = repo.read(lambda tx: tx.get(collection, counter_key))
    assert final["n"] == 5

    # Cleanup
    from backend.src.firebase import get_db
    get_db().collection(collection).document(counter_key).delete()


def test_upload_submission_and_daily_reward(db, monkeypatch, tmp_path):
    from io import BytesIO
    from uuid import uuid4

    from fastapi.testclient import TestClient
    from PIL import Image

    from backend.src.assets_routes import SubmissionInput
    from backend.src.auth import _create_or_get_identity
    from backend.src.jobs import intake_submission
    from backend.src.main import create_app
    from backend.src.platform_routes import require_actor
    from backend.src.worker.http import process_delivery
    from scripts.seed_eras import seed_eras

    uid = str(uuid4())
    actor, created = _create_or_get_identity(db, db.collection("auth_identities").document(uid), uid, "Emulator")
    assert created
    seed_eras()
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("ASSESSMENT_PROVIDER", "fixture")
    monkeypatch.setenv("STORAGE_TYPE", "local")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path))
    app = create_app()
    app.dependency_overrides[require_actor] = lambda: actor

    with TestClient(app, raise_server_exceptions=False) as client:
        for index, expected in enumerate((20, 0)):
            photo = BytesIO()
            Image.new("RGB", (16, 16), "red").save(photo, "PNG")
            files = {"photo": ("capture.png", photo.getvalue(), "image/png")}
            headers = {"Idempotency-Key": str(uuid4())}
            created_asset = client.post("/api/v1/assets", headers=headers, files=files)
            assert created_asset.status_code == 201, created_asset.text
            asset = created_asset.json()
            assert client.post("/api/v1/assets", headers=headers, files=files).json() == asset
            assert client.post("/api/v1/assets", headers=headers,
                               files={"photo": ("other.jpg", photo.getvalue() + b"x")}).status_code == 409
            url = client.get(f"/api/v1/assets/{asset['id']}/url").json()["url"]
            assert client.get(url).headers["content-type"] == "image/jpeg"

            body = SubmissionInput(asset_id=asset["id"], mode="free", mission_id=None,
                                   mission_version=None, evaluation_session_id=None,
                                   expected_previous_submission_id=None)
            key = str(uuid4())
            submission = intake_submission(actor, body, key)
            assert intake_submission(actor, body, key) == submission
            process_delivery(db, submission["job_id"], 1)
            process_delivery(db, submission["job_id"], 1)
            response = client.get(f"/api/v1/submissions/{submission['id']}")
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["status"] == "succeeded"
            assert result["discovery"]["id"] == submission["id"]
            assert result["discovery"]["xp_awarded"] == expected
            assert result["discovery"]["fragment_added"] is (index == 0)
        assert db.collection("profiles").document(actor).get().to_dict()["xp_total"] == 20
        timeline = client.get("/api/v1/timeline")
        assert timeline.status_code == 200, timeline.text
        assert timeline.json()["items"][0]["fragment_count"] == 1


def test_auth_emulator_bootstraps_only_verified_user(db, monkeypatch):
    import os
    from concurrent.futures import ThreadPoolExecutor
    from uuid import uuid4

    import requests
    from fastapi.testclient import TestClient
    from firebase_admin import auth

    from backend.src.main import create_app

    host = os.getenv("FIREBASE_AUTH_EMULATOR_HOST")
    if not host:
        pytest.skip("Requires Auth Emulator")
    monkeypatch.setenv("ENV", "test")
    app = create_app()
    email = f"test-{uuid4().hex}@example.test"
    password = "emulator-password"
    firebase_user = auth.create_user(email=email, password=password, display_name="Tên thử")

    def token():
        response = requests.post(
            f"http://{host}/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=demo",
            json={"email": email, "password": password, "returnSecureToken": True},
            timeout=5,
        )
        return {"Authorization": f"Bearer {response.json()['idToken']}"}

    with TestClient(app, raise_server_exceptions=True) as client:
        assert client.get("/api/v1/me", headers=token()).status_code == 401
        auth.update_user(firebase_user.uid, email_verified=True)
        headers = token()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.map(lambda _: client.get("/api/v1/me", headers=headers), range(2))
        assert first.status_code == second.status_code == 200, (first.text, second.text)
        assert first.json() == second.json()
        key = str(uuid4())
        first_patch = client.patch("/api/v1/me", json={"bio": "first"},
                                   headers={**headers, "Idempotency-Key": key})
        client.patch("/api/v1/me", json={"bio": "second"},
                     headers={**headers, "Idempotency-Key": str(uuid4())})
        replay = client.patch("/api/v1/me", json={"bio": "first"},
                              headers={**headers, "Idempotency-Key": key})
        assert first_patch.status_code == replay.status_code == 200
        assert replay.json() == first_patch.json()
        assert client.get("/api/v1/me", headers=headers).json()["bio"] == "second"


def test_private_storage_emulator_upload(db):
    import os
    from io import BytesIO
    from uuid import uuid4

    from PIL import Image

    from backend.src.firebase import get_storage_bucket
    from backend.src.image_upload import store_image
    from backend.src.jobs import CONFIG

    if not os.getenv("FIREBASE_STORAGE_EMULATOR_HOST"):
        pytest.skip("Requires Storage Emulator")
    actor = str(uuid4())
    photo = BytesIO()
    Image.new("RGB", (16, 16), "red").save(photo, "PNG")
    dto = store_image(actor, str(uuid4()), photo.getvalue(), CONFIG, None)
    asset = db.collection("assets").document(dto["id"]).get().to_dict()
    blob = get_storage_bucket().blob(asset["object_path"])
    assert blob.download_as_bytes().startswith(b"\xff\xd8")
    blob.delete()


def test_expired_lease_recovery_and_retry_replay(db, monkeypatch):
    from datetime import timedelta
    from uuid import uuid4

    from backend.src.assets_routes import SubmissionInput
    from backend.src.award import award_result, error_detail
    from backend.src.jobs import intake_submission, read, retry_submission
    from backend.src.social.core import now
    from backend.src.worker.http import claim, process_delivery, recover

    monkeypatch.setenv("ASSESSMENT_PROVIDER", "fixture")
    actor, asset = str(uuid4()), str(uuid4())
    db.collection("profiles").document(actor).set({"xp_total": 0})
    db.collection("assets").document(asset).set({"owner_id": actor, "state": "ready"})
    body = SubmissionInput(asset_id=asset, mode="free", mission_id=None, mission_version=None,
                           evaluation_session_id=None, expected_previous_submission_id=None)
    submission = intake_submission(actor, body, str(uuid4()))
    job_id = submission["job_id"]
    lease, _, _ = claim(db, job_id, 1)
    job = db.collection("jobs").document(job_id)
    job.update({"lease_until": now() - timedelta(seconds=1)})
    assert recover(db, job_id)
    assert not award_result(job_id, lease, {})
    assert claim(db, job_id, 1) is None
    job.update({"status": "failed"})
    db.collection("submissions").document(submission["id"]).update({
        "status": "failed", "error": error_detail("provider_failed", "temporary", True),
    })
    key = str(uuid4())
    replay = retry_submission(actor, submission["id"], key)
    assert retry_submission(actor, submission["id"], key) == replay
    assert read(db, "job_outbox", job_id)["generation"] == 3
    process_delivery(db, job_id, 3)
    assert read(db, "profiles", actor)["xp_total"] == 20
    assert read(db, "submissions", submission["id"])["status"] == "succeeded"


def test_group_asset_url_tracks_membership_incarnation(db, monkeypatch):
    from uuid import uuid4

    from fastapi.testclient import TestClient

    from backend.src.main import create_app
    from backend.src.platform_routes import require_actor

    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("STORAGE_TYPE", "local")
    author, member, outsider, group, post, asset, incarnation = [str(uuid4()) for _ in range(7)]
    db.collection("assets").document(asset).set({"owner_id": author, "state": "attached"})
    db.collection("posts").document(post).set({
        "author_id": author, "asset_id": asset, "direct_user_ids": [],
        "group_grants": {group: {member: incarnation}},
    })
    group_ref = db.collection("groups").document(group)
    group_ref.set({"id": group, "members": {member: {"incarnation_id": incarnation}}})
    app = create_app()
    actor = member
    app.dependency_overrides[require_actor] = lambda: actor
    with TestClient(app) as client:
        path = f"/api/v1/assets/{asset}/url?post_id={post}"
        assert client.get(path).status_code == 200
        actor = outsider
        assert client.get(path).status_code == 404
        actor = member
        group_ref.update({"members": {member: {"incarnation_id": str(uuid4())}}})
        assert client.get(path).status_code == 404
        db.collection("posts").document(post).update({"direct_user_ids": [member]})
        assert client.get(path).status_code == 200


def test_session_evidence_cap(db, monkeypatch):
    from uuid import uuid4

    from backend.src.assets_routes import SubmissionInput
    from backend.src.jobs import intake_submission, read
    from backend.src.social.core import SocialError
    from backend.src.worker.http import process_delivery

    monkeypatch.setenv("ASSESSMENT_PROVIDER", "fixture")
    monkeypatch.setenv("WORKER_FIXTURE_VERDICT", "retake_required")
    actor = str(uuid4())
    previous = None
    session_id = None
    for index in range(5):
        asset_id = str(uuid4())
        db.collection("assets").document(asset_id).set({"owner_id": actor, "state": "ready"})
        body = SubmissionInput(asset_id=asset_id, mode="free", mission_id=None, mission_version=None,
                               evaluation_session_id=session_id, expected_previous_submission_id=previous)
        if index == 4:
            with pytest.raises(SocialError) as exc:
                intake_submission(actor, body, str(uuid4()))
            assert exc.value.code == "session_closed"
            break
        queued = intake_submission(actor, body, str(uuid4()))
        previous, session_id = queued["id"], queued["evaluation_session_id"]
        if index:
            with pytest.raises(SocialError):
                intake_submission(actor, body, str(uuid4()))
        process_delivery(db, queued["job_id"], 1)
        assert read(db, "submissions", previous)["verdict"] == "retake_required"
    session = read(db, "evaluation_sessions", session_id)
    assert session["status"] == "closed"
    assert session["evidence_count"] == 4
