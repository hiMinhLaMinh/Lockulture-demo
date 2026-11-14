"""Deterministic assessment adapter for explicitly enabled test environments."""
import os

from ..jobs import read
from ..social.core import require


def fixture_assessment(db, submission):
    require(os.getenv("ASSESSMENT_PROVIDER") == "fixture", 503, "Assessment provider unavailable")
    if os.getenv("ENV") not in {"development", "test"}:
        require(submission["owner_id"] in os.getenv("FIXTURE_ACTOR_IDS", "").split(","),
                403, "Fixture assessment is restricted")
    mode = submission["mode"]
    mission = read(db, "missions", submission["mission_id"]) if mode == "mission" else None
    success = "completed" if mission else "accepted"
    verdict = os.getenv("WORKER_FIXTURE_VERDICT") or success
    accepted = verdict == success
    name = mission["place_name"] if mission else os.getenv("FIXTURE_SUBJECT_NAME", "Trống đồng")
    return {
        "mode": mode, "verdict": verdict, "name": name if accepted else None,
        "knowledge": "Kết quả đánh giá thử nghiệm của Lockulture." if accepted else None,
        "instruction": None if accepted else "Chụp lại ảnh rõ nét hơn.",
        "category": ("place" if mission else "object") if accepted else None,
        "canonical_name": name if accepted else None, "locality": None,
        "era_id": (mission["era_id"] if mission else "ERA_ANCIENT") if accepted else None,
    }
