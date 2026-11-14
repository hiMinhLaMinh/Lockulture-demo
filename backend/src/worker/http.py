"""Internal Cloud Tasks and Scheduler entry points."""
import logging
import os
from datetime import timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Response
from google.api_core.exceptions import AlreadyExists, GoogleAPICallError, RetryError
from google.auth.transport.requests import Request as GoogleRequest
from google.cloud import tasks_v2
from google.cloud.firestore import transactional
from google.oauth2 import id_token
from jsonschema import ValidationError
from pydantic import BaseModel, ConfigDict, Field

from ..award import SCHEMAS, award_result, finish_failure
from ..firebase import get_db
from ..image_upload import remove_object
from ..jobs import transaction, CONFIG, can_retry, queue, read, write
from ..social.core import SocialError, now, require
from .fixture_worker import fixture_assessment

router = APIRouter(prefix="/internal", include_in_schema=False)
logger = logging.getLogger(__name__)


class EmptyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Delivery(EmptyBody):
    generation: int = Field(ge=0)


def authenticate(identity):
    def verify(authorization: Annotated[str | None, Header()] = None):
        scheme, _, token = (authorization or "").partition(" ")
        audience = os.getenv("INTERNAL_AUDIENCE")
        email = os.getenv(identity)
        require(scheme.lower() == "bearer" and token and audience and email, 401, "OIDC required")
        try:
            claims = id_token.verify_oauth2_token(token, GoogleRequest(), audience)
        except ValueError as exc:
            raise SocialError(401, "Invalid OIDC token") from exc
        require(claims.get("email") == email and claims.get("email_verified") is True, 403, "Identity not allowed")
    return verify


task_identity = authenticate("TASK_SERVICE_ACCOUNT")
scheduler_identity = authenticate("SCHEDULER_SERVICE_ACCOUNT")


def claim(db, job_id, generation):
    @transactional
    def run(tx):
        time = now()
        job = read(db, "jobs", job_id, tx)
        outbox = read(db, "job_outbox", job_id, tx)
        if not (job and outbox and outbox["generation"] == generation and job["status"] in {"queued", "running"}):
            return None
        if job["status"] == "running" and job["lease_until"] > time:
            return None
        submission = None
        if job.get("kind", "submission") == "submission":
            submission = read(db, "submissions", job["submission_id"], tx)
            session = read(db, "evaluation_sessions", submission["evaluation_session_id"], tx)
            if session["expires_at"] <= time:
                finish_failure(db, tx, job, "session_closed", "Evaluation session expired")
                write(db, tx, "evaluation_sessions", submission["evaluation_session_id"], {"status": "expired"}, merge=True)
                return None
        if not can_retry(job, time):
            finish_failure(db, tx, job, "deadline_exceeded", "Job deadline, attempts or budget exhausted")
            return None
        lease = str(uuid4())
        write(db, tx, "jobs", job_id, {"status": "running", "stage": "finding" if job.get("kind") == "mission_search" else "evaluating", "lease_token": lease,
                                      "lease_until": time + timedelta(seconds=150),
                                      "attempts": job["attempts"] + 1}, merge=True)
        if submission:
            write(db, tx, "submissions", submission["id"], {"status": "running"}, merge=True)
        return lease, submission, job.get("checkpoint")

    return transaction(db, run)


def process_delivery(db, job_id, generation):
    claimed = claim(db, job_id, generation)
    if claimed is None:
        return
    lease, submission, checkpoint = claimed

    @transactional
    def save(tx, assessment, failed=False, failure_code="provider_failed"):
        job = read(db, "jobs", job_id, tx)
        if job["status"] != "running" or job["lease_token"] != lease or job["lease_until"] <= now() or job["deadline"] <= now():
            return False
        if failed:
            finish_failure(db, tx, job, failure_code, "Job could not be completed", can_retry(job, now()))
            return False
        write(db, tx, "jobs", job_id, {"checkpoint": assessment, "stage": "persisting"}, merge=True)
        return True

    try:
        job = read(db, "jobs", job_id)
        kind = job.get("kind", "submission")
        if kind == "mission_search":
            from ..missions.worker import process
            process(db, job, lease)
        elif kind == "souvenir":
            from .souvenir import process
            process(db, job, lease)
        else:
            from .providers import assess
            from .lease import reserve
            if submission.get("mission_id"):
                from ..jobs import active_mission
                from ..missions.location import check_location
                from datetime import datetime
                mission = active_mission(db, None, submission["owner_id"], submission["mission_id"], submission["mission_version"])
                require(submission.get("location_config_version") == CONFIG["version"] and submission.get("location_check"), 409, "Missing location snapshot")
                check_location(submission["capture_location"], mission, datetime.fromisoformat(submission["location_check"]["checked_at"].replace("Z", "+00:00")))
            if checkpoint is None:
                reserve(db, job_id, lease, "gemini_calls")
                assessment = assess(db, submission)
            else:
                assessment = checkpoint
            SCHEMAS[submission["mode"]].validate(assessment)
            if checkpoint is not None or transaction(db, save, assessment):
                award_result(job_id, lease, assessment)
    except (GoogleAPICallError, RetryError):
        raise
    except Exception as exc:
        # Provider/validation/import failures are redacted; counters remain consumed.
        logger.warning("Job processing failed for job %s", job_id)
        code = "deadline_exceeded" if isinstance(exc, TimeoutError) or getattr(exc, "code", None) == "deadline_exceeded" else "provider_failed"
        transaction(db, save, None, True, code)


@router.post("/jobs/{job_id}", status_code=204, dependencies=[Depends(task_identity)])
def deliver(job_id: UUID, body: Delivery):
    try:
        process_delivery(get_db(), str(job_id), body.generation)
    except (GoogleAPICallError, RetryError) as exc:
        raise SocialError(503, "Worker storage unavailable") from exc
    return Response(status_code=204)


def dispatch_one(db, client, parent, job_id):
    token = str(uuid4())

    @transactional
    def reserve(tx):
        time = now()
        outbox = read(db, "job_outbox", job_id, tx)
        if not outbox or outbox["status"] != "pending" or outbox["dispatch_after"] > time:
            return None
        write(db, tx, "job_outbox", job_id, {"dispatch_token": token,
                                            "dispatch_after": time + timedelta(seconds=60)}, merge=True)
        return outbox["generation"]

    generation = transaction(db, reserve)
    if generation is None:
        return False
    audience = os.environ["INTERNAL_AUDIENCE"]
    task = tasks_v2.Task(name=f"{parent}/tasks/{job_id}-{generation}", http_request={
        "http_method": tasks_v2.HttpMethod.POST,
        "url": f"{audience.rstrip('/')}/internal/jobs/{job_id}",
        "headers": {"Content-Type": "application/json"},
        "body": ('{"generation": %d}' % generation).encode(),
        "oidc_token": {"service_account_email": os.environ["TASK_SERVICE_ACCOUNT"], "audience": audience},
    }, dispatch_deadline={"seconds": 180})
    try:
        client.create_task(parent=parent, task=task)
    except AlreadyExists:
        pass

    @transactional
    def delivered(tx):
        outbox = read(db, "job_outbox", job_id, tx)
        if outbox.get("dispatch_token") == token and outbox["generation"] == generation:
            write(db, tx, "job_outbox", job_id, {"status": "delivered", "delivered_at": now()}, merge=True)

    transaction(db, delivered)
    return True


@router.post("/dispatch", dependencies=[Depends(scheduler_identity)])
def dispatch(body: EmptyBody):
    db = get_db()
    client = tasks_v2.CloudTasksClient()
    parent = os.environ["TASK_QUEUE_PATH"]
    processed = 0
    for snapshot in (db.collection("job_outbox").where("status", "==", "pending")
                     .where("dispatch_after", "<=", now()).limit(100).stream()):
        try:
            processed += dispatch_one(db, client, parent, snapshot.id)
        except Exception:
            logger.exception("Dispatch failed for job %s", snapshot.id)
    return {"processed": processed}


def recover(db, job_id):
    @transactional
    def run(tx):
        time = now()
        job = read(db, "jobs", job_id, tx)
        if not job or job["status"] not in {"queued", "running"}:
            return False
        if job["deadline"] <= time:
            finish_failure(db, tx, job, "deadline_exceeded", "Job deadline exceeded")
            return True
        if job["status"] != "running" or job["lease_until"] > time:
            return False
        if not can_retry(job, time):
            finish_failure(db, tx, job, "provider_failed", "Job attempts or budget exhausted")
            return True
        outbox = read(db, "job_outbox", job_id, tx)
        queue(db, tx, job_id, outbox["generation"] + 1, time)
        write(db, tx, "jobs", job_id, {"status": "queued", "stage": "queued", "lease_token": None,
                                      "lease_until": None}, merge=True)
        if job.get("kind", "submission") == "submission":
            write(db, tx, "submissions", job["submission_id"], {"status": "queued"}, merge=True)
        return True

    return transaction(db, run)


def clean_assets(db):
    from ..assets_routes import _local_path, _storage_type

    @transactional
    def mark(tx, asset_id, expected, field, cutoff):
        asset = read(db, "assets", asset_id, tx)
        if not asset or asset["state"] != expected or asset.get(field, cutoff) > cutoff:
            return None
        write(db, tx, "assets", asset_id, {"state": "deleting", "deleting_at": now()}, merge=True)
        return asset["object_path"]

    processed = 0
    local_path = _local_path if _storage_type() == "local" else None
    time = now()
    targets = (
        ("ready", "created_at", time - timedelta(hours=CONFIG["orphan_asset_retention_hours"])),
        ("in_submission", "used_at", time - timedelta(days=CONFIG["failed_evidence_retention_days"])),
        ("deleting", "deleting_at", time),
    )
    for state, field, cutoff in targets:
        for snap in db.collection("assets").where("state", "==", state).where(field, "<=", cutoff).limit(100).stream():
            try:
                path = mark(db.transaction(), snap.id, state, field, cutoff)
                if path:
                    remove_object(path, local_path)
                    snap.reference.update({"state": "deleted"})
                    processed += 1
            except Exception:
                logger.exception("Asset cleanup failed for %s", snap.id)
    for snap in db.collection("asset_uploads").where("cleanup_after", "<=", time).limit(100).stream():
        try:
            remove_object(snap.to_dict()["object_path"], local_path)
            snap.reference.delete()
            processed += 1
        except Exception:
            logger.exception("Abandoned upload cleanup failed for %s", snap.id)
    return processed


@router.post("/maintenance", dependencies=[Depends(scheduler_identity)])
def maintenance(body: EmptyBody):
    db = get_db()
    processed = 0
    queries = (
        db.collection("jobs").where("status", "in", ["queued", "running"]).where("deadline", "<=", now()),
        db.collection("jobs").where("status", "==", "running").where("lease_until", "<=", now()),
    )
    for query in queries:
        for snap in query.limit(100).stream():
            processed += recover(db, snap.id)
    return {"processed": processed + clean_assets(db)}
