"""Platform routes: /me, /timeline, /discoveries, /leaderboard.

These routes use Firestore directly (not through SocialRepository)
because they deal with eras, profiles, and XP ledger — not social graph data.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StringConstraints

from .firebase import get_db
from .social.core import SocialError, digest, normalized, page, require, timestamp, created_key

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
router = APIRouter(prefix="/api/v1")

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProfilePatch(Input):
    display_name: Name | None = None
    bio: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

def require_actor(request: Request, authorization: Annotated[str | None, Header()] = None) -> str:
    """Resolve Firebase ID token to internal UUID. Used in platform routes."""
    from .auth import FirebaseActorResolver, _create_or_get_identity, _uid_key
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
def patch_me(body: ProfilePatch, actor: Actor,
             key: Annotated[UUID, Header(alias="Idempotency-Key")]):
    db = get_db()
    updates: dict = {}
    if body.display_name is not None:
        updates["display_name"] = body.display_name
    if body.bio is not None:
        updates["bio"] = body.bio
    if not updates:
        snap = db.collection("profiles").document(actor).get()
        return _profile_dto(snap.to_dict())
    db.collection("profiles").document(actor).update(updates)
    snap = db.collection("profiles").document(actor).get()
    return _profile_dto(snap.to_dict())


def _profile_dto(data: dict) -> dict:
    return {
        "id": data["id"],
        "display_name": data["display_name"],
        "username": data["username"],
        "bio": data.get("bio", ""),
        "xp": data.get("xp_total", 0),
    }


# ---------------------------------------------------------------------------
# /timeline
# ---------------------------------------------------------------------------

@router.get("/timeline", operation_id="getTimeline")
def get_timeline(actor: Actor):
    # Load canonical eras
    eras_data = json.loads((CONTRACTS / "fixtures/eras.json").read_text(encoding="utf-8"))

    # Load actor's era_progress
    progress_by_era: dict = {}
    env = os.getenv("ENV", "production")
    fixtures_on = os.getenv("LOCKULTURE_SOCIAL_FIXTURES") == "1"
    if not (env in {"development", "test"} and fixtures_on and actor in {
        row["id"] for row in json.loads(
            (CONTRACTS / "fixtures/identities.json").read_text(encoding="utf-8")
        )["users"].values()
    }):
        db = get_db()
        progress_snaps = (db.collection("era_progress")
                          .where("owner_id", "==", actor)
                          .stream())
        for s in progress_snaps:
            d = s.to_dict()
            era_id = d.get("era_id")
            if era_id:
                progress_by_era[era_id] = d

    items = []
    for era in sorted(eras_data, key=lambda e: e["sort_order"]):
        prog = progress_by_era.get(era["id"], {})
        fragment_count = prog.get("fragment_count", 0)
        goal = era["fragment_goal"]
        if fragment_count == 0:
            status = "locked"
        elif fragment_count >= goal:
            status = "complete"
        else:
            status = "in_progress"
        items.append({
            "era_id": era["id"],
            "name": era["name"],
            "period": era["period"],
            "sort_order": era["sort_order"],
            "fragment_count": fragment_count,
            "fragment_goal": goal,
            "status": status,
        })

    return {"items": items}


# ---------------------------------------------------------------------------
# /leaderboard — overrides the in-memory version from social/http.py
# ---------------------------------------------------------------------------
# (Already implemented in social/http.py using repository; no change needed
#  as long as the repository contains xp from profiles.)
