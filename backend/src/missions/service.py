"""Owner-scoped mission API with transactional search and hint CAS."""

import json
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4
from fastapi import APIRouter, Header
from pydantic import BaseModel, ConfigDict, Field
from google.cloud.firestore import transactional
from ..firebase import get_db
from ..jobs import transaction, CONFIG, read, write, replay, remember, queue
from ..platform_routes import Actor
from ..social.core import now, require, digest, timestamp
from ..worker.providers import preflight

router = APIRouter(prefix="/api/v1")
Key = Annotated[UUID, Header(alias="Idempotency-Key")]
ERAS = json.loads(
    (Path(__file__).resolve().parents[3] / "contracts/fixtures/eras.json").read_text()
)
FIELDS = (
    "id",
    "version",
    "era_id",
    "era_name",
    "place_id",
    "place_name",
    "address",
    "location",
    "clue",
    "hints",
    "photo_requirements",
    "distance_meters",
    "xp",
    "revealed_hints",
    "answer_revealed",
    "status",
    "arrival_radius_m",
    "badge_design",
    "heritage",
)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Coordinates(Input):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class SearchInput(Input):
    location: Coordinates
    location_source: Literal["gps", "manual"]
    radius_meters: Literal[1000, 3000, 5000]
    era_id: str | None = None
    exclude_place_id: str | None = None
    expected_active_mission_id: UUID | None


class HintInput(Input):
    expected_revealed_hints: int = Field(ge=0, le=3)


def mission_dto(m):
    require(
        all(k in m for k in FIELDS),
        503,
        "Mission predates contract 1.1.0; start a new search",
    )
    return {k: m[k] for k in FIELDS}


def job_dto(j):
    return {
        **{
            k: j.get(k)
            for k in ("id", "kind", "status", "stage", "resource_id", "error")
        },
        "created_at": timestamp(j["created_at"]),
        "updated_at": timestamp(j["updated_at"]),
        "retry_after_seconds": 2 if j["status"] in {"queued", "running"} else 0,
    }


def owned(db, collection, ident, actor, tx=None):
    r = read(db, collection, ident, tx)
    require(r and r["owner_id"] == actor, 404, "Resource not found")
    return r


@router.post("/mission-searches", status_code=202, operation_id="startMissionSearch")
def start_search(body: SearchInput, actor: Actor, key: Key):
    preflight(actor, search=True)
    require(
        body.era_id is None or body.era_id in {e["id"] for e in ERAS},
        422,
        "Invalid era",
    )
    db = get_db()
    payload = body.model_dump(mode="json")
    ident = str(uuid4())

    @transactional
    def run(tx):
        time = now()
        idem, cached = replay(
            db, tx, actor, "startMissionSearch", str(key), payload, time
        )
        if cached:
            return cached
        profile = read(db, "profiles", actor, tx)
        require(profile is not None, 404, "Profile not found")
        require(
            profile.get("active_mission_id") == payload["expected_active_mission_id"],
            409,
            "Active mission changed",
        )
        active = (
            read(db, "jobs", profile["active_search_id"], tx)
            if profile.get("active_search_id")
            else None
        )
        require(
            not active or active["status"] not in {"queued", "running"},
            409,
            "Search already running",
        )
        mission = (
            read(db, "missions", profile["active_mission_id"], tx)
            if profile.get("active_mission_id")
            else None
        )
        require(
            not mission or not mission.get("evaluating_submission_id"),
            409,
            "Mission is being evaluated",
        )
        hour = time.replace(minute=0, second=0, microsecond=0)
        rate_id = digest([actor, "mission_search", hour.isoformat()])
        rate = read(db, "rate_windows", rate_id, tx) or {}
        require(
            rate.get("used", 0) < CONFIG["max_searches_per_hour"],
            429,
            "Search rate limit exceeded",
        )
        job = {
            "id": ident,
            "schema_version": 1,
            "owner_id": actor,
            "kind": "mission_search",
            "status": "queued",
            "stage": "queued",
            "input": payload,
            "created_at": time,
            "updated_at": time,
            "deadline": time + timedelta(seconds=CONFIG["job_deadline_seconds"]),
            "attempts": 0,
            "maps_calls": 0,
            "gemini_calls": 0,
            "checkpoint": None,
            "resource_id": None,
            "error": None,
        }
        result = job_dto(job)
        write(db, tx, "jobs", ident, job)
        queue(db, tx, ident, 1, time)
        write(db, tx, "profiles", actor, {"active_search_id": ident}, merge=True)
        write(
            db,
            tx,
            "rate_windows",
            rate_id,
            {"used": rate.get("used", 0) + 1, "owner_id": actor, "schema_version": 1},
        )
        remember(tx, idem, payload, result, time)
        return result

    return transaction(db, run)


@router.get("/mission-searches/{search_id}", operation_id="getMissionSearch")
def get_search(search_id: UUID, actor: Actor):
    j = owned(get_db(), "jobs", str(search_id), actor)
    require(j.get("kind") == "mission_search", 404, "Search not found")
    return job_dto(j)


@router.get("/missions/active", operation_id="getActiveMission")
def get_active(actor: Actor):
    db = get_db()
    p = read(db, "profiles", actor)
    return (
        mission_dto(owned(db, "missions", p["active_mission_id"], actor))
        if p and p.get("active_mission_id")
        else None
    )


@router.get("/missions/{mission_id}", operation_id="getMission")
def get_mission(mission_id: UUID, actor: Actor):
    return mission_dto(owned(get_db(), "missions", str(mission_id), actor))


def reveal(actor, ident, key, body, hint):
    db = get_db()
    payload = [ident, body]
    operation = "revealHint" if hint else "revealAnswer"

    @transactional
    def run(tx):
        time = now()
        idem, cached = replay(db, tx, actor, operation, key, payload, time)
        if cached:
            return cached
        m = owned(db, "missions", ident, actor, tx)
        require(m["status"] == "active", 409, "Mission is not active")
        if hint:
            require(
                m["revealed_hints"] == body["expected_revealed_hints"]
                and m["revealed_hints"] < 3,
                409,
                "Hint state changed",
            )
            m["revealed_hints"] += 1
        else:
            m["answer_revealed"] = True
        result = mission_dto(m)
        write(db, tx, "missions", ident, m)
        remember(tx, idem, payload, result, time)
        return result

    return transaction(db, run)


@router.post("/missions/{mission_id}/hints", operation_id="revealHint")
def hint(mission_id: UUID, body: HintInput, actor: Actor, key: Key):
    return reveal(actor, str(mission_id), str(key), body.model_dump(), True)


@router.put("/missions/{mission_id}/answer", operation_id="revealAnswer")
def answer(mission_id: UUID, body: Input, actor: Actor, key: Key):
    return reveal(actor, str(mission_id), str(key), {}, False)


@router.get("/discoveries/{discovery_id}/celebration", operation_id="getCelebration")
def celebration(discovery_id: UUID, actor: Actor):
    db = get_db()
    c = owned(db, "mission_completions", str(discovery_id), actor)
    b = owned(db, "earned_badges", c["badge_id"], actor)
    j = (
        owned(db, "jobs", c["souvenir_job_id"], actor)
        if c.get("souvenir_job_id")
        else None
    )
    return {
        "discovery_id": str(discovery_id),
        "badge": {
            **{k: b[k] for k in ("id", "title", "motif", "era_id")},
            "earned_at": timestamp(b["earned_at"]),
        },
        "heritage": c["heritage"],
        "souvenir": {
            "job_id": c.get("souvenir_job_id"),
            "status": j["status"] if j else "not_requested",
            "asset_id": j.get("asset_id") if j else None,
            "error": j.get("error") if j else None,
        },
    }
