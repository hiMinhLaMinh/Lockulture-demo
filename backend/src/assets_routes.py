"""Asset upload intake and submission pipeline routes.

Covers:
  POST   /assets                   — register upload slot, return signed upload URL
  GET    /assets/{asset_id}/url    — issue signed read URL (60s) after ACL check
  POST   /submissions              — intake: validate, create job, outbox
  GET    /submissions/{id}         — get submission status
  POST   /submissions/{id}/retry   — retry with same idempotency key

Upload flow:
  1. Client calls POST /assets → gets asset_id + signed upload URL
  2. Client uploads JPEG/PNG to Storage via signed URL
  3. Backend (or webhook) confirms upload → asset.state = "ready"
  4. Client calls POST /submissions with asset_id
"""
import datetime
import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from .firebase import get_db, get_storage_bucket
from .social.core import SocialError, digest, now, require, timestamp

router = APIRouter(prefix="/api/v1")
CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
CONFIG = json.loads((CONTRACTS / "fixtures/config.json").read_text(encoding="utf-8"))

MAX_BYTES = CONFIG["max_upload_bytes"]
SIGNED_READ_EXPIRY_SECONDS = 60
SIGNED_UPLOAD_EXPIRY_SECONDS = 300  # 5 min to upload
_LOCAL_URL_KEY = secrets.token_bytes(32)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssetInput(Input):
    mime_type: Literal["image/jpeg", "image/png", "image/webp"]
    byte_size: int = Field(ge=1, le=MAX_BYTES)
    sha256: str = Field(min_length=64, max_length=64)
    width: int = Field(ge=1, le=20_000)
    height: int = Field(ge=1, le=20_000)


class SubmissionInput(Input):
    session_id: UUID | None = None
    asset_id: UUID
    mode: Literal["free", "mission"]
    mission_id: UUID | None = None


def _actor(request: Request, authorization: Annotated[str | None, Header()] = None) -> str:
    from .platform_routes import _resolve_fixture_actor
    from firebase_admin import auth as firebase_auth
    import hashlib

    scheme, _, token = (authorization or "").partition(" ")
    if not (scheme.lower() == "bearer" and token):
        raise SocialError(401, "Authentication required")

    env = os.getenv("ENV", "production")
    if env in {"development", "test"} and os.getenv("LOCKULTURE_SOCIAL_FIXTURES") == "1":
        if token.startswith("lockulture-dev-"):
            return _resolve_fixture_actor(token)

    db = get_db()
    try:
        decoded = firebase_auth.verify_id_token(token)
    except Exception as exc:
        raise SocialError(401, "Invalid or expired token") from exc
    if not decoded.get("email_verified", False):
        raise SocialError(401, "Email not verified")
    firebase_uid = decoded["uid"]
    id_key = hashlib.sha256(firebase_uid.encode()).hexdigest()
    snap = db.collection("auth_identities").document(id_key).get()
    if not snap.exists:
        raise SocialError(401, "Authentication required")
    return snap.to_dict()["user_id"]


Actor = Annotated[str, Depends(_actor)]


def _storage_type() -> str:
    value = os.getenv("STORAGE_TYPE", "firebase").strip().lower()
    if value not in {"firebase", "local"}:
        raise RuntimeError("STORAGE_TYPE must be 'firebase' or 'local'")
    if value == "local" and os.getenv("ENV", "production") not in {"development", "test"}:
        raise RuntimeError("Local asset storage is only available in development or test")
    return value


def _local_path(object_path: str) -> Path:
    root = Path(os.getenv("LOCAL_STORAGE_DIR", "uploads")).resolve()
    path = (root / object_path).resolve()
    if root not in path.parents:
        raise RuntimeError("Asset path is outside the local storage directory")
    return path


def _local_signature(asset_id: str, expires: int) -> str:
    return hmac.new(_LOCAL_URL_KEY, f"{asset_id}:{expires}".encode(), hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# POST /assets — register upload slot
# ---------------------------------------------------------------------------

@router.post("/assets", operation_id="uploadAsset", status_code=201)
def create_asset(body: AssetInput, actor: Actor, request: Request,
                 key: Annotated[UUID, Header(alias="Idempotency-Key")]):
    db = get_db()
    asset_id = str(uuid4())
    # Prefix: discoveries/owner_id/asset_id.jpg
    ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[body.mime_type]
    object_path = f"discoveries/{actor}/{asset_id}.{ext}"

    asset_doc = {
        "schema_version": 1,
        "id": asset_id,
        "owner_id": actor,
        "object_path": object_path,
        "sha256": body.sha256,
        "mime_type": body.mime_type,
        "byte_size": body.byte_size,
        "width": body.width,
        "height": body.height,
        "state": "pending",
        "created_at": now(),
    }

    if _storage_type() == "local":
        upload_url = (
            f"{str(request.base_url).rstrip('/')}/api/v1/assets/{asset_id}/upload"
        )
    else:
        bucket = get_storage_bucket()
        blob = bucket.blob(object_path)
        upload_url = blob.generate_signed_url(
            expiration=datetime.timedelta(seconds=SIGNED_UPLOAD_EXPIRY_SECONDS),
            method="PUT",
            content_type=body.mime_type,
            version="v4",
        )

    db.collection("assets").document(asset_id).set(asset_doc)
    return {"asset_id": asset_id, "upload_url": upload_url}


@router.put("/assets/{asset_id}/upload", include_in_schema=False)
async def upload_local_asset(asset_id: UUID, actor: Actor, request: Request):
    require(_storage_type() == "local", 404, "Asset not found")
    db = get_db()
    asset_ref = db.collection("assets").document(str(asset_id))
    snapshot = asset_ref.get()
    require(snapshot.exists, 404, "Asset not found")
    asset = snapshot.to_dict()
    require(asset["owner_id"] == actor, 404, "Asset not found")
    require(asset.get("state") == "pending", 409, "Asset is not awaiting upload")

    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    require(content_type == asset["mime_type"], 415, "Invalid asset content type")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        require(len(body) <= MAX_BYTES, 413, "Asset exceeds maximum size")
    require(len(body) == asset["byte_size"], 409, "Asset size mismatch")
    require(hashlib.sha256(body).hexdigest() == asset["sha256"], 409, "Asset hash mismatch")

    target = _local_path(asset["object_path"])
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    temporary.write_bytes(body)
    temporary.replace(target)
    asset_ref.update({"state": "ready"})
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# GET /assets/{asset_id}/url — signed read URL
# ---------------------------------------------------------------------------

@router.get("/assets/{asset_id}/url", operation_id="getAssetUrl")
def get_asset_url(asset_id: UUID, actor: Actor, response: Response, request: Request,
                  post_id: UUID | None = None):
    from .social.core import SocialRepository
    db = get_db()
    snap = db.collection("assets").document(str(asset_id)).get()
    require(snap.exists, 404, "Asset not found")
    asset = snap.to_dict()

    if asset["owner_id"] != actor:
        # Need a valid post context
        require(post_id is not None, 404, "Asset not found")
        post_snap = db.collection("posts").document(str(post_id)).get()
        require(post_snap.exists and not post_snap.to_dict().get("deleted_at"), 404, "Asset not found")
        post = post_snap.to_dict()
        require(post.get("asset_id") == str(asset_id), 404, "Asset not found")
        # Minimal ACL: actor must appear in direct_user_ids or current group membership
        direct = post.get("direct_user_ids", [])
        if actor not in [post["author_id"]] + direct:
            # Check group grants
            group_grants = post.get("group_grants", {})
            has_group_access = False
            for group_id, snapshot_members in group_grants.items():
                group_snap = db.collection("groups").document(group_id).get()
                if group_snap.exists:
                    group = group_snap.to_dict()
                    if not group.get("deleted_at") and actor in group.get("members", {}):
                        inc_id = group["members"][actor].get("incarnation_id")
                        if inc_id in snapshot_members:
                            has_group_access = True
                            break
            require(has_group_access, 404, "Asset not found")

    require(asset.get("state") in ("ready", "attached"), 404, "Asset not ready")

    expires_at = now() + datetime.timedelta(seconds=SIGNED_READ_EXPIRY_SECONDS)
    if _storage_type() == "local":
        expires = int(expires_at.timestamp())
        signature = _local_signature(str(asset_id), expires)
        url = (
            f"{str(request.base_url).rstrip('/')}/api/v1/assets/{asset_id}/file"
            f"?expires={expires}&signature={signature}"
        )
    else:
        blob = get_storage_bucket().blob(asset["object_path"])
        url = blob.generate_signed_url(
            expiration=datetime.timedelta(seconds=SIGNED_READ_EXPIRY_SECONDS),
            method="GET",
            version="v4",
        )
    response.headers["Cache-Control"] = "no-store"
    return {"url": url, "expires_at": timestamp(expires_at)}


@router.get("/assets/{asset_id}/file", include_in_schema=False)
def get_local_asset(asset_id: UUID, expires: int, signature: str):
    require(_storage_type() == "local", 404, "Asset not found")
    require(expires > int(now().timestamp()), 404, "Asset not found")
    expected = _local_signature(str(asset_id), expires)
    require(hmac.compare_digest(signature, expected), 404, "Asset not found")
    snapshot = get_db().collection("assets").document(str(asset_id)).get()
    require(snapshot.exists, 404, "Asset not found")
    asset = snapshot.to_dict()
    require(asset.get("state") in ("ready", "attached"), 404, "Asset not found")
    path = _local_path(asset["object_path"])
    require(path.is_file(), 404, "Asset not found")
    return FileResponse(path, media_type=asset["mime_type"], headers={"Cache-Control": "no-store"})


# ---------------------------------------------------------------------------
# POST /submissions — intake
# ---------------------------------------------------------------------------

@router.post("/submissions", operation_id="startSubmission", status_code=202)
def submit_photo(body: SubmissionInput, actor: Actor,
                 key: Annotated[UUID, Header(alias="Idempotency-Key")]):
    from .jobs import intake_submission
    result = intake_submission(actor, body, str(key))
    return result


@router.get("/submissions/{submission_id}", operation_id="getSubmission")
def get_submission(submission_id: UUID, actor: Actor):
    db = get_db()
    snap = db.collection("submissions").document(str(submission_id)).get()
    require(snap.exists, 404, "Submission not found")
    sub = snap.to_dict()
    require(sub["owner_id"] == actor, 404, "Submission not found")
    return _submission_dto(sub)


@router.post("/submissions/{submission_id}/retry", operation_id="retrySubmission", status_code=202)
def retry_submission(submission_id: UUID, actor: Actor,
                     key: Annotated[UUID, Header(alias="Idempotency-Key")]):
    db = get_db()
    snap = db.collection("submissions").document(str(submission_id)).get()
    require(snap.exists, 404, "Submission not found")
    sub = snap.to_dict()
    require(sub["owner_id"] == actor, 404, "Submission not found")
    require(sub["status"] in ("failed", "pending"), 409, "Submission already complete")

    # Re-enqueue via same job
    job_id = sub.get("job_id")
    if job_id:
        from .jobs import reenqueue_job
        reenqueue_job(job_id)

    return _submission_dto(sub)


def _submission_dto(sub: dict) -> dict:
    return {
        "id": sub["id"],
        "status": sub["status"],
        "verdict": sub.get("verdict"),
        "discovery_id": sub.get("discovery_id"),
        "knowledge": sub.get("knowledge"),
        "error": sub.get("error"),
        "created_at": _ts(sub.get("created_at")),
    }


def _ts(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return timestamp(value)
    return value
