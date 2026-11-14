"""Persist an assessment and all of its effects under the current worker lease."""
import json
from pathlib import Path
from uuid import uuid4, uuid5, NAMESPACE_URL
from datetime import timedelta
from zoneinfo import ZoneInfo

from google.cloud.firestore import transactional
from jsonschema import Draft202012Validator

from .firebase import get_db
from .jobs import transaction, CONFIG, active_mission, read, write, queue
from .social.core import SocialError, digest, normalized, now, timestamp

SCHEMAS = {
    mode: Draft202012Validator(json.loads(
        (Path(__file__).resolve().parents[2] / f"contracts/ai/{mode}-assessment.schema.json").read_text()
    )) for mode in ("free", "mission")
}


def error_detail(code, message, retryable=False):
    return {"code": code, "message": message, "retryable": retryable, "request_id": str(uuid4())}


def finish_failure(db, tx, job, code, message, retryable=False):
    # Gather every dependent read before the first write, including mission lock.
    kind = job.get("kind", "submission")
    sub = read(db, "submissions", job["submission_id"], tx) if kind == "submission" else None
    mission = read(db, "missions", sub["mission_id"], tx) if sub and sub.get("mission_id") else None
    profile = read(db, "profiles", job["owner_id"], tx) if kind == "mission_search" else None
    error = error_detail(code, message, retryable)
    write(db, tx, "jobs", job["id"], {"status": "failed", "stage": "done", "lease_token": None,
                                     "lease_until": None, "error": error, "updated_at": now()}, merge=True)
    if sub:
        write(db, tx, "submissions", sub["id"], {"status": "failed", "error": error}, merge=True)
    if mission and mission.get("evaluating_submission_id") == sub["id"]:
        write(db, tx, "missions", sub["mission_id"], {"evaluating_submission_id": None}, merge=True)
    if profile and profile.get("active_search_id") == job["id"]:
        write(db, tx, "profiles", job["owner_id"], {"active_search_id": None}, merge=True)


def award_result(job_id: str, lease_token: str, assessment: dict) -> bool:
    """Return whether the current lease committed a result."""
    db = get_db()

    @transactional
    def run(tx):
        time = now()
        job = read(db, "jobs", job_id, tx)
        if not (job and job["status"] == "running" and job["lease_token"] == lease_token
                and job["lease_until"] > time and job["deadline"] > time):
            return False
        sub = read(db, "submissions", job["submission_id"], tx)
        session_id = sub["evaluation_session_id"]
        session = read(db, "evaluation_sessions", session_id, tx)
        if session["expires_at"] <= time or session["last_submission_id"] != sub["id"]:
            finish_failure(db, tx, job, "session_closed", "Evaluation session has expired or changed")
            if session["expires_at"] <= time:
                write(db, tx, "evaluation_sessions", session_id, {"status": "expired"}, merge=True)
            return False
        owner = sub["owner_id"]
        mode = sub["mode"]
        SCHEMAS[mode].validate(assessment)
        mission = None
        if mode == "mission":
            try:
                mission = active_mission(db, tx, owner, sub["mission_id"], sub["mission_version"])
            except SocialError:
                finish_failure(db, tx, job, "mission_inactive", "Mission is no longer active")
                return False
        if mission:
            from .missions.location import check_location
            # Recheck against intake time, not inference completion time.
            from datetime import datetime
            check = sub.get("location_check")
            if not check or sub.get("location_config_version") != CONFIG["version"]:
                finish_failure(db, tx, job, "validation_error", "Missing location snapshot")
                return False
            check_location(sub["capture_location"], mission, datetime.fromisoformat(check["checked_at"].replace("Z", "+00:00")))
        verdict = assessment["verdict"]
        discovery = None
        if verdict in {"accepted", "completed"}:
            discovery = grant_discovery(db, tx, sub, mission, assessment, time)
            status = "completed"
        elif verdict in {"retake_required", "unidentified"} and session["evidence_count"] < CONFIG["max_evidence_images"]:
            status = "awaiting_evidence"
        else:
            status = "closed"
        instruction = assessment["instruction"]
        if status == "closed" and verdict in {"retake_required", "unidentified"}:
            instruction = "Phiên đã đủ bốn ảnh. Hãy bắt đầu phiên mới."
        if mission:
            write(db, tx, "missions", sub["mission_id"], {"evaluating_submission_id": None}, merge=True)
        write(db, tx, "evaluation_sessions", session_id, {"status": status}, merge=True)
        write(db, tx, "submissions", sub["id"], {
            "status": "succeeded", "verdict": verdict, "name": assessment["name"],
            "knowledge": assessment["knowledge"], "instruction": instruction, "discovery": discovery,
            "error": None,
        }, merge=True)
        write(db, tx, "jobs", job_id, {"status": "succeeded", "stage": "done", "completed_at": time,
                                      "lease_token": None, "lease_until": None}, merge=True)
        return True

    return transaction(db, run)


def grant_discovery(db, tx, sub, mission, assessment, time):
    owner = sub["owner_id"]
    discovery_id = sub["id"]
    era_id = assessment["era_id"]
    mission_id = sub["mission_id"]
    if mission:
        subject = f"place:{mission['place_id']}"
        reward_key = f"mission:{mission_id}"
        xp = CONFIG["mission_xp"]
        if era_id != mission["era_id"]:
            raise ValueError("Assessment era must match the active mission")
    else:
        name = " ".join(normalized(assessment["canonical_name"]).split())
        subject = f"{assessment['category']}:{name}"
        if assessment["category"] == "street_sign":
            subject += ":" + " ".join(normalized(assessment["locality"]).split())
        day = sub["created_at"].astimezone(ZoneInfo(CONFIG["reward_timezone"])).date()
        reward_key = f"free:{subject}:{day}"
        xp = CONFIG["free_xp"]

    existing = read(db, "discoveries", discovery_id, tx)
    if existing:
        return {key: timestamp(value) if key == "created_at" else value
                for key, value in existing.items() if key != "schema_version"}
    profile = read(db, "profiles", owner, tx)
    ledger_id = digest([owner, reward_key])
    ledger = read(db, "reward_ledger", ledger_id, tx)
    progress_id = digest([owner, era_id])
    progress = (read(db, "era_progress", progress_id, tx) or {}) if era_id else {}
    completion = None
    if mission:
        badge_id = str(uuid5(NAMESPACE_URL, "lockulture:badge:" + owner + ":" + mission_id))
        souvenir_id = str(uuid5(NAMESPACE_URL, "lockulture:souvenir:" + discovery_id)) if sub.get("souvenir_opt_in") else None
        # Deterministic reservations are read before ANY reward write.
        for collection, ident in (("earned_badges", badge_id), ("mission_completions", discovery_id),
                                  ("jobs", souvenir_id), ("job_outbox", souvenir_id)):
            if ident:
                reserved = read(db, collection, ident, tx)
                if reserved:
                    raise ValueError("Completion reservation already exists")
        session = read(db, "evaluation_sessions", sub["evaluation_session_id"], tx)
        completion = {"schema_version": 1, "owner_id": owner, "mission_id": mission_id,
                      "badge_id": badge_id, "heritage": mission["heritage"],
                      "souvenir_job_id": souvenir_id, "evidence_asset_ids": session["asset_ids"][:sub["sequence"]],
                      "portrait_asset_id": sub.get("portrait_asset_id"), "consent": sub.get("souvenir_opt_in", False)}
    subjects = progress.get("subject_keys", [])
    fragment = bool(era_id and subject not in subjects and len(subjects) < CONFIG["fragment_goal"])
    if ledger and mission:
        raise ValueError("Mission reward already exists")
    if ledger:
        xp = 0
    result = {
        "id": discovery_id, "owner_id": owner, "submission_id": sub["id"], "asset_id": sub["asset_id"],
        "mode": sub["mode"], "mission_id": mission_id, "subject_key": subject, "era_id": era_id,
        "name": assessment["name"], "knowledge": assessment["knowledge"],
        "xp_awarded": xp, "reward_reason": "granted" if xp else "daily_subject_limit",
        "fragment_added": fragment, "created_at": timestamp(time),
    }
    write(db, tx, "discoveries", discovery_id, {**result, "created_at": time, "schema_version": 1})
    write(db, tx, "assets", sub["asset_id"], {"state": "attached"}, merge=True)
    profile_updates = {}
    if xp:
        write(db, tx, "reward_ledger", ledger_id, {
            "schema_version": 1, "owner_id": owner, "discovery_id": discovery_id, "xp": xp, "created_at": time,
        })
        profile_updates["xp_total"] = profile.get("xp_total", 0) + xp
    if fragment:
        write(db, tx, "era_progress", progress_id, {
            "schema_version": 1, "owner_id": owner, "era_id": era_id, "subject_keys": [*subjects, subject],
            "fragment_count": len(subjects) + 1, "discovery_ids": [*progress.get("discovery_ids", []), discovery_id],
        })
    if mission:
        write(db, tx, "earned_badges", badge_id, {"schema_version": 1, "id": badge_id,
              "owner_id": owner, "mission_id": mission_id, "place_id": mission["place_id"],
              **mission["badge_design"], "earned_at": time})
        write(db, tx, "mission_completions", discovery_id, completion)
        for evidence_id in completion["evidence_asset_ids"]:
            write(db, tx, "assets", evidence_id, {"state": "attached"}, merge=True)
        if completion["portrait_asset_id"]:
            write(db, tx, "assets", completion["portrait_asset_id"], {"state": "attached"}, merge=True)
        if souvenir_id:
            write(db, tx, "jobs", souvenir_id, {"schema_version": 1, "id": souvenir_id,
                  "kind": "souvenir", "owner_id": owner, "discovery_id": discovery_id,
                  "status": "queued", "stage": "queued", "attempts": 0, "image_calls": 0,
                  "created_at": time, "updated_at": time, "checkpoint": None,
                  "deadline": time + timedelta(seconds=CONFIG["job_deadline_seconds"])})
            queue(db, tx, souvenir_id, 1, time)
        write(db, tx, "missions", mission_id, {"status": "completed", "completed_at": time}, merge=True)
        profile_updates["active_mission_id"] = None
    if profile_updates:
        write(db, tx, "profiles", owner, profile_updates, merge=True)
    return result
