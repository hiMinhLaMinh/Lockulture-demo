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
    from backend.src.social.core import MemoryTransaction

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
    db.collection("idempotency").document().delete()


def test_transaction_contention(repo):
    """Concurrent atomics on the same key succeed via retry."""
    import threading
    from backend.src.social.core import MemoryTransaction

    results = []
    errors = []
    collection = "_test_contention"
    counter_key = "counter"

    # Initialize
    repo.atomic(lambda tx: tx.put(collection, counter_key, {"n": 0}))

    def increment():
        try:
            def op(tx):
                row = tx.get(collection, counter_key)
                tx.put(collection, counter_key, {"n": row["n"] + 1})
            repo.atomic(op)
            results.append(1)
        except Exception as exc:
            errors.append(exc)

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


def test_award_no_double_xp(db):
    """Award transaction doesn't grant XP twice for the same reward_key."""
    import datetime
    from uuid import uuid4
    from backend.src.award import award_result
    from backend.src.firebase import get_db

    db = get_db()
    actor_id = str(uuid4())
    asset_id = str(uuid4())
    submission_id = str(uuid4())
    job_id = str(uuid4())
    now = datetime.datetime.now(datetime.timezone.utc)

    # Create minimal profile
    db.collection("profiles").document(actor_id).set({
        "schema_version": 1, "id": actor_id, "display_name": "Test",
        "username": "test" + actor_id[:4], "bio": "", "xp_total": 0,
        "active_mission_id": None, "active_search_id": None, "created_at": now,
    })
    # Create asset
    db.collection("assets").document(asset_id).set({
        "schema_version": 1, "id": asset_id, "owner_id": actor_id,
        "object_path": f"discoveries/{actor_id}/{asset_id}.jpg",
        "sha256": "a" * 64, "mime_type": "image/jpeg",
        "byte_size": 1024, "width": 640, "height": 480,
        "state": "ready", "created_at": now,
    })
    # Create submission
    db.collection("submissions").document(submission_id).set({
        "schema_version": 1, "id": submission_id, "owner_id": actor_id,
        "asset_id": asset_id, "mode": "free", "mission_id": None,
        "job_id": job_id, "status": "pending",
        "verdict": None, "knowledge": None, "discovery_id": None,
        "error": None, "created_at": now,
    })
    db.collection("jobs").document(job_id).set({
        "schema_version": 1, "id": job_id, "submission_id": submission_id,
        "owner_id": actor_id, "asset_id": asset_id, "mode": "free",
        "mission_id": None, "status": "pending", "attempts": 0,
        "deadline": now + datetime.timedelta(minutes=10), "checkpoint": None,
        "created_at": now,
    })

    ai_result = {
        "verdict": "valid",
        "subject_key": "test:landmark:abc",
        "era_id": "ERA_NGUYEN",
        "knowledge": "Test knowledge",
    }

    # Award twice
    award_result(submission_id, job_id, ai_result)
    award_result(submission_id, job_id, ai_result)

    # XP should only be granted once
    profile = db.collection("profiles").document(actor_id).get().to_dict()
    assert profile["xp_total"] == 20  # FREE_XP, not 40
