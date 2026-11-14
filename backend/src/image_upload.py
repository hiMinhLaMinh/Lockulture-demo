"""Validate, reserve and finalize an immutable private image."""
from datetime import timedelta
from hashlib import sha256
from io import BytesIO
from uuid import uuid4

from google.cloud.exceptions import NotFound
from google.cloud.firestore import transactional
from PIL import Image, ImageOps, UnidentifiedImageError

from .firebase import get_db, get_storage_bucket
from .social.core import SocialError, digest, now, require, timestamp


def normalize_image(data: bytes, max_pixels: int) -> tuple[bytes, int, int]:
    try:
        with Image.open(BytesIO(data), formats=["JPEG", "PNG", "WEBP"]) as source:
            require(source.width * source.height <= max_pixels, 413, "Image has too many pixels")
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((1080, 1080), Image.Resampling.LANCZOS)
            image.info.clear()
            result = BytesIO()
            image.save(result, format="JPEG", quality=85)
            return result.getvalue(), image.width, image.height
    except Image.DecompressionBombError as exc:
        raise SocialError(413, "Image has too many pixels") from exc
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise SocialError(415, "Invalid JPEG, PNG or WebP image") from exc


def remove_object(path, local_path):
    if local_path:
        local_path(path).unlink(missing_ok=True)
        return
    try:
        get_storage_bucket().blob(path).delete()
    except NotFound:
        pass


def store_image(actor, key, data, config, local_path):
    jpeg, width, height = normalize_image(data, config["max_image_pixels"])
    db = get_db()
    ref = db.collection("idempotency_keys").document(digest([actor, "uploadAsset", key]))
    request_hash = sha256(data).hexdigest()
    lease = str(uuid4())
    pending_ref = db.collection("asset_uploads").document(lease)

    @transactional
    def reserve(tx):
        time = now()
        previous = ref.get(transaction=tx).to_dict()
        asset_id = str(uuid4())
        if previous and previous["expires_at"] > time:
            require(previous["request_hash"] == request_hash, 409, "Idempotency key already used")
            if previous.get("response"):
                return previous["response"], None
            if previous["lease_until"] > time:
                raise SocialError(409, "Upload in progress", retry_after=2)
            asset_id = previous["asset_id"]
        path = f"discoveries/{actor}/{asset_id}/{lease}.jpg"
        tx.set(ref, {
            "schema_version": 1, "request_hash": request_hash, "asset_id": asset_id,
            "lease": lease, "lease_until": time + timedelta(seconds=60),
            "expires_at": time + timedelta(days=config["idempotency_retention_days"]),
        })
        tx.create(pending_ref, {
            "schema_version": 1, "object_path": path, "reservation_id": ref.id,
            "lease_until": time + timedelta(seconds=60),
            "cleanup_after": time + timedelta(hours=config["orphan_asset_retention_hours"]),
        })
        return {"id": asset_id, "mime_type": "image/jpeg", "width": width, "height": height,
                "byte_size": len(jpeg), "created_at": timestamp(time)}, path

    dto, path = reserve(db.transaction())
    if path is None:
        return dto

    @transactional
    def finalize(tx):
        pending = pending_ref.get(transaction=tx).to_dict()
        reservation = ref.get(transaction=tx).to_dict() or {}
        if not pending or reservation.get("lease") != lease or reservation["lease_until"] <= now():
            return False
        tx.create(db.collection("assets").document(dto["id"]), {
            **dto, "schema_version": 1, "owner_id": actor, "state": "ready",
            "object_path": path, "created_at": now(), "sha256": sha256(jpeg).hexdigest(),
        })
        tx.update(ref, {"response": dto, "status_code": 201})
        tx.delete(pending_ref)
        return True

    if local_path:
        target = local_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(jpeg)
    else:
        get_storage_bucket().blob(path).upload_from_string(jpeg, content_type="image/jpeg", if_generation_match=0)
    # A commit with an unknown outcome must leave the object available for replay.
    if not finalize(db.transaction()):
        remove_object(path, local_path)
        pending_ref.delete()
        raise SocialError(409, "Upload lease expired", retry_after=2)
    return dto
