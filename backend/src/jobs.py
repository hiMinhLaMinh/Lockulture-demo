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



def transaction(db, operation, *args):
    """Preserve retryable Firestore contention hidden by the SDK's ValueError."""
    from google.api_core.exceptions import GoogleAPICallError, ServiceUnavailable
    try:
        return operation(db.transaction(), *args)
    except ValueError as exc:
        if isinstance(exc.__cause__, GoogleAPICallError):
            raise ServiceUnavailable("Firestore transaction contention; retry delivery") from exc
        raise


def read(db, collection, key, tx=None):
    return db.collection(collection).document(key).get(transaction=tx).to_dict()


def write(db, tx, collection, key, data, *, merge=False):
    tx.set(db.collection(collection).document(key), data, merge=merge)


def submission_dto(submission, session):
    return {
        **{field: submission.get(field) for field in (
            "id", "job_id", "evaluation_session_id", "mode", "status",
            "verdict", "name", "knowledge", "instruction", "discovery", "error", "location_check",
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

    from .worker.providers import preflight
    preflight(actor)

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
        location_check = None
        mission = None
        if mission_id:
            from .missions.location import check_location
            mission = active_mission(db, tx, actor, mission_id, mission_version)
            require(all(k in mission for k in ("arrival_radius_m", "badge_design", "heritage")),
                    409, "Mission predates contract 1.1.0; start a new search")
            require(not mission.get("evaluating_submission_id"), 409, "Mission is being evaluated")
            location_check = check_location(payload.get("capture_location"), mission, time)
        portrait_id = payload.get("portrait_asset_id")
        if portrait_id:
            portrait = read(db, "assets", portrait_id, tx)
            require(portrait and portrait["owner_id"] == actor and portrait["state"] == "ready", 404, "Portrait not found")
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
            "capture_location": payload.get("capture_location"), "location_check": location_check,
            "location_config_version": CONFIG["version"], "souvenir_opt_in": payload.get("souvenir_opt_in", False),
            "portrait_asset_id": portrait_id,
            "previous_instruction": previous.get("instruction") if payload["evaluation_session_id"] else None,
        }
        job = {
            "schema_version": 1, "kind": "submission", "id": job_id, "submission_id": submission_id,
            "owner_id": actor, "status": "queued", "attempts": 0, "stage": "queued",
            "deadline": time + timedelta(seconds=CONFIG["job_deadline_seconds"]),
            "checkpoint": None, "gemini_calls": 0, "maps_calls": 0,
        }
        response = submission_dto(submission, session)
        if mission:
            write(db, tx, "missions", mission_id, {"evaluating_submission_id": submission_id}, merge=True)
        if portrait_id:
            write(db, tx, "assets", portrait_id, {"state": "in_submission", "used_at": time}, merge=True)
        write(db, tx, "evaluation_sessions", session_id, session)
        write(db, tx, "submissions", submission_id, submission)
        write(db, tx, "jobs", job_id, job)
        queue(db, tx, job_id, 1, time)
        write(db, tx, "assets", asset_id, {"state": "in_submission", "used_at": time,
                   "capture_location": payload.get("capture_location"), "mission_id": mission_id,
                   "mission_version": mission_version}, merge=True)
        tx.set(rate_ref, rate)
        remember(tx, idem, payload, response, time)
        return response

    return transaction(db, run)


def queue(db, tx, job_id, generation, time):
    write(db, tx, "job_outbox", job_id, {
        "schema_version": 1, "generation": generation, "status": "pending",
        "delivered_at": None, "dispatch_after": time,
    })


def can_retry(job, time):
    if job["deadline"] <= time or job["attempts"] >= CONFIG["max_worker_attempts"]:
        return False
    kind = job.get("kind", "submission")
    if kind == "mission_search":
        phase = (job.get("checkpoint") or {}).get("phase", "decision")
        return phase in {"complete", "no_result"} or (
            job.get("maps_calls", 0) < CONFIG["max_maps_calls"] if phase == "maps"
            else job.get("gemini_calls", 0) < CONFIG["max_gemini_calls_search"])
    counter, limit = ("image_calls", "max_image_calls_souvenir") if kind == "souvenir" else ("gemini_calls", "max_gemini_calls_submission")
    return job.get("checkpoint") is not None or job.get(counter, 0) < CONFIG[limit]


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
            mission = active_mission(db, tx, actor, submission["mission_id"], submission["mission_version"])
            require(not mission.get("evaluating_submission_id"), 409, "Mission is being evaluated")
        rate_ref, rate = quota(db, tx, actor, time)
        if submission["mission_id"]:
            write(db, tx, "missions", submission["mission_id"], {"evaluating_submission_id": submission_id}, merge=True)
        queue(db, tx, job_id, outbox["generation"] + 1, time)
        write(db, tx, "jobs", job_id, {"status": "queued", "stage": "queued", "lease_token": None,
                                       "lease_until": None}, merge=True)
        submission.update(status="queued", error=None)
        write(db, tx, "submissions", submission_id, submission)
        response = submission_dto(submission, session)
        tx.set(rate_ref, rate)
        remember(tx, idem, payload, response, time)
        return response

    return transaction(db, run)
