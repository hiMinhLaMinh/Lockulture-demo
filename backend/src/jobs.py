"""Job/outbox infrastructure for the assessment pipeline.

Implements the intake transaction (DATA_TRANSACTIONS.md):
  - Check idempotency / rate limit / asset state / session
  - Create submission + job + outbox atomically
  - Dispatch fixture worker synchronously in dev/test mode

In production, Cloud Tasks picks up outbox entries.
"""
import datetime
import json
import os
from pathlib import Path
from uuid import uuid4

from .firebase import get_db
from .social.core import SocialError, digest, now, require, timestamp

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
CONFIG = json.loads((CONTRACTS / "fixtures/config.json").read_text(encoding="utf-8"))

JOB_DEADLINE_MINUTES = 10
MAX_ATTEMPTS = 3
IDEMPOTENCY_TTL_DAYS = 7
RATE_SUBMISSION_HOUR = 30  # submissions per hour


def _utc_hour_key(actor: str, operation: str, dt: datetime.datetime) -> str:
    hour = dt.replace(minute=0, second=0, microsecond=0).isoformat()
    return digest([actor, operation, hour])


def intake_submission(actor: str, body, idempotency_key: str) -> dict:
    """Atomic intake transaction for a photo submission."""
    db = get_db()
    idem_key = digest([actor, "submitPhoto", idempotency_key])
    idem_ref = db.collection("idempotency_keys").document(idem_key)

    @db.transaction(max_attempts=5)
    def run(tx):
        current_time = now()

        # --- Idempotency check ---
        idem_snap = idem_ref.get(transaction=tx)
        if idem_snap.exists:
            d = idem_snap.to_dict()
            if d.get("expires_at") and _to_dt(d["expires_at"]) > current_time:
                return d["response"]

        # --- Rate limit check ---
        rate_key = _utc_hour_key(actor, "submit", current_time)
        rate_ref = db.collection("rate_windows").document(rate_key)
        rate_snap = rate_ref.get(transaction=tx)
        used = rate_snap.to_dict().get("used", 0) if rate_snap.exists else 0
        require(used < RATE_SUBMISSION_HOUR, 429, "Submission rate limit exceeded")

        # --- Asset validation ---
        asset_ref = db.collection("assets").document(str(body.asset_id))
        asset_snap = asset_ref.get(transaction=tx)
        require(asset_snap.exists, 404, "Asset not found")
        asset = asset_snap.to_dict()
        require(asset["owner_id"] == actor, 403, "Asset does not belong to actor")
        require(asset.get("state") in ("ready",), 409, "Asset not ready for submission")

        # --- Profile check ---
        profile_ref = db.collection("profiles").document(actor)
        profile_snap = profile_ref.get(transaction=tx)
        require(profile_snap.exists, 404, "Profile not found")
        profile = profile_snap.to_dict()

        # --- Mission check for mission mode ---
        mission_id = str(body.mission_id) if body.mission_id else None
        if body.mode == "mission":
            require(mission_id is not None, 422, "mission_id required for mission mode")
            require(profile.get("active_mission_id") == mission_id, 409,
                    "Mission not active for actor")

        # --- Create submission + job ---
        submission_id = str(uuid4())
        job_id = str(uuid4())
        deadline = current_time + datetime.timedelta(minutes=JOB_DEADLINE_MINUTES)

        submission = {
            "schema_version": 1,
            "id": submission_id,
            "owner_id": actor,
            "asset_id": str(body.asset_id),
            "mode": body.mode,
            "mission_id": mission_id,
            "job_id": job_id,
            "status": "pending",
            "verdict": None,
            "knowledge": None,
            "discovery_id": None,
            "error": None,
            "created_at": current_time,
        }
        job = {
            "schema_version": 1,
            "id": job_id,
            "submission_id": submission_id,
            "owner_id": actor,
            "asset_id": str(body.asset_id),
            "mode": body.mode,
            "mission_id": mission_id,
            "status": "pending",
            "attempts": 0,
            "deadline": deadline,
            "checkpoint": None,
            "created_at": current_time,
        }
        outbox = {
            "schema_version": 1,
            "id": job_id,
            "generation": 1,
            "status": "pending",
            "dispatch_after": current_time,
            "created_at": current_time,
        }

        response = {
            "id": submission_id,
            "status": "pending",
            "verdict": None,
            "discovery_id": None,
            "knowledge": None,
            "error": None,
            "created_at": timestamp(current_time),
        }

        tx.set(db.collection("submissions").document(submission_id), submission)
        tx.set(db.collection("jobs").document(job_id), job)
        tx.set(db.collection("job_outbox").document(job_id), outbox)
        tx.set(rate_ref, {"used": used + 1, "owner_id": actor, "updated_at": current_time})
        tx.set(idem_ref, {
            "response": response,
            "expires_at": current_time + datetime.timedelta(days=IDEMPOTENCY_TTL_DAYS),
        })
        # Mark asset as "in_submission"
        tx.update(asset_ref, {"state": "in_submission"})
        return response

    result = run()

    # In dev/test mode, dispatch the fixture worker synchronously
    env = os.getenv("ENV", "production")
    if env in {"development", "test"}:
        try:
            from .worker.fixture_worker import run_fixture_worker
            submission_id = result["id"]
            run_fixture_worker(submission_id)
        except Exception:
            pass  # Worker errors should not fail the intake response

    return result


def reenqueue_job(job_id: str) -> None:
    """Re-enqueue an existing job in the outbox for retry."""
    db = get_db()
    db.collection("job_outbox").document(job_id).set({
        "status": "pending",
        "dispatch_after": now(),
        "updated_at": now(),
    }, merge=True)
    db.collection("jobs").document(job_id).update({"status": "pending"})


def _to_dt(value) -> datetime.datetime:
    if isinstance(value, datetime.datetime):
        return value
    return datetime.datetime.fromisoformat(str(value))
