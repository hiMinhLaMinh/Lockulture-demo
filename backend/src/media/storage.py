"""Firebase private image I/O; callers retain transaction, lease and asset attachment ownership."""
from hashlib import sha256
from pathlib import PurePosixPath
from uuid import UUID

from ..firebase import get_db, get_storage_bucket
from ..social.core import SocialError
from .souvenir import MAX_BYTES, inspect_image


class MediaStorageError(Exception):
    pass


def _path(value: str) -> str:
    if (not isinstance(value, str) or not value or len(value) > 1024 or value.startswith("/")
            or "\\" in value or ":" in value or any(p in {"", ".", ".."} for p in value.split("/"))
            or str(PurePosixPath(value)) != value or not value.startswith("discoveries/")):
        raise MediaStorageError("Invalid private image object path")
    return value


def load_owned_image(*, actor_id: str, asset_id: str) -> bytes:
    try:
        UUID(asset_id)
    except (ValueError, TypeError, AttributeError):
        raise SocialError(404, "Asset not found") from None
    asset = get_db().collection("assets").document(asset_id).get().to_dict()
    if not asset or asset.get("owner_id") != actor_id or asset.get("state") not in {"ready", "in_submission", "attached"}:
        raise SocialError(404, "Asset not found")
    path = _path(asset.get("object_path"))
    try:
        blob = get_storage_bucket().blob(path)
        blob.reload(timeout=30, retry=None)
        if not blob.size or blob.size > MAX_BYTES:
            raise MediaStorageError("Stored image exceeds the byte limit")
        data = blob.download_as_bytes(if_generation_match=blob.generation, timeout=30, retry=None)
    except MediaStorageError:
        raise
    except Exception:
        raise MediaStorageError("Private image could not be read") from None
    inspect_image(data, asset.get("mime_type"))
    if not asset.get("sha256") or sha256(data).hexdigest() != asset["sha256"]:
        raise MediaStorageError("Private image checksum mismatch")
    return data


def put_private_image(*, object_path: str, image_bytes: bytes, mime_type: str) -> dict:
    path = _path(object_path)
    mime, width, height = inspect_image(image_bytes, mime_type)
    checksum = sha256(image_bytes).hexdigest()
    try:
        blob = get_storage_bucket().blob(path)
        blob.metadata = {"sha256": checksum}
        blob.upload_from_string(image_bytes, content_type=mime, if_generation_match=0,
                                timeout=30, retry=None)
    except Exception:
        raise MediaStorageError("Private image could not be stored") from None
    return {"object_path": path, "sha256": checksum, "mime_type": mime,
            "byte_size": len(image_bytes), "width": width, "height": height}
