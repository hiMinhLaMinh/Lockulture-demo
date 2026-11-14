"""Source-grounded search checkpoints and active mission compare-and-swap."""

import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from google.cloud.firestore import transactional
from jsonschema import Draft202012Validator
from ..jobs import transaction, CONFIG, read, write
from ..social.core import now, require
from ..worker import providers
from ..worker.lease import reserve, checkpoint, current
from .location import distance
from .service import ERAS

SCHEMA = json.loads(
    (
        Path(__file__).resolve().parents[3] / "contracts/ai/search-decision.schema.json"
    ).read_text()
)


def process(db, job, token):
    providers.preflight(job["owner_id"], search=True)
    payload = job["input"]
    state = job.get("checkpoint") or {"phase": "decision", "candidates": []}
    # A durable next phase is written before each network call. Counters survive a crash.
    while state["phase"] not in {"complete", "no_result"}:
        if state["phase"] == "maps":
            reserve(db, job["id"], token, "maps_calls")
            places = providers.places(
                state["query"], payload["location"], payload["radius_meters"]
            )
            sources = {r["place_id"]: r for r in providers.source_context()}
            candidates = {p["id"]: p for p in state["candidates"]}
            for p in places:
                source = sources.get(p.get("id"))
                if not source or p.get("id") == payload.get("exclude_place_id"):
                    continue
                if payload.get("era_id") and source["era_id"] != payload["era_id"]:
                    continue
                location = p.get("location", {})
                from .service import Coordinates

                Coordinates.model_validate(location)
                meters = distance(payload["location"], location)
                if meters <= payload["radius_meters"]:
                    candidates[p["id"]] = {
                        "id": p["id"],
                        "name": p["displayName"]["text"],
                        "address": p.get("formattedAddress", ""),
                        "location": location,
                        "distance": meters,
                        "source": source,
                    }
            state = {"phase": "decision", "candidates": list(candidates.values())}
            checkpoint(db, job["id"], token, state, "reviewing")
        else:
            latest = read(db, "jobs", job["id"])
            if latest.get("gemini_calls", 0) >= CONFIG["max_gemini_calls_search"]:
                state = {"phase": "no_result"}
                checkpoint(db, job["id"], token, state)
                break
            reserve(db, job["id"], token, "gemini_calls")
            prompt = (
                "Find a nearby cultural mission. Return JSON matching schema. Select ONLY a supplied candidate with its verified era. "
                "Use the reviewed source snapshot, never invent dates or URLs. If candidates are absent request a Places search for cultural landmarks; "
                "stop if no suitable candidate. Schema: "
                + json.dumps(SCHEMA, ensure_ascii=False)
                + "\nRequest: "
                + json.dumps(payload)
                + "\nCandidates: "
                + json.dumps(state["candidates"], ensure_ascii=False)
            )
            decision = providers.gemini(prompt, timeout=20)
            Draft202012Validator(SCHEMA).validate(decision)
            if decision["action"] == "search":
                if latest.get("maps_calls", 0) >= CONFIG["max_maps_calls"]:
                    state = {"phase": "no_result"}
                else:
                    state = {**state, "phase": "maps", "query": decision["query"]}
            elif decision["action"] == "stop":
                state = {"phase": "no_result"}
            else:
                m = decision["mission"]
                p = next(
                    (p for p in state["candidates"] if p["id"] == m["place_id"]), None
                )
                require(
                    p and p["source"]["era_id"] == m["era_id"],
                    409,
                    "Unverified mission candidate",
                )
                source = p["source"]
                era = next(e for e in ERAS if e["id"] == m["era_id"])
                mission = {
                    "id": str(uuid5(NAMESPACE_URL, "lockulture:mission:" + job["id"])),
                    "schema_version": 1,
                    "owner_id": job["owner_id"],
                    "search_id": job["id"],
                    "version": 1,
                    "era_id": era["id"],
                    "era_name": era["name"],
                    "place_id": p["id"],
                    "place_name": p["name"],
                    "address": p["address"],
                    "location": p["location"],
                    "clue": m["clue"],
                    "hints": m["hints"],
                    "photo_requirements": m["photo_requirements"],
                    "distance_meters": round(p["distance"]),
                    "xp": CONFIG["mission_xp"],
                    "revealed_hints": 0,
                    "answer_revealed": False,
                    "status": "active",
                    "arrival_radius_m": CONFIG["arrival_radius_m"],
                    "badge_design": {
                        "title": p["name"],
                        "motif": source["motif"],
                        "era_id": era["id"],
                    },
                    "heritage": {
                        k: source[k]
                        for k in ("summary", "fun_facts", "era_id", "sources")
                    },
                }
                state = {"phase": "complete", "mission": mission}
            checkpoint(db, job["id"], token, state, "preparing")
    finalize(db, job["id"], token, state)


def finalize(db, ident, token, state):
    @transactional
    def run(tx):
        job = read(db, "jobs", ident, tx)
        require(current(job, token), 409, "Worker lease expired")
        profile = read(db, "profiles", job["owner_id"], tx)
        old_id = profile.get("active_mission_id")
        old = read(db, "missions", old_id, tx) if old_id else None
        require(profile.get("active_search_id") == ident, 409, "Search changed")
        require(
            old_id == job["input"]["expected_active_mission_id"],
            409,
            "Active mission changed",
        )
        require(
            not old or not old.get("evaluating_submission_id"),
            409,
            "Mission is being evaluated",
        )
        changes = {"active_search_id": None}
        resource = None
        if state["phase"] == "complete":
            m = state["mission"]
            resource = m["id"]
            changes["active_mission_id"] = resource
            if old:
                write(db, tx, "missions", old_id, {"status": "replaced"}, merge=True)
            write(db, tx, "missions", resource, {**m, "created_at": now()})
        write(db, tx, "profiles", job["owner_id"], changes, merge=True)
        write(
            db,
            tx,
            "jobs",
            ident,
            {
                "status": "succeeded" if resource else "no_result",
                "resource_id": resource,
                "stage": "done",
                "updated_at": now(),
                "lease_token": None,
                "lease_until": None,
                "error": None,
            },
            merge=True,
        )

    transaction(db, run)
