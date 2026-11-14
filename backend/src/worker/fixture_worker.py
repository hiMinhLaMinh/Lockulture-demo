"""Fixture worker adapter — simulates AI assessment without calling real AI.

This is a TEST/DEV adapter only. It reads the fixture verdict from
contracts/fixtures/config.json and returns a canned result that exercises
the same submission→job→discovery/XP path as the real worker.

CONTRACT: Never used in production. Never auto-posts. Never grants XP from
outside the award_result() transaction.

Fixture behaviour (configurable via WORKER_FIXTURE_VERDICT env var):
  valid   → discovery created, XP awarded, mission completed if mode=mission
  invalid → no discovery, no XP
  no_result → no discovery, no XP, submission status=no_result
"""
import json
import os
from pathlib import Path

CONTRACTS = Path(__file__).resolve().parents[4] / "contracts"


def _fixture_verdict() -> str:
    """Read WORKER_FIXTURE_VERDICT env or default to 'valid'."""
    return os.getenv("WORKER_FIXTURE_VERDICT", "valid")


def run_fixture_worker(submission_id: str) -> None:
    """Process a submission synchronously with fixture results.

    This is called after intake in dev/test mode.
    """
    from ..firebase import get_db
    from ..award import award_result

    db = get_db()
    sub_snap = db.collection("submissions").document(submission_id).get()
    if not sub_snap.exists:
        return
    sub = sub_snap.to_dict()
    if sub.get("status") != "pending":
        return

    job_id = sub.get("job_id")
    if not job_id:
        return
    job_snap = db.collection("jobs").document(job_id).get()
    if not job_snap.exists:
        return

    verdict = _fixture_verdict()

    # Build fixture AI result
    config = json.loads((CONTRACTS / "fixtures/config.json").read_text(encoding="utf-8"))
    identities = json.loads((CONTRACTS / "fixtures/identities.json").read_text(encoding="utf-8"))

    # Use first era from catalog as fixture context
    eras = json.loads((CONTRACTS / "fixtures/eras.json").read_text(encoding="utf-8"))
    era_id = eras[0]["id"]

    if verdict == "valid":
        ai_result = {
            "verdict": "valid",
            "subject_key": f"fixture:landmark:{submission_id[:8]}",
            "era_id": era_id,
            "knowledge": "Đây là một địa danh lịch sử tiêu biểu của Việt Nam (kết quả fixture).",
            "instruction": None,
        }
    elif verdict == "invalid":
        ai_result = {
            "verdict": "invalid",
            "subject_key": None,
            "era_id": None,
            "knowledge": None,
            "instruction": "Ảnh chưa phù hợp với tiêu chí nhiệm vụ (fixture).",
        }
    else:
        ai_result = {
            "verdict": "no_result",
            "subject_key": None,
            "era_id": None,
            "knowledge": None,
            "instruction": None,
        }

    # Mark job as processing
    db.collection("jobs").document(job_id).update({
        "status": "processing",
        "attempts": 1,
    })

    try:
        award_result(submission_id, job_id, ai_result)
    except Exception as exc:
        db.collection("jobs").document(job_id).update({
            "status": "failed",
            "error": str(exc),
        })
        db.collection("submissions").document(submission_id).update({
            "status": "failed",
            "error": str(exc),
        })
        raise
