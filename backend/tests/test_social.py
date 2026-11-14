from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.src.main import create_app
from backend.src.social.fixtures import load_fixture_services

A, B, C, D = (f"00000000-0000-4000-8000-{n:012d}" for n in range(1, 5))
G = "00000000-0000-4000-8000-000000000016"


@pytest.fixture
def services():
    return load_fixture_services()


@pytest.fixture
def client(monkeypatch, services):
    monkeypatch.setenv("ENV", "test")
    with TestClient(create_app(social=services), raise_server_exceptions=False) as transport:
        yield transport


def call(client, method, path, actor="A", *, key=None, **kwargs):
    headers = {"Authorization": f"Bearer lockulture-dev-{actor}"}
    if method != "GET":
        headers["Idempotency-Key"] = str(key or uuid4())
    return client.request(method, "/api/v1" + path, headers=headers, **kwargs)


def test_health_and_fixture_gate(client, monkeypatch):
    assert client.get("/api/v1/health").json() == {"status": "ok", "contract_version": "1.0.0"}
    assert client.get("/health").json()["status"] == "HEALTHY"
    assert client.get("/api/v1/friends").json()["error"]["code"] == "unauthorized"
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("LOCKULTURE_SOCIAL_FIXTURES", "1")
    with pytest.raises(RuntimeError):
        create_app()
    monkeypatch.delenv("LOCKULTURE_SOCIAL_FIXTURES")
    assert call(TestClient(create_app()), "GET", "/friends").status_code == 401


def test_users_and_cursor(client):
    assert call(client, "GET", "/users?query=THAO").json()["items"][0]["id"] == C
    assert call(client, "GET", "/users?query=Minh").json()["items"][0]["id"] == B
    assert "email" not in call(client, "GET", f"/users/{B}").json()
    assert call(client, "GET", "/users?query=x").status_code == 422
    first = call(client, "GET", "/friends?limit=1").json()
    cursor = first["next_cursor"]
    assert call(client, "GET", "/friends", params={"cursor": cursor}).json() == {
        "items": [call(client, "GET", f"/users/{C}").json()], "next_cursor": None,
    }
    assert call(client, "GET", "/friends", "B", params={"cursor": cursor}).status_code == 422


def test_friend_lifecycle(client):
    key = uuid4()
    request = call(client, "POST", "/friend-requests", key=key, json={"target_user_id": D})
    assert request.status_code == 201
    assert call(client, "POST", "/friend-requests", key=key, json={"target_user_id": D}).json() == request.json()
    assert call(client, "POST", "/friend-requests", key=key, json={"target_user_id": C}).json()["error"]["code"] == "idempotency_conflict"
    assert call(client, "POST", "/friend-requests", "D", json={"target_user_id": A}).status_code == 409
    path = "/friend-requests/" + request.json()["id"]
    assert call(client, "GET", "/friend-requests", "D").json()["items"] == [request.json()]
    assert call(client, "PATCH", path, "C", json={"action": "accept"}).status_code == 404
    assert call(client, "PATCH", path, json={"action": "accept"}).status_code == 403
    assert call(client, "PATCH", path, "D", json={"action": "accept"}).json()["status"] == "accepted"
    assert call(client, "GET", "/friends", "D").json()["items"][0]["id"] == A
    for _ in range(2):
        response = call(client, "DELETE", f"/friends/{D}")
        assert response.status_code == 204 and response.content == b""


def test_group_roles_and_atomic_recipient_validation(client):
    assert call(client, "GET", f"/groups/{G}", "D").status_code == 404
    assert call(client, "PATCH", f"/groups/{G}", "B", json={"name": "x"}).status_code == 403
    assert call(client, "DELETE", f"/groups/{G}/members/{A}").status_code == 409
    members = f"/groups/{G}/members"
    assert call(client, "POST", members, json={"user_ids": [C, D]}).status_code == 422
    assert call(client, "GET", members).json()["items"][-1]["user"]["id"] != C
    assert call(client, "POST", members, json={"user_ids": [C] * 25}).json()["member_count"] == 3
    assert call(client, "POST", members, json={"user_ids": [C]}).json()["member_count"] == 3
    assert call(client, "DELETE", f"{members}/{C}", "C").status_code == 204
    created = call(client, "POST", "/groups", json={"name": "  Nhóm mới ", "member_ids": [B]})
    assert created.status_code == 201 and created.json()["name"] == "Nhóm mới"
    assert call(client, "DELETE", f"/groups/{G}").status_code == 204
    assert call(client, "GET", f"/groups/{G}").status_code == 404
