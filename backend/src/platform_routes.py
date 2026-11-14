"""Profile bootstrap, profile editing and timeline routes."""
import json
import os
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from .firebase import get_db
from .social.core import SocialError, mutate, require

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
router = APIRouter(prefix="/api/v1")

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProfilePatch(Input):
    display_name: Name | None = None
    username: Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{3,24}$")] | None = None
    bio: Annotated[str, StringConstraints(max_length=160)] | None = None

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set or any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Provide at least one non-null profile field")
        return self


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

def require_actor(request: Request, authorization: Annotated[str | None, Header()] = None) -> str:
    """Resolve Firebase ID token to internal UUID. Used in platform routes."""
    from .auth import FirebaseActorResolver
    scheme, _, token = (authorization or "").partition(" ")
    if not (scheme.lower() == "bearer" and token):
        raise SocialError(401, "Authentication required")

    # Allow fixture actors in dev/test
    env = os.getenv("ENV", "production")
    fixtures_on = os.getenv("LOCKULTURE_SOCIAL_FIXTURES") == "1"
    if env in {"development", "test"} and fixtures_on and token.startswith("lockulture-dev-"):
        return _resolve_fixture_actor(token)

    resolver = FirebaseActorResolver()
    user_id = resolver.resolve(token)
    if user_id is None:
        raise SocialError(401, "Authentication required")
    return user_id


def require_actor_or_create(request: Request,
                             authorization: Annotated[str | None, Header()] = None) -> str:
    """Like require_actor but creates profile on first call (for GET /me)."""
    from .auth import FirebaseActorResolver

    scheme, _, token = (authorization or "").partition(" ")
    if not (scheme.lower() == "bearer" and token):
        raise SocialError(401, "Authentication required")

    env = os.getenv("ENV", "production")
    fixtures_on = os.getenv("LOCKULTURE_SOCIAL_FIXTURES") == "1"
    if env in {"development", "test"} and fixtures_on and token.startswith("lockulture-dev-"):
        return _resolve_fixture_actor(token)

    user_id, _ = FirebaseActorResolver().resolve_or_create(token)
    return user_id


def _resolve_fixture_actor(token: str) -> str:
    """Dev-only: map fixture tokens to UUIDs from identities.json."""
    identities = json.loads((CONTRACTS / "fixtures/identities.json").read_text(encoding="utf-8"))
    name = token.removeprefix("lockulture-dev-")
    user = identities["users"].get(name)
    if not user:
        raise SocialError(401, "Unknown fixture actor")
    return user["id"]


Actor = Annotated[str, Depends(require_actor)]
ActorOrCreate = Annotated[str, Depends(require_actor_or_create)]


# ---------------------------------------------------------------------------
# /me
# ---------------------------------------------------------------------------

@router.get("/me", operation_id="getMe")
def get_me(actor: ActorOrCreate):
    db = get_db()
    snap = db.collection("profiles").document(actor).get()
    if not snap.exists:
        raise SocialError(404, "Profile not found")
    return _profile_dto(snap.to_dict())


@router.patch("/me", operation_id="updateMe")
def patch_me(body: ProfilePatch, actor: Actor, request: Request,
             key: Annotated[UUID, Header(alias="Idempotency-Key")]):
    updates = body.model_dump(exclude_unset=True)

    def update(tx):
        profile = tx.get("users", actor)
        require(profile is not None, 404, "Profile not found")
        username = updates.get("username")
        if username and username != profile["username"]:
            reservation = tx.get("usernames", username)
            require(not reservation or reservation["owner_id"] == actor, 409, "Username already taken")
            previous = tx.get("usernames", profile["username"])
            if previous and previous["owner_id"] == actor:
                tx.delete("usernames", profile["username"])
            tx.put("usernames", username, {"owner_id": actor})
        profile = {**profile, **updates}
        tx.put("users", actor, profile)
        return _profile_dto(profile)

    result = mutate(request.app.state.social.repository, actor, "updateMe", str(key), [], updates, 200, update)
    if "error" in result:
        return JSONResponse({"error": result["error"]}, status_code=result["status"])
    return result["body"]


def _profile_dto(data: dict) -> dict:
    return {
        "id": data["id"],
        "display_name": data["display_name"],
        "username": data["username"],
        "bio": data.get("bio", ""),
        "xp": data.get("xp_total", data.get("xp", 0)),
    }


# ---------------------------------------------------------------------------
# /timeline
# ---------------------------------------------------------------------------

@router.get("/timeline", operation_id="getTimeline")
def get_timeline(actor: Actor):
    progress_by_era = {}
    env = os.getenv("ENV", "production")
    fixture = env in {"development", "test"} and os.getenv("LOCKULTURE_SOCIAL_FIXTURES") == "1"
    if fixture:
        eras_data = json.loads((CONTRACTS / "fixtures/eras.json").read_text(encoding="utf-8"))
    else:
        db = get_db()
        eras_data = [snap.to_dict() for snap in db.collection("eras").stream()]
        require(len(eras_data) == 10, 503, "Era catalog has not been seeded")
        for snap in db.collection("era_progress").where("owner_id", "==", actor).stream():
            progress = snap.to_dict()
            progress_by_era[progress["era_id"]] = progress

    items = []
    for era in sorted(eras_data, key=lambda e: e["sort_order"]):
        prog = progress_by_era.get(era["id"], {})
        fragment_count = prog.get("fragment_count", 0)
        goal = era["fragment_goal"]
        if fragment_count == 0:
            status = "not_started"
        elif fragment_count >= goal:
            status = "decoded"
        else:
            status = "in_progress"
        items.append({
            "id": era["id"],
            "name": era["name"],
            "period": era["period"],
            "fragment_count": fragment_count,
            "fragment_goal": goal,
            "status": status,
        })

    return {"items": items, "next_cursor": None}
