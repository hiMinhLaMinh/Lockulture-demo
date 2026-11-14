"""Submission intake and job lifecycle shared by HTTP and the worker."""
import json
import os
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from google.cloud.firestore import transactional

from .firebase import get_db
from .social.core import SocialError, digest, now, require

CONFIG = json.loads((Path(__file__).resolve().parents[2] / "contracts/fixtures/config.json").read_text())


def read(db, collection, key, tx=None):
    return db.collection(collection).document(key).get(transaction=tx).to_dict()


def write(db, tx, collection, key, data, *, merge=False):
    tx.set(db.collection(collection).document(key), data, merge=merge)


def submission_dto(submission, session):
    return {
        **{field: submission.get(field) for field in (
            "id", "job_id", "evaluation_session_id", "mode", "status",
            "verdict", "name", "knowledge", "instruction", "discovery", "error",
        )},
        "evidence_count": submission["sequence"],
        "session_status": "expired" if session["expires_at"] <= now()
        and session["status"] in {"open", "awaiting_evidence"} else session["status"],
    }


def replay(db, tx, actor, operation, key, payload, time):
    ref = db.collection("idempotency_keys").document(digest([actor, operation, key]))
    record = ref.get(transaction=tx).to_dict()
    if record and record["expires_at"] > time:
        if record["request_hash"] != digest(payload):
            raise SocialError(409, "Idempotency key already used", "idempotency_conflict")
        return ref, record["response"]
    return ref, None


def remember(tx, ref, payload, response, time):
    tx.set(ref, {"schema_version": 1, "request_hash": digest(payload), "response": response,
                 "status_code": 202, "expires_at": time + timedelta(days=CONFIG["idempotency_retention_days"])})


def quota(db, tx, actor, time):
    hour = time.replace(minute=0, second=0, microsecond=0)
    ref = db.collection("rate_windows").document(digest([actor, "submission", hour.isoformat()]))
    record = ref.get(transaction=tx).to_dict() or {}
    used = record.get("used", 0)
    if used >= CONFIG["max_submissions_per_hour"]:
        raise SocialError(429, "Submission rate limit exceeded", retry_after=3600 - time.minute * 60 - time.second)
    return ref, {"schema_version": 1, "used": used + 1, "owner_id": actor, "updated_at": time}


def active_mission(db, tx, actor, mission_id, version):
    mission = read(db, "missions", mission_id, tx)
    profile = read(db, "profiles", actor, tx)
    if not (mission and profile and profile.get("active_mission_id") == mission_id
            and mission["owner_id"] == actor and mission["status"] == "active"
            and mission["version"] == version):
        raise SocialError(409, "Mission is no longer active", "mission_inactive")
    return mission


def intake_submission(actor, body, key):
    db = get_db()
    payload = body.model_dump(mode="json")
    submission_id, job_id = str(uuid4()), str(uuid4())
    session_id = payload["evaluation_session_id"] or str(uuid4())
    asset_id = payload["asset_id"]
    mission_id = payload["mission_id"]
    mission_version = payload["mission_version"]
    mode = payload["mode"]

    require(os.getenv("ASSESSMENT_PROVIDER") == "fixture", 503, "Assessment provider unavailable")
    if os.getenv("ENV") not in {"development", "test"}:
        require(actor in os.getenv("FIXTURE_ACTOR_IDS", "").split(","), 403, "Fixture assessment is restricted")

    @transactional
    def run(tx):
        time = now()
        idem, cached = replay(db, tx, actor, "startSubmission", key, payload, time)
        if cached:
            return cached
        rate_ref, rate = quota(db, tx, actor, time)
        asset = read(db, "assets", asset_id, tx)
        require(asset and asset["owner_id"] == actor, 404, "Asset not found")
        require(asset["state"] == "ready", 409, "Asset already used")
        if mission_id:
            active_mission(db, tx, actor, mission_id, mission_version)
        if payload["evaluation_session_id"]:
            session = read(db, "evaluation_sessions", session_id, tx)
            require(session and session["owner_id"] == actor, 404, "Session not found")
            previous = read(db, "submissions", session["last_submission_id"], tx)
            if not (session["expires_at"] > time and session["status"] == "awaiting_evidence"
                    and session["evidence_count"] < CONFIG["max_evidence_images"]
                    and session["mode"] == mode and session["mission_id"] == mission_id
                    and session["mission_version"] == mission_version
                    and session["last_submission_id"] == payload["expected_previous_submission_id"]
                    and previous and previous["status"] == "succeeded"):
                raise SocialError(409, "Session cannot accept more evidence", "session_closed")
        else:
            session = {"schema_version": 1, "owner_id": actor, "mode": mode, "mission_id": mission_id,
                       "mission_version": mission_version, "status": "open", "evidence_count": 0,
                       "asset_ids": [], "expires_at": time + timedelta(hours=CONFIG["session_expiry_hours"])}
        session["evidence_count"] += 1
        session["last_submission_id"] = submission_id
        session["asset_ids"].append(asset_id)
        submission = {
            "schema_version": 1, "id": submission_id, "job_id": job_id, "owner_id": actor,
            "evaluation_session_id": session_id, "asset_id": asset_id, "mode": mode,
            "mission_id": mission_id, "mission_version": mission_version,
            "sequence": session["evidence_count"], "status": "queued", "created_at": time,
        }
        job = {
            "schema_version": 1, "id": job_id, "submission_id": submission_id,
            "owner_id": actor, "status": "queued", "attempts": 0, "stage": "queued",
            "deadline": time + timedelta(seconds=CONFIG["job_deadline_seconds"]),
            "checkpoint": None, "gemini_calls": 0, "maps_calls": 0,
        }
        response = submission_dto(submission, session)
        write(db, tx, "evaluation_sessions", session_id, session)
        write(db, tx, "submissions", submission_id, submission)
        write(db, tx, "jobs", job_id, job)
        queue(db, tx, job_id, 1, time)
        write(db, tx, "assets", asset_id, {"state": "in_submission", "used_at": time}, merge=True)
        tx.set(rate_ref, rate)
        remember(tx, idem, payload, response, time)
        return response

    return run(db.transaction())


def queue(db, tx, job_id, generation, time):
    write(db, tx, "job_outbox", job_id, {
        "schema_version": 1, "generation": generation, "status": "pending",
        "delivered_at": None, "dispatch_after": time,
    })


def can_retry(job, time):
    return (job["deadline"] > time and job["attempts"] < CONFIG["max_worker_attempts"]
            and (job.get("checkpoint") is not None or job.get("gemini_calls", 0) < CONFIG["max_gemini_calls_submission"]))


def retry_submission(actor, submission_id, key):
    db = get_db()

    @transactional
    def run(tx):
        time = now()
        payload = [submission_id, {}]
        idem, cached = replay(db, tx, actor, "retrySubmission", key, payload, time)
        if cached:
            return cached
        submission = read(db, "submissions", submission_id, tx)
        require(submission and submission["owner_id"] == actor, 404, "Submission not found")
        job_id = submission["job_id"]
        job = read(db, "jobs", job_id, tx)
        outbox = read(db, "job_outbox", job_id, tx)
        session = read(db, "evaluation_sessions", submission["evaluation_session_id"], tx)
        require(job and outbox and submission["status"] == "failed" and job["status"] == "failed"
                and (submission.get("error") or {}).get("retryable") and can_retry(job, time)
                and session["expires_at"] > time and session["last_submission_id"] == submission_id,
                409, "Submission cannot be retried")
        if submission["mission_id"]:
            active_mission(db, tx, actor, submission["mission_id"], submission["mission_version"])
        rate_ref, rate = quota(db, tx, actor, time)
        queue(db, tx, job_id, outbox["generation"] + 1, time)
        write(db, tx, "jobs", job_id, {"status": "queued", "stage": "queued", "lease_token": None,
                                       "lease_until": None}, merge=True)
        submission.update(status="queued", error=None)
        write(db, tx, "submissions", submission_id, submission)
        response = submission_dto(submission, session)
        tx.set(rate_ref, rate)
        remember(tx, idem, payload, response, time)
        return response

    return run(db.transaction())
