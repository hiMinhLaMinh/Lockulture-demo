"""One image call per completion; private upload and lease-fenced publication."""

from datetime import timedelta
from uuid import uuid5, NAMESPACE_URL
from google.cloud.firestore import transactional
from ..jobs import transaction, read, write
from ..social.core import now, require
from .lease import reserve, checkpoint, current


def process(db, job, token):
    saved = job.get("checkpoint")
    if saved is None:
        from ..media.storage import load_owned_image, put_private_image
        from ..media.souvenir import generate_souvenir

        completion = read(db, "mission_completions", job["discovery_id"])
        require(
            completion
            and completion["owner_id"] == job["owner_id"]
            and completion["consent"],
            409,
            "Souvenir consent unavailable",
        )
        mission = read(db, "missions", completion["mission_id"])
        images = [
            load_owned_image(actor_id=job["owner_id"], asset_id=a)
            for a in completion["evidence_asset_ids"]
        ]
        portrait = (
            load_owned_image(
                actor_id=job["owner_id"], asset_id=completion["portrait_asset_id"]
            )
            if completion.get("portrait_asset_id")
            else None
        )
        reserve(db, job["id"], token, "image_calls")
        image, mime = generate_souvenir(
            evidence_images=images,
            portrait=portrait,
            place_context={
                "name": mission["place_name"],
                "place_id": mission["place_id"],
                "era_id": mission["era_id"],
                "motif": mission["badge_design"]["motif"],
                "summary": mission["heritage"]["summary"],
            },
            timeout_s=60,
        )
        path = f"discoveries/{job['owner_id']}/souvenirs/{job['id']}/{token}"
        # Track even a crash during upload; existing cleanup handles this reservation.
        reservation = job["id"] + "-" + token
        db.collection("asset_uploads").document(reservation).set(
            {"object_path": path, "cleanup_after": now() + timedelta(hours=24)}
        )
        metadata = put_private_image(
            object_path=path, image_bytes=image, mime_type=mime
        )
        require(metadata["object_path"] == path, 409, "Storage path mismatch")
        saved = {
            "metadata": metadata,
            "reservation": reservation,
            "asset_id": str(
                uuid5(NAMESPACE_URL, "lockulture:souvenir-asset:" + job["id"])
            ),
        }
        checkpoint(db, job["id"], token, saved)

    @transactional
    def finalize(tx):
        latest = read(db, "jobs", job["id"], tx)
        require(current(latest, token), 409, "Worker lease expired")
        existing = read(db, "assets", saved["asset_id"], tx)
        if existing:
            require(
                existing["owner_id"] == job["owner_id"]
                and existing.get("discovery_id") == job["discovery_id"],
                409,
                "Asset conflict",
            )
        else:
            write(
                db,
                tx,
                "assets",
                saved["asset_id"],
                {
                    **saved["metadata"],
                    "id": saved["asset_id"],
                    "schema_version": 1,
                    "owner_id": job["owner_id"],
                    "state": "attached",
                    "purpose": "souvenir",
                    "discovery_id": job["discovery_id"],
                    "created_at": now(),
                },
            )
        tx.delete(db.collection("asset_uploads").document(saved["reservation"]))
        write(
            db,
            tx,
            "jobs",
            job["id"],
            {
                "status": "succeeded",
                "stage": "done",
                "asset_id": saved["asset_id"],
                "updated_at": now(),
                "error": None,
                "lease_token": None,
                "lease_until": None,
            },
            merge=True,
        )

    transaction(db, finalize)
