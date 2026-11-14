"""Private image upload, signed reads, and submission HTTP routes."""
import datetime
import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urljoin
from uuid import UUID

from fastapi import APIRouter, File, Header, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .missions.location import CaptureLocation
from .firebase import get_db
from .image_upload import store_image
from .platform_routes import Actor
from .social.core import now, require, timestamp
from .social.posts import visible_post

router = APIRouter(prefix="/api/v1")
CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
CONFIG = json.loads((CONTRACTS / "fixtures/config.json").read_text(encoding="utf-8"))

MAX_BYTES = CONFIG["max_upload_bytes"]
SIGNED_READ_EXPIRY_SECONDS = 60
_LOCAL_URL_KEY = secrets.token_bytes(32)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SubmissionInput(Input):
    asset_id: UUID
    mode: Literal["free", "mission"]
    mission_id: UUID | None
    mission_version: int | None = Field(ge=1)
    evaluation_session_id: UUID | None
    expected_previous_submission_id: UUID | None

    capture_location: CaptureLocation | None = None
    souvenir_opt_in: bool = False
    portrait_asset_id: UUID | None = None

    @model_validator(mode="after")
    def validate_context(self):
        if (self.mode == "mission") != (self.mission_id is not None and self.mission_version is not None):
            raise ValueError("Mission mode requires mission ID and version")
        if self.mode == "free" and (self.mission_id is not None or self.mission_version is not None):
            raise ValueError("Free mode cannot specify a mission")
        if (self.evaluation_session_id is None) != (self.expected_previous_submission_id is None):
            raise ValueError("Continuation requires both session and previous submission")
        if self.mode == "mission" and self.capture_location is None:
            raise ValueError("Mission requires capture GPS")
        if self.portrait_asset_id and not self.souvenir_opt_in:
            raise ValueError("Portrait requires souvenir consent")
        return self


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
# Asset upload and signed reads
# ---------------------------------------------------------------------------

@router.post("/assets", operation_id="uploadAsset", status_code=201)
def create_asset(actor: Actor, photo: Annotated[UploadFile, File()],
                 key: Annotated[UUID, Header(alias="Idempotency-Key")]):
    data = photo.file.read(MAX_BYTES + 1)
    require(len(data) <= MAX_BYTES, 413, "Asset exceeds maximum size")
    local_path = _local_path if _storage_type() == "local" else None
    return store_image(actor, str(key), data, CONFIG, local_path)


@router.get("/assets/{asset_id}/url", operation_id="getAssetUrl")
def get_asset_url(asset_id: UUID, actor: Actor, response: Response, request: Request,
                  post_id: UUID | None = None):
    asset = get_db().collection("assets").document(str(asset_id)).get().to_dict()
    require(asset and asset["state"] in {"ready", "in_submission", "attached"}, 404, "Asset not found")
    services = request.app.state.social
    if asset["owner_id"] != actor:
        require(post_id is not None, 404, "Asset not found")
        post = services.repository.read(lambda tx: visible_post(tx, actor, str(post_id)))
        require(post["asset_id"] == str(asset_id), 404, "Asset not found")
    expires_at = now() + datetime.timedelta(seconds=SIGNED_READ_EXPIRY_SECONDS)
    url = services.urls.issue(str(asset_id), expires_at)
    response.headers["Cache-Control"] = "no-store"
    return {"url": urljoin(str(request.base_url), url), "expires_at": timestamp(expires_at)}


@router.get("/assets/{asset_id}/file", include_in_schema=False)
def get_local_asset(asset_id: UUID, expires: int, signature: str):
    require(_storage_type() == "local", 404, "Asset not found")
    require(expires > int(now().timestamp()), 404, "Asset not found")
    expected = _local_signature(str(asset_id), expires)
    require(hmac.compare_digest(signature, expected), 404, "Asset not found")
    snapshot = get_db().collection("assets").document(str(asset_id)).get()
    require(snapshot.exists, 404, "Asset not found")
    asset = snapshot.to_dict()
    require(asset.get("state") in ("ready", "in_submission", "attached"), 404, "Asset not found")
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
    from .jobs import read, submission_dto

    db = get_db()
    submission = read(db, "submissions", str(submission_id))
    require(submission and submission["owner_id"] == actor, 404, "Submission not found")
    return submission_dto(submission, read(db, "evaluation_sessions", submission["evaluation_session_id"]))


@router.post("/submissions/{submission_id}/retry", operation_id="retrySubmission", status_code=202)
def retry_submission(submission_id: UUID, body: Input, actor: Actor,
                     key: Annotated[UUID, Header(alias="Idempotency-Key")]):
    from .jobs import retry_submission as retry

    return retry(actor, str(submission_id), str(key))
