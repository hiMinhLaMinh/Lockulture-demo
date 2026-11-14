"""Award transaction: grant XP, fragment, and create discovery from AI result.

Implements DATA_TRANSACTIONS.md "Award" transaction:
  - Lock on owner via profile document
  - Check reward_ledger for idempotency (no double XP)
  - Create discovery document
  - Update era_progress (fragment cap=3, unique subject/era)
  - Update profile.xp_total
  - Close submission + job atomically
"""
import datetime
import json
from pathlib import Path
from uuid import uuid4

from .firebase import get_db
from .social.core import SocialError, digest, now, timestamp

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
CONFIG = json.loads((CONTRACTS / "fixtures/config.json").read_text(encoding="utf-8"))
FREE_XP = CONFIG["free_xp"]           # 20
MISSION_XP = CONFIG["mission_xp"]     # 100
MAX_FRAGMENTS = 3


def _vn_date_key(dt: datetime.datetime) -> str:
    """Vietnam date string for daily XP gate (Asia/Ho_Chi_Minh = UTC+7)."""
    vn = dt + datetime.timedelta(hours=7)
    return vn.strftime("%Y-%m-%d")


def award_result(submission_id: str, job_id: str, ai_result: dict) -> None:
    """Atomic award transaction. Idempotent — safe to call twice with same job_id."""
    db = get_db()
    verdict = ai_result.get("verdict", "no_result")

    # Fetch submission outside transaction for owner
    sub_snap = db.collection("submissions").document(submission_id).get()
    if not sub_snap.exists:
        raise SocialError(404, "Submission not found")
    sub = sub_snap.to_dict()
    owner_id = sub["owner_id"]
    mode = sub["mode"]
    mission_id = sub.get("mission_id")
    asset_id = sub.get("asset_id")
    created_at = sub.get("created_at")
    if isinstance(created_at, str):
        created_at = datetime.datetime.fromisoformat(created_at)

    if verdict in ("invalid", "no_result"):
        # No reward — just close the submission
        _close_submission_no_reward(db, submission_id, job_id, verdict, ai_result)
        return

    subject_key = ai_result.get("subject_key")
    era_id = ai_result.get("era_id")
    knowledge = ai_result.get("knowledge", "")

    @db.transaction(max_attempts=5)
    def run(tx):
        current_time = now()

        # --- Profile (lock + read xp_total) ---
        profile_ref = db.collection("profiles").document(owner_id)
        profile_snap = profile_ref.get(transaction=tx)
        if not profile_snap.exists:
            raise SocialError(404, "Profile not found")
        profile = profile_snap.to_dict()

        # --- Idempotency: check if job already awarded ---
        job_ref = db.collection("jobs").document(job_id)
        job_snap = job_ref.get(transaction=tx)
        if job_snap.exists and job_snap.to_dict().get("status") == "complete":
            return  # Already awarded, no-op

        # --- XP calculation ---
        xp_to_grant = 0
        reward_reason = "valid"
        if mode == "mission":
            # Mission: 100 XP, one-time only (checked via ledger)
            reward_key = f"mission:{mission_id}"
        else:
            # Free: 20 XP, once per subject_key per VN day
            vn_day = _vn_date_key(created_at)
            reward_key = f"free:{subject_key}:{vn_day}"

        ledger_key = digest([owner_id, reward_key])
        ledger_ref = db.collection("reward_ledger").document(ledger_key)
        ledger_snap = ledger_ref.get(transaction=tx)

        if ledger_snap.exists:
            # Already rewarded
            reward_reason = "daily_subject_limit" if mode == "free" else "mission_already_complete"
            xp_to_grant = 0
        else:
            xp_to_grant = MISSION_XP if mode == "mission" else FREE_XP

        # --- Fragment calculation ---
        fragment_added = False
        era_progress_key = digest([owner_id, era_id]) if era_id else None
        era_progress_ref = None
        era_progress = None

        if era_id and subject_key:
            era_progress_ref = db.collection("era_progress").document(era_progress_key)
            era_snap = era_progress_ref.get(transaction=tx)
            if era_snap.exists:
                era_progress = era_snap.to_dict()
            else:
                era_progress = {
                    "schema_version": 1,
                    "owner_id": owner_id,
                    "era_id": era_id,
                    "subject_keys": [],
                    "fragment_count": 0,
                    "discovery_ids": [],
                }

            existing_subjects = era_progress.get("subject_keys", [])
            fragment_count = era_progress.get("fragment_count", 0)
            if subject_key not in existing_subjects and fragment_count < MAX_FRAGMENTS:
                fragment_added = True

        # --- Create discovery ---
        discovery_id = str(uuid4())
        discovery = {
            "schema_version": 1,
            "id": discovery_id,
            "owner_id": owner_id,
            "submission_id": submission_id,
            "asset_id": asset_id,
            "mission_id": mission_id,
            "mode": mode,
            "subject_key": subject_key,
            "era_id": era_id,
            "knowledge": knowledge,
            "xp_awarded": xp_to_grant,
            "reward_reason": reward_reason,
            "fragment_added": fragment_added,
            "created_at": current_time,
        }

        # --- Writes ---
        discovery_ref = db.collection("discoveries").document(discovery_id)
        tx.set(discovery_ref, discovery)

        # Update submission
        sub_ref = db.collection("submissions").document(submission_id)
        tx.update(sub_ref, {
            "status": "complete",
            "verdict": "valid",
            "knowledge": knowledge,
            "discovery_id": discovery_id,
        })

        # Close job
        tx.update(job_ref, {"status": "complete", "completed_at": current_time})

        # Mark asset as attached
        asset_ref = db.collection("assets").document(asset_id)
        tx.update(asset_ref, {"state": "attached"})

        # Reward ledger + XP
        if xp_to_grant > 0 and not ledger_snap.exists:
            tx.set(ledger_ref, {
                "schema_version": 1,
                "discovery_id": discovery_id,
                "xp": xp_to_grant,
                "created_at": current_time,
            })
            tx.update(profile_ref, {"xp_total": profile["xp_total"] + xp_to_grant})

        # Era progress fragment
        if fragment_added and era_progress_ref is not None and era_progress is not None:
            new_subjects = era_progress["subject_keys"] + [subject_key]
            new_count = era_progress["fragment_count"] + 1
            new_ids = era_progress.get("discovery_ids", []) + [discovery_id]
            tx.set(era_progress_ref, {
                **era_progress,
                "subject_keys": new_subjects,
                "fragment_count": new_count,
                "discovery_ids": new_ids,
            })

        # Mission completion
        if mode == "mission" and mission_id and not ledger_snap.exists:
            mission_ref = db.collection("missions").document(mission_id)
            tx.update(mission_ref, {"status": "complete", "completed_at": current_time})
            tx.update(profile_ref, {"active_mission_id": None})

    run()


def _close_submission_no_reward(db, submission_id: str, job_id: str,
                                 verdict: str, ai_result: dict) -> None:
    """Close submission without any reward for invalid/no_result verdicts."""
    updates = {
        "status": "complete",
        "verdict": verdict,
        "knowledge": ai_result.get("knowledge"),
        "instruction": ai_result.get("instruction"),
    }
    db.collection("submissions").document(submission_id).update(updates)
    db.collection("jobs").document(job_id).update({"status": "complete"})
