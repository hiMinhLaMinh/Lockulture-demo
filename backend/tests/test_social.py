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


DISCOVERY = "00000000-0000-4000-8000-000000000015"
ASSET = "00000000-0000-4000-8000-000000000011"


def publish(client, *, friends=(), groups=(G,), key=None, actor="A"):
    return call(client, "POST", "/posts", actor, key=key, json={
        "discovery_id": DISCOVERY, "caption": "  Huế  ", "friend_ids": friends, "group_ids": groups,
    })


def test_publish_and_grants(client):
    assert publish(client, friends=[B, D]).status_code == 422
    assert publish(client, groups=[G, str(uuid4())]).status_code == 404
    assert publish(client, groups=[]).status_code == 422
    assert publish(client, actor="B").status_code == 404
    key = uuid4()
    created = publish(client, friends=[B] * 51, groups=[G] * 11, key=key)
    assert created.status_code == 201
    assert publish(client, friends=[B], key=key).json() == created.json()
    post = created.json()
    assert post["caption"] == "Huế"
    assert post["audience"] == {"friend_ids": [B], "group_ids": [G]}
    post_path = f"/posts/{post['id']}"
    assert call(client, "GET", "/posts", "C").json()["items"] == []
    assert call(client, "GET", post_path, "C").status_code == 404
    assert call(client, "GET", "/posts", "B").json()["items"] == [{**post, "audience": None}]
    url_path = f"/assets/{ASSET}/url?post_id={post['id']}"
    url = call(client, "GET", url_path, "B")
    assert url.status_code == 200 and url.headers["cache-control"] == "no-store"
    assert client.get(url.json()["url"]).headers["content-type"].startswith("image/svg+xml")
    assert call(client, "GET", url_path, "C").status_code == 404
    assert call(client, "GET", f"/assets/{ASSET}/url", "B").status_code == 404
    assert call(client, "DELETE", f"/friends/{B}").status_code == 204
    assert call(client, "DELETE", f"/groups/{G}").status_code == 204
    assert call(client, "GET", post_path, "B").status_code == 200
    assert call(client, "GET", f"/posts?group_id={G}", "B").status_code == 404
    assert call(client, "DELETE", post_path, "B").status_code == 403
    for _ in range(2):
        assert call(client, "DELETE", post_path).status_code == 204
    assert call(client, "GET", post_path, "B").status_code == 404
    assert publish(client, groups=[], friends=[C]).status_code == 409
    assert call(client, "GET", f"/discoveries/{DISCOVERY}").status_code == 200
    assert call(client, "GET", f"/discoveries/{DISCOVERY}", "B").status_code == 404


def test_membership_incarnation_and_comment_cleanup(client):
    post_id = publish(client).json()["id"]
    path = f"/posts/{post_id}"
    comment = call(client, "POST", f"{path}/comments", "B", json={"text": "  Hay  "}).json()
    assert comment["text"] == "Hay"
    comment_path = f"/comments/{comment['id']}"
    assert call(client, "DELETE", comment_path).status_code == 403
    members = f"/groups/{G}/members"
    call(client, "DELETE", f"{members}/{B}", "B")
    call(client, "POST", members, json={"user_ids": [B, C]})
    assert call(client, "POST", f"{path}/shares", json={"group_ids": [G]}).status_code == 200
    for actor in ("B", "C"):
        assert call(client, "GET", path, actor).status_code == 404
        assert call(client, "GET", f"/posts?group_id={G}", actor).json()["items"] == []
        assert call(client, "GET", f"/groups/{G}", actor).json()["post_count"] == 0
        assert call(client, "GET", f"/assets/{ASSET}/url?post_id={post_id}", actor).status_code == 404
    for _ in range(2):
        assert call(client, "DELETE", comment_path, "B").status_code == 204
    assert call(client, "GET", path).json()["comment_count"] == 0
    second = call(client, "POST", "/groups", json={"name": "Khác", "member_ids": [C]}).json()["id"]
    assert call(client, "POST", f"{path}/shares", json={"group_ids": [second, str(uuid4())]}).status_code == 404
    assert call(client, "GET", path, "C").status_code == 404
    assert call(client, "POST", f"{path}/shares", json={"group_ids": [second]}).status_code == 200
    assert call(client, "GET", path, "C").status_code == 200
    assert call(client, "GET", f"/posts?group_id={G}", "C").json()["items"] == []


def test_reactions_comments_and_rank(client, services):
    from datetime import datetime, timezone

    services.clock = lambda: datetime(2026, 11, 12, tzinfo=timezone.utc)
    post_id = publish(client).json()["id"]
    path = f"/posts/{post_id}"
    reaction = f"{path}/reaction"
    assert call(client, "PUT", reaction, "C", json={"reaction": "heart"}).status_code == 404
    assert call(client, "PUT", reaction, "B", json={"reaction": "heart"}).status_code == 200
    key = uuid4()
    changed = call(client, "PUT", reaction, "B", key=key, json={"reaction": "wow"})
    assert changed.json()["counts"] == {"heart": 0, "clap": 0, "wow": 1}
    assert call(client, "PUT", reaction, "B", key=key, json={"reaction": "wow"}).json() == changed.json()
    assert call(client, "DELETE", reaction, "B").status_code == 204
    comments = f"{path}/comments"
    assert call(client, "POST", comments, json={"text": " "}).status_code == 422
    assert call(client, "POST", comments, json={"text": "😮" * 301}).status_code == 422
    for _ in range(51):
        assert call(client, "POST", comments, json={"text": "😮" * 300}).status_code == 201
    first = call(client, "GET", comments, params={"limit": 50}).json()
    assert len(first["items"]) == 50
    second = call(client, "GET", comments, params={"cursor": first["next_cursor"]}).json()
    assert second["next_cursor"] is None and len(second["items"]) == 1
    assert second["items"][0]["id"] not in {row["id"] for row in first["items"]}
    assert call(client, "GET", "/posts", params={"cursor": first["next_cursor"]}).status_code == 422
    assert [row["rank"] for row in call(client, "GET", "/leaderboard").json()["items"]] == [1, 1, 3]
