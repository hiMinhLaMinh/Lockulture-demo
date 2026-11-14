"""Transactional doubles enforce read-before-write and atomic rollback; no live calls."""

from copy import deepcopy
from datetime import timedelta
from threading import RLock
from uuid import uuid4
import pytest
from backend.src.social.core import now, SocialError
from backend.src import jobs, award
from backend.src.worker import http, lease, souvenir, providers
from backend.src.missions import service, worker


class Ref:
    def __init__(self, db, collection, key):
        self.db, self.collection, self.key = db, collection, key

    def get(self, transaction=None):
        if transaction:
            assert not transaction.written, "Firestore read after write"
        data = (transaction.data if transaction else self.db.data).get(
            (self.collection, self.key)
        )
        return type("Snapshot", (), {"to_dict": lambda _: deepcopy(data)})()

    def set(self, value):
        self.db.data[(self.collection, self.key)] = deepcopy(value)


class Collection:
    def __init__(self, db, name):
        self.db, self.name = db, name

    def document(self, key):
        return Ref(self.db, self.name, key)


class Tx:
    def __init__(self, db):
        self.db = db
        self.written = False
        self.data = None

    def set(self, ref, value, merge=False):
        self.written = True
        key = (ref.collection, ref.key)
        self.data[key] = {
            **(self.data.get(key, {}) if merge else {}),
            **deepcopy(value),
        }

    def delete(self, ref):
        self.written = True
        self.data.pop((ref.collection, ref.key), None)


class DB:
    def __init__(self):
        self.data = {}
        self.lock = RLock()

    def collection(self, name):
        return Collection(self, name)

    def transaction(self):
        return Tx(self)


def atomic(fn):
    def run(tx, *args, **kwargs):
        with tx.db.lock:
            tx.data = deepcopy(tx.db.data)
            result = fn(tx, *args, **kwargs)
            tx.db.data = tx.data
            return result

    return run


@pytest.fixture
def db(monkeypatch):
    db = DB()
    for module in (jobs, award, http, lease, souvenir, service, worker):
        monkeypatch.setattr(module, "transactional", atomic)
        if hasattr(module, "get_db"):
            monkeypatch.setattr(module, "get_db", lambda: db)
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("ASSESSMENT_PROVIDER", "fixture")
    return db


def seed(db, mission=True, opt=True):
    from backend.src.assets_routes import SubmissionInput

    actor, asset, mid = map(str, (uuid4(), uuid4(), uuid4()))
    db.data["profiles", actor] = {
        "xp_total": 0,
        "active_mission_id": mid if mission else None,
    }
    db.data["assets", asset] = {"owner_id": actor, "state": "ready"}
    if mission:
        db.data["missions", mid] = {
            "id": mid,
            "owner_id": actor,
            "version": 1,
            "status": "active",
            "place_id": "p",
            "place_name": "Place",
            "era_id": "ERA_NGUYEN",
            "location": {"latitude": 0, "longitude": 0},
            "arrival_radius_m": 150,
            "badge_design": {"title": "Badge", "motif": "Gate", "era_id": "ERA_NGUYEN"},
            "heritage": {
                "summary": "Source fact",
                "fun_facts": ["Fact"],
                "era_id": "ERA_NGUYEN",
                "sources": [{"title": "Source", "url": "https://example.org"}],
            },
        }
    body = SubmissionInput(
        asset_id=asset,
        mode="mission" if mission else "free",
        mission_id=mid if mission else None,
        mission_version=1 if mission else None,
        evaluation_session_id=None,
        expected_previous_submission_id=None,
        capture_location=(
            {
                "latitude": 0,
                "longitude": 0,
                "accuracy_m": 10,
                "captured_at": now(),
                "source": "gps",
            }
            if mission
            else None
        ),
        souvenir_opt_in=opt,
    )
    response = jobs.intake_submission(actor, body, str(uuid4()))
    return actor, mid, response


def test_completion_atomic_and_redelivery(db):
    actor, mid, r = seed(db)
    http.process_delivery(db, r["job_id"], 1)
    assert db.data["submissions", r["id"]]["verdict"] == "completed"
    assert db.data["profiles", actor]["xp_total"] == 100
    assert len([k for k in db.data if k[0] == "earned_badges"]) == 1
    assert (
        len(
            [
                k
                for k, v in db.data.items()
                if k[0] == "jobs" and v.get("kind") == "souvenir"
            ]
        )
        == 1
    )
    before = deepcopy(db.data)
    http.process_delivery(db, r["job_id"], 1)
    assert db.data == before


def test_wrong_photo_no_reward(db, monkeypatch):
    actor, mid, r = seed(db)
    monkeypatch.setenv("WORKER_FIXTURE_VERDICT", "not_matched")
    http.process_delivery(db, r["job_id"], 1)
    assert db.data["profiles", actor]["xp_total"] == 0
    assert not [k for k in db.data if k[0] == "earned_badges"]
    assert db.data["missions", mid]["evaluating_submission_id"] is None


def test_free_unchanged(db):
    actor, _, r = seed(db, False)
    http.process_delivery(db, r["job_id"], 1)
    assert db.data["profiles", actor]["xp_total"] == 20
    assert not [k for k in db.data if k[0] == "mission_completions"]


def test_expired_lease_no_award(db):
    _, _, r = seed(db)
    token, sub, _ = http.claim(db, r["job_id"], 1)
    db.data["jobs", r["job_id"]]["lease_until"] = now() - timedelta(seconds=1)
    assert not award.award_result(r["job_id"], token, http.fixture_assessment(db, sub))


def test_reservation_survives_crash(db):
    _, _, r = seed(db)
    token, _, _ = http.claim(db, r["job_id"], 1)
    lease.reserve(db, r["job_id"], token, "gemini_calls")
    with pytest.raises(SocialError):
        lease.reserve(db, r["job_id"], token, "gemini_calls")
    db.data["jobs", r["job_id"]]["lease_until"] = now() - timedelta(seconds=1)
    http.recover(db, r["job_id"])
    assert db.data["jobs", r["job_id"]]["status"] == "failed"


def test_checkpoint_recovers_without_provider(db, monkeypatch):
    actor, _, r = seed(db)
    token, sub, _ = http.claim(db, r["job_id"], 1)
    lease.reserve(db, r["job_id"], token, "gemini_calls")
    lease.checkpoint(db, r["job_id"], token, http.fixture_assessment(db, sub))
    db.data["jobs", r["job_id"]]["lease_until"] = now() - timedelta(seconds=1)
    http.recover(db, r["job_id"])
    monkeypatch.setattr(
        providers, "assess", lambda *a: pytest.fail("unexpected provider")
    )
    http.process_delivery(db, r["job_id"], 2)
    assert db.data["profiles", actor]["xp_total"] == 100


def test_concurrent_delivery(db):
    from concurrent.futures import ThreadPoolExecutor

    actor, _, r = seed(db)
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(lambda _: http.process_delivery(db, r["job_id"], 1), range(2)))
    assert db.data["profiles", actor]["xp_total"] == 100
    assert len([k for k in db.data if k[0] == "reward_ledger"]) == 1


def test_souvenir_checkpoint_no_second_image(db, monkeypatch):
    actor, _, r = seed(db)
    http.process_delivery(db, r["job_id"], 1)
    job = next(
        v for k, v in db.data.items() if k[0] == "jobs" and v.get("kind") == "souvenir"
    )
    saved = {
        "asset_id": str(uuid4()),
        "reservation": "upload",
        "metadata": {"object_path": "private/image", "mime_type": "image/jpeg"},
    }
    job.update(checkpoint=saved, image_calls=1)
    http.process_delivery(db, job["id"], 1)
    assert db.data["jobs", job["id"]]["status"] == "succeeded"
    assert db.data["assets", saved["asset_id"]]["state"] == "attached"
    view = service.celebration(r["id"], actor)
    assert view["souvenir"]["asset_id"] == saved["asset_id"]
    with pytest.raises(SocialError) as e:
        service.celebration(r["id"], "outsider")
    assert e.value.status == 404


def test_souvenir_missing_helper_fails_without_reward_rollback(db):
    actor, _, r = seed(db)
    http.process_delivery(db, r["job_id"], 1)
    job = next(
        v for k, v in db.data.items() if k[0] == "jobs" and v.get("kind") == "souvenir"
    )
    http.process_delivery(db, job["id"], 1)
    assert db.data["jobs", job["id"]]["status"] == "failed"
    assert db.data["profiles", actor]["xp_total"] == 100


@pytest.mark.parametrize("failure", ["refusal", "timeout", "storage", "success"])
def test_image_single_call_and_failure(db, monkeypatch, failure):
    import sys, types

    actor, _, r = seed(db)
    http.process_delivery(db, r["job_id"], 1)
    job = next(
        v for k, v in db.data.items() if k[0] == "jobs" and v.get("kind") == "souvenir"
    )
    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        if failure in {"refusal", "timeout"}:
            raise TimeoutError("redacted")
        return b"image", "image/jpeg"

    def upload(**kwargs):
        if failure == "storage":
            raise ValueError("upload failed")
        return {
            "object_path": kwargs["object_path"],
            "sha256": "checksum",
            "mime_type": "image/jpeg",
            "byte_size": 5,
            "width": 1,
            "height": 1,
        }

    media = types.ModuleType("backend.src.media")
    storage = types.ModuleType("backend.src.media.storage")
    image = types.ModuleType("backend.src.media.souvenir")
    storage.load_owned_image = lambda **k: b"owned"
    storage.put_private_image = upload
    image.generate_souvenir = generate
    for name, module in [
        ("backend.src.media", media),
        ("backend.src.media.storage", storage),
        ("backend.src.media.souvenir", image),
    ]:
        monkeypatch.setitem(sys.modules, name, module)
    http.process_delivery(db, job["id"], 1)
    http.process_delivery(db, job["id"], 1)
    result = db.data["jobs", job["id"]]
    assert result["status"] == ("succeeded" if failure == "success" else "failed")
    assert result["image_calls"] == len(calls) == 1
    assert db.data["profiles", actor]["xp_total"] == 100
    if failure != "success":
        assert not jobs.can_retry(result, now())


def test_mutated_mission_version_prevents_vision(db, monkeypatch):
    actor, mid, r = seed(db)
    db.data["missions", mid]["version"] = 2
    monkeypatch.setattr(
        providers, "assess", lambda *a: pytest.fail("vision should not run")
    )
    http.process_delivery(db, r["job_id"], 1)
    assert db.data["jobs", r["job_id"]]["gemini_calls"] == 0
    assert db.data["profiles", actor]["xp_total"] == 0


def test_two_sessions_cannot_complete_one_mission(db):
    from backend.src.assets_routes import SubmissionInput

    actor, mid, r = seed(db)
    asset = str(uuid4())
    db.data["assets", asset] = {"owner_id": actor, "state": "ready"}
    body = SubmissionInput(
        asset_id=asset,
        mode="mission",
        mission_id=mid,
        mission_version=1,
        evaluation_session_id=None,
        expected_previous_submission_id=None,
        capture_location={
            "latitude": 0,
            "longitude": 0,
            "accuracy_m": 1,
            "captured_at": now(),
            "source": "gps",
        },
    )
    with pytest.raises(SocialError):
        jobs.intake_submission(actor, body, str(uuid4()))
    assert db.data["assets", asset]["state"] == "ready"


def test_emulator_mission_completion_and_duplicate_delivery(monkeypatch):
    import os

    if not os.getenv("FIRESTORE_EMULATOR_HOST"):
        pytest.skip("Requires isolated Firestore emulator")
    from concurrent.futures import ThreadPoolExecutor
    from backend.src.firebase import get_db
    from backend.src.assets_routes import SubmissionInput

    real = get_db()
    actor, asset, mid = map(str, (uuid4(), uuid4(), uuid4()))
    monkeypatch.setenv("ASSESSMENT_PROVIDER", "fixture")
    monkeypatch.setenv("ENV", "test")
    real.collection("profiles").document(actor).set(
        {"xp_total": 0, "active_mission_id": mid}
    )
    real.collection("assets").document(asset).set({"owner_id": actor, "state": "ready"})
    real.collection("missions").document(mid).set(
        {
            "id": mid,
            "owner_id": actor,
            "version": 1,
            "status": "active",
            "place_id": "emulator-place",
            "place_name": "Emulator Gate",
            "era_id": "ERA_NGUYEN",
            "location": {"latitude": 0, "longitude": 0},
            "arrival_radius_m": 150,
            "badge_design": {"title": "Badge", "motif": "Gate", "era_id": "ERA_NGUYEN"},
            "heritage": {
                "summary": "Test source",
                "fun_facts": ["Test fact"],
                "era_id": "ERA_NGUYEN",
                "sources": [{"title": "Test", "url": "https://example.org"}],
            },
        }
    )
    body = SubmissionInput(
        asset_id=asset,
        mode="mission",
        mission_id=mid,
        mission_version=1,
        evaluation_session_id=None,
        expected_previous_submission_id=None,
        capture_location={
            "latitude": 0,
            "longitude": 0,
            "accuracy_m": 10,
            "captured_at": now(),
            "source": "gps",
        },
        souvenir_opt_in=True,
    )
    key = str(uuid4())
    response = jobs.intake_submission(actor, body, key)
    assert jobs.intake_submission(actor, body, key) == response
    from google.api_core.exceptions import GoogleAPICallError

    def deliver_with_queue_redelivery(_):
        # Cloud Tasks redelivers a 503; reproduce that transport behavior here.
        for attempt in range(3):
            try:
                http.process_delivery(real, response["job_id"], 1)
                return
            except GoogleAPICallError:
                if attempt == 2:
                    raise

    with ThreadPoolExecutor(2) as pool:
        list(pool.map(deliver_with_queue_redelivery, range(2)))
    result = jobs.read(real, "submissions", response["id"])
    assert result["status"] == "succeeded", result
    assert jobs.read(real, "profiles", actor)["xp_total"] == 100
    completion = jobs.read(real, "mission_completions", response["id"])
    assert jobs.read(real, "earned_badges", completion["badge_id"])["owner_id"] == actor
    image_job = jobs.read(real, "jobs", completion["souvenir_job_id"])
    assert image_job["kind"] == "souvenir" and image_job["image_calls"] == 0
    assert jobs.read(real, "job_outbox", image_job["id"])["generation"] == 1
    http.process_delivery(real, response["job_id"], 1)
    assert jobs.read(real, "profiles", actor)["xp_total"] == 100


def test_exhausted_firestore_retry_is_infrastructure_error(db):
    from google.api_core.exceptions import Aborted, ServiceUnavailable

    def exhausted(tx):
        raise ValueError("Failed to commit") from Aborted("contention")

    with pytest.raises(ServiceUnavailable):
        jobs.transaction(db, exhausted)


def test_source_context_rejects_unreviewed_record(monkeypatch, tmp_path):
    import json

    path = tmp_path / "sources.json"
    path.write_text(
        json.dumps([{"place_id": "p", "era_id": "ERA_NGUYEN", "verified": False}])
    )
    monkeypatch.setenv("MISSION_SOURCE_CONTEXT_FILE", str(path))
    with pytest.raises(SocialError) as e:
        providers.source_context()
    assert e.value.status == 503
