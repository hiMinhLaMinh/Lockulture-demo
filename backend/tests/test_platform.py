"""Tests for platform routes (/me, /timeline) with fixture services.

These use the fixture actor system (dev tokens) to test the endpoint shapes
without requiring real Firebase. Emulator tests for real data are in
test_firebase_emulator.py (to be run separately when Emulator is available).
"""
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.src.main import create_app
from backend.src.social.fixtures import load_fixture_services


@pytest.fixture(scope="module")
def services():
    return load_fixture_services()


@pytest.fixture
def client(services, monkeypatch):
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("LOCKULTURE_SOCIAL_FIXTURES", "1")
    app = create_app(social=services)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def auth(actor="A"):
    return {"Authorization": f"Bearer lockulture-dev-{actor}"}


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_firebase_me_route_precedes_social_route_without_fixtures(monkeypatch):
    monkeypatch.setenv("ENV", "test")
    monkeypatch.delenv("LOCKULTURE_SOCIAL_FIXTURES", raising=False)
    app = create_app()
    routes = [route for route in app.routes if getattr(route, "path", None) == "/api/v1/me"]
    assert routes[0].endpoint.__module__.endswith("platform_routes")


def test_get_me_requires_auth(client):
    r = client.get("/api/v1/me")
    assert r.status_code == 401


def test_get_me_fixture_actor(client):
    """GET /me with fixture token returns user profile from fixture identities."""
    r = client.get("/api/v1/me", headers=auth("A"))
    assert r.status_code == 200
    body = r.json()
    assert "id" in body
    assert "display_name" in body
    assert "username" in body
    assert "xp" in body
    assert "email" not in body  # private fields not exposed


def test_get_me_different_actors(client):
    """Each actor returns their own profile."""
    r_a = client.get("/api/v1/me", headers=auth("A"))
    r_b = client.get("/api/v1/me", headers=auth("B"))
    assert r_a.status_code == 200
    assert r_b.status_code == 200
    assert r_a.json()["id"] != r_b.json()["id"]


def test_patch_me_requires_idempotency_key(client):
    """PATCH /me without Idempotency-Key header should fail validation."""
    r = client.patch("/api/v1/me", headers=auth("A"), json={"display_name": "Test"})
    # Should fail — no Idempotency-Key
    assert r.status_code in (400, 422)


def test_timeline_returns_10_eras(client):
    """GET /timeline returns all 10 canonical eras."""
    r = client.get("/api/v1/timeline", headers=auth("A"))
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    # In fixture mode without real Firestore, era_progress may be empty
    # but all 10 eras should still be returned from the catalog
    assert len(body["items"]) == 10


def test_timeline_requires_auth(client):
    r = client.get("/api/v1/timeline")
    assert r.status_code == 401


def test_timeline_all_locked_without_progress(client):
    """Without real Firestore era_progress, all eras should be locked."""
    r = client.get("/api/v1/timeline", headers=auth("D"))
    assert r.status_code == 200
    items = r.json()["items"]
    for item in items:
        assert item["fragment_goal"] == 3
        assert item["id"].startswith("ERA_")
        assert item["status"] == "not_started"
    assert r.json()["next_cursor"] is None


def test_discoveries_returns_fixture_data(client):
    """GET /discoveries returns owner's discoveries (fixture data)."""
    r = client.get("/api/v1/discoveries", headers=auth("A"))
    assert r.status_code == 200
    assert "items" in r.json()


def test_discoveries_b_cannot_see_a_discovery(client):
    """B cannot access A's discovery by ID."""
    # Get A's discovery ID
    r_a = client.get("/api/v1/discoveries", headers=auth("A"))
    items = r_a.json().get("items", [])
    if items:
        disc_id = items[0]["id"]
        r_b = client.get(f"/api/v1/discoveries/{disc_id}", headers=auth("B"))
        assert r_b.status_code == 404


def test_leaderboard_returns_friends(client):
    """Leaderboard contains actor and their accepted friends."""
    r = client.get("/api/v1/leaderboard", headers=auth("A"))
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "my_rank" in body
    assert "as_of" in body
    ids = {item["user"]["id"] for item in body["items"]}
    # A should be in results
    r_me = client.get("/api/v1/me", headers=auth("A"))
    assert r_me.json()["id"] in ids
