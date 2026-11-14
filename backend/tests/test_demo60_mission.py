from datetime import timedelta
import math
import pytest
from pydantic import ValidationError
from backend.src.missions.location import CaptureLocation, check_location
from backend.src.social.core import now, SocialError
from backend.src.missions import service, worker
from backend.src.worker import http, providers
from test_demo60_jobs import db, seed


@pytest.mark.parametrize(
    "age,accuracy,ok",
    [
        (60, 50, True),
        (-5, 50, True),
        (60.001, 10, False),
        (-5.001, 10, False),
        (0, 50.001, False),
    ],
)
def test_gps_time_accuracy(age, accuracy, ok):
    time = now()
    sample = {
        "latitude": 0,
        "longitude": 0,
        "accuracy_m": accuracy,
        "captured_at": time - timedelta(seconds=age),
        "source": "gps",
    }
    mission = {"location": {"latitude": 0, "longitude": 0}, "arrival_radius_m": 150}
    if ok:
        assert check_location(sample, mission, time)["within_radius"]
    else:
        with pytest.raises(SocialError) as e:
            check_location(sample, mission, time)
        assert e.value.status == 422


@pytest.mark.parametrize("meters,ok", [(149.999, True), (150.001, False)])
def test_radius(meters, ok):
    time = now()
    sample = {
        "latitude": math.degrees(meters / 6371000),
        "longitude": 0,
        "accuracy_m": 10,
        "captured_at": time,
        "source": "gps",
    }
    mission = {"location": {"latitude": 0, "longitude": 0}}
    if ok:
        assert check_location(sample, mission, time)["within_radius"]
    else:
        with pytest.raises(SocialError) as e:
            check_location(sample, mission, time)
        assert e.value.code == "location_out_of_range"


@pytest.mark.parametrize(
    "field,value",
    [
        ("latitude", float("nan")),
        ("longitude", float("inf")),
        ("accuracy_m", None),
        ("source", "manual"),
        ("captured_at", "2026-01-01T00:00:00"),
    ],
)
def test_invalid_samples(field, value):
    sample = {
        "latitude": 0,
        "longitude": 0,
        "accuracy_m": 10,
        "captured_at": now(),
        "source": "gps",
    }
    sample[field] = value
    with pytest.raises(ValidationError):
        CaptureLocation.model_validate(sample)


def test_no_result_keeps_mission(db, monkeypatch):
    from uuid import uuid4

    actor, mid, r = seed(db)
    http.process_delivery(db, r["job_id"], 1)
    # Restore an active mission without an inflight submission for a new search.
    db.data["missions", mid]["status"] = "active"
    db.data["profiles", actor]["active_mission_id"] = mid
    monkeypatch.setattr(service, "preflight", lambda *a, **k: None)
    monkeypatch.setattr(providers, "preflight", lambda *a, **k: None)
    monkeypatch.setattr(
        providers,
        "gemini",
        lambda *a, **k: {"action": "stop", "reason": "No verified candidate"},
    )
    body = service.SearchInput(
        location={"latitude": 0, "longitude": 0},
        location_source="gps",
        radius_meters=1000,
        expected_active_mission_id=mid,
    )
    key = uuid4()
    search = service.start_search(body, actor, key)
    assert service.start_search(body, actor, key) == search
    http.process_delivery(db, search["id"], 1)
    assert db.data["jobs", search["id"]]["status"] == "no_result"
    assert db.data["profiles", actor]["active_mission_id"] == mid


def test_search_success_uses_places_and_reviewed_snapshot(db, monkeypatch):
    from uuid import uuid4

    actor = str(uuid4())
    db.data["profiles", actor] = {"xp_total": 0, "active_mission_id": None}
    monkeypatch.setattr(service, "preflight", lambda *a, **k: None)
    monkeypatch.setattr(providers, "preflight", lambda *a, **k: None)
    calls = []

    def model(*args, **kwargs):
        calls.append(1)
        return (
            {
                "action": "search",
                "query": "heritage landmarks",
                "reason": "Find candidate",
            }
            if len(calls) == 1
            else {
                "action": "select",
                "mission": {
                    "place_id": "real-place",
                    "era_id": "ERA_NGUYEN",
                    "clue": "Find the gate",
                    "hints": ["a", "b", "c"],
                    "photo_requirements": ["Gate facade"],
                    "rationale": "Reviewed source",
                },
            }
        )

    monkeypatch.setattr(providers, "gemini", model)
    monkeypatch.setattr(
        providers,
        "places",
        lambda *a: [
            {
                "id": "real-place",
                "displayName": {"text": "Gate"},
                "formattedAddress": "Address",
                "location": {"latitude": 0, "longitude": 0},
            },
            {
                "id": "far-away",
                "displayName": {"text": "Far"},
                "location": {"latitude": 10, "longitude": 10},
            },
        ],
    )
    monkeypatch.setattr(
        providers,
        "source_context",
        lambda: [
            {
                "place_id": "real-place",
                "era_id": "ERA_NGUYEN",
                "summary": "Reviewed history",
                "fun_facts": ["Reviewed fact"],
                "motif": "Gate",
                "sources": [{"title": "Museum", "url": "https://example.org"}],
            }
        ],
    )
    body = service.SearchInput(
        location={"latitude": 0, "longitude": 0},
        location_source="manual",
        radius_meters=1000,
        expected_active_mission_id=None,
    )
    search = service.start_search(body, actor, uuid4())
    http.process_delivery(db, search["id"], 1)
    result = db.data["jobs", search["id"]]
    assert result["status"] == "succeeded"
    assert result["maps_calls"] == 1 and result["gemini_calls"] == 2
    mission = service.get_mission(result["resource_id"], actor)
    assert mission["heritage"]["summary"] == "Reviewed history"
    assert mission["location"] == {"latitude": 0, "longitude": 0}
    key = uuid4()
    hint = service.HintInput(expected_revealed_hints=0)
    assert service.hint(result["resource_id"], hint, actor, key)["revealed_hints"] == 1
    assert service.hint(result["resource_id"], hint, actor, key)["revealed_hints"] == 1
    with pytest.raises(SocialError):
        service.hint(result["resource_id"], hint, actor, uuid4())
    service.answer(result["resource_id"], service.Input(), actor, uuid4())
    assert len(calls) == 2


def test_gps_rejection_leaves_intake_unchanged(db):
    from uuid import uuid4
    from backend.src.assets_routes import SubmissionInput
    from backend.src import jobs

    actor, mid, r = seed(db)
    db.data["missions", mid]["evaluating_submission_id"] = None
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
            "latitude": 1,
            "longitude": 1,
            "accuracy_m": 1,
            "captured_at": now(),
            "source": "gps",
        },
    )
    from copy import deepcopy

    before = deepcopy(db.data)
    with pytest.raises(SocialError) as e:
        jobs.intake_submission(actor, body, str(uuid4()))
    assert e.value.code == "location_out_of_range" and db.data == before
