"""Lease-fenced provider reservations and durable checkpoints."""

from google.cloud.firestore import transactional
from ..jobs import transaction, CONFIG, read, write
from ..social.core import now, require

LIMITS = {
    "maps_calls": "max_maps_calls",
    "gemini_calls": "max_gemini_calls_search",
    "image_calls": "max_image_calls_souvenir",
}


def current(job, token):
    time = now()
    return bool(
        job
        and job["status"] == "running"
        and job.get("lease_token") == token
        and job["lease_until"] > time
        and job["deadline"] > time
    )


def reserve(db, job_id, token, counter):
    @transactional
    def run(tx):
        job = read(db, "jobs", job_id, tx)
        require(current(job, token), 409, "Worker lease expired")
        limit = (
            CONFIG["max_gemini_calls_submission"]
            if counter == "gemini_calls"
            and job.get("kind", "submission") == "submission"
            else CONFIG[LIMITS[counter]]
        )
        require(job.get(counter, 0) < limit, 409, "Provider budget exhausted")
        write(db, tx, "jobs", job_id, {counter: job.get(counter, 0) + 1}, merge=True)

    transaction(db, run)


def checkpoint(db, job_id, token, value, stage="persisting"):
    @transactional
    def run(tx):
        job = read(db, "jobs", job_id, tx)
        require(current(job, token), 409, "Worker lease expired")
        write(
            db,
            tx,
            "jobs",
            job_id,
            {"checkpoint": value, "stage": stage, "updated_at": now()},
            merge=True,
        )

    transaction(db, run)
