#!/usr/bin/env python3
"""F1 cloud storage prepare/verify + actual completion verification. Never seeds rewards."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlparse
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/demo"))
from common import SmokeBlocked, SmokeError, api, emit, http, load_env, require_cloud


def state_path():
    value = os.getenv("SMOKE_STATE_FILE")
    if not value:
        raise SmokeBlocked("Missing SMOKE_STATE_FILE (use a private file outside the repository)")
    path = Path(value).expanduser().resolve()
    if path == ROOT or ROOT in path.parents:
        raise SmokeError("SMOKE_STATE_FILE must be outside the repository")
    return path


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(state, stream)
    os.chmod(path, 0o600)


def marker():
    pid = os.getenv("SMOKE_BACKEND_PID")
    if not pid or not pid.isdigit():
        raise SmokeBlocked("Missing SMOKE_BACKEND_PID; use restart_firebase.py to own the demo process")
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
        # Fields after comm begin at field 3; starttime is field 22.
        return {"pid": int(pid), "starttime": raw[raw.rindex(')')+2:].split()[19]}
    except (OSError, ValueError, IndexError):
        raise SmokeError("Cannot verify demo backend process identity") from None


def require_test_account():
    if os.getenv("SMOKE_TEST_ACCOUNT_CONFIRMED") != "1":
        raise SmokeBlocked("Set SMOKE_TEST_ACCOUNT_CONFIRMED=1 only for the authorized acceptance account")
    _, profile = api("/me")
    UUID(profile["id"])
    return profile["id"]


def verify_asset(asset_id, owner, *, check_expiry=False):
    from backend.src.firebase import get_db
    from backend.src.media.storage import load_owned_image
    UUID(asset_id)
    record = get_db().collection("assets").document(asset_id).get().to_dict()
    if not record or record.get("owner_id") != owner:
        raise SmokeError("Asset metadata owner mismatch")
    data = load_owned_image(actor_id=owner, asset_id=asset_id)
    checksum = sha256(data).hexdigest()
    if checksum != record.get("sha256") or len(data) != record.get("byte_size"):
        raise SmokeError("Normalized stored image checksum/size mismatch")
    _, dto = api(f"/assets/{asset_id}/url")
    expires = datetime.fromisoformat(dto["expires_at"].replace("Z", "+00:00"))
    remaining = (expires - datetime.now(timezone.utc)).total_seconds()
    if not 0 < remaining <= 65:
        raise SmokeError("Signed URL TTL is not within 60 seconds")
    parsed = urlparse(dto["url"])
    bucket = os.environ["STORAGE_BUCKET"]
    if parsed.scheme != "https" or parsed.hostname not in {"storage.googleapis.com", f"{bucket}.storage.googleapis.com"}:
        raise SmokeError("Cloud smoke expected a private HTTPS Cloud Storage signed URL")
    _, downloaded = http(dto["url"], limit=8*1024*1024)
    if sha256(downloaded).hexdigest() != checksum:
        raise SmokeError("Signed-download checksum mismatch")
    if check_expiry:
        # Real expiry, not a simulated clock. Never retain signed URLs in the state file.
        while (remaining := (expires - datetime.now(timezone.utc)).total_seconds()) >= -1:
            time.sleep(min(1, remaining + 1.01))
        try:
            http(dto["url"], limit=8*1024*1024)
        except SmokeError as exc:
            if str(exc) != "HTTP 403":
                raise SmokeError("Expired URL did not return HTTP 403") from None
        else:
            raise SmokeError("Expired signed URL still allowed a download")
        _, fresh = api(f"/assets/{asset_id}/url")
        fresh_url = urlparse(fresh["url"])
        if fresh_url.scheme != "https" or fresh_url.hostname not in {"storage.googleapis.com", f"{bucket}.storage.googleapis.com"}:
            raise SmokeError("Refreshed signed URL has an unexpected origin")
        _, fresh_bytes = http(fresh["url"], limit=8*1024*1024)
        if sha256(fresh_bytes).hexdigest() != checksum:
            raise SmokeError("Refreshed signed URL returned a different image")
        emit("signed_url_expiry_refresh", "PASS", asset_id=asset_id)
    # No signed URL, token or raw metadata enters the state/report.
    emit("asset_roundtrip", "PASS", asset_id=asset_id, sha256=checksum, byte_size=len(data))
    return {"asset_id": asset_id, "sha256": checksum}


def outsider_check(path):
    token = os.getenv("SMOKE_OTHER_ID_TOKEN")
    if not token:
        emit("outsider_acl", "BLOCKED", reason="Missing SMOKE_OTHER_ID_TOKEN for a different verified account")
        return False
    _, other = api("/me", token=token)
    _, current = api("/me")
    if other["id"] == current["id"]:
        raise SmokeError("Outsider token belongs to the same account")
    try:
        api(path, token=token)
    except SmokeError as exc:
        if str(exc) == "HTTP 404":
            emit("outsider_acl", "PASS")
            return True
        raise
    raise SmokeError("Outsider accessed an owner-only resource")


def rules_indexes():
    from backend.src.firebase import get_storage_bucket
    import google.auth.transport.requests
    import firebase_admin
    project = os.environ["FIREBASE_PROJECT_ID"]
    for item, url in [
        ("firestore_anon_rules", f"https://firestore.googleapis.com/v1/projects/{project}/databases/(default)/documents/eras/ERA_ANCIENT"),
        ("storage_anon_rules", f"https://firebasestorage.googleapis.com/v0/b/{os.environ['STORAGE_BUCKET']}/o?maxResults=1"),
    ]:
        try:
            http(url)
        except SmokeError as exc:
            if str(exc) not in {"HTTP 401", "HTTP 403"}:
                raise SmokeError(f"{item} did not demonstrate deny rules") from None
            emit(item, "PASS")
        else:
            raise SmokeError(f"{item} allowed unauthenticated access")
    token = os.getenv("SMOKE_ID_TOKEN")
    for item, url in [
        ("firestore_authenticated_rules", f"https://firestore.googleapis.com/v1/projects/{project}/databases/(default)/documents/eras/ERA_ANCIENT"),
        ("storage_authenticated_rules", f"https://firebasestorage.googleapis.com/v0/b/{os.environ['STORAGE_BUCKET']}/o?maxResults=1"),
    ]:
        try:
            http(url, headers={"Authorization": f"Bearer {token}"})
        except SmokeError as exc:
            if str(exc) != "HTTP 403":
                raise SmokeError(f"{item} did not demonstrate deny rules for verified user") from None
            emit(item, "PASS")
        else:
            raise SmokeError(f"{item} allowed direct client access")
    bucket = get_storage_bucket()
    policy = bucket.get_iam_policy(requested_policy_version=3, timeout=15, retry=None)
    if any(any(member in {"allUsers", "allAuthenticatedUsers"} for member in binding["members"]) for binding in policy.bindings):
        raise SmokeError("Bucket has public IAM grants")
    # Check deployed definitions against checked-in indexes, including READY state.
    cred = firebase_admin.get_app().credential.get_credential()
    cred.refresh(google.auth.transport.requests.Request())
    base = f"https://firestore.googleapis.com/v1/projects/{project}/databases/(default)/collectionGroups/-/indexes"
    remote = []
    next_page = None
    from urllib.parse import urlencode
    while True:
        url = base + ("?" + urlencode({"pageToken": next_page}) if next_page else "")
        _, raw = http(url, headers={"Authorization": f"Bearer {cred.token}"})
        page = json.loads(raw)
        remote.extend(page.get("indexes", []))
        next_page = page.get("nextPageToken")
        if not next_page:
            break
    missing = []
    for expected in json.loads((ROOT / "firebase/firestore.indexes.json").read_text())["indexes"]:
        fields = [(f["fieldPath"], f["order"]) for f in expected["fields"]]
        explicit_name = any(field[0] == "__name__" for field in fields)
        found = any(r.get("state") == "READY" and r.get("queryScope") == expected["queryScope"]
            and f"/collectionGroups/{expected['collectionGroup']}/indexes/" in r.get("name", "")
            and [(f["fieldPath"], f.get("order")) for f in r.get("fields", []) if explicit_name or f["fieldPath"] != "__name__"] == fields for r in remote)
        if not found:
            missing.append(expected["collectionGroup"])
    if missing:
        raise SmokeError("Deployed READY composite indexes missing: " + ", ".join(sorted(set(missing))))
    emit("deployed_indexes", "PASS", expected_count=len(json.loads((ROOT / "firebase/firestore.indexes.json").read_text())["indexes"]),
         note="Composite definitions checked; inherited IAM and all possible ACL paths are separate checks")


def storage_phase(path, owner):
    if path.exists():
        raise SmokeError("State file already exists; use verify after restart, or a new private state file")
    image_path = os.getenv("SMOKE_IMAGE_PATH")
    if not image_path or os.getenv("SMOKE_IMAGE_CONSENT") != "1":
        raise SmokeBlocked("Missing authorized SMOKE_IMAGE_PATH / SMOKE_IMAGE_CONSENT=1")
    image = Path(image_path).read_bytes()
    if len(image) > 8*1024*1024:
        raise SmokeError("Input image exceeds the byte limit")
    from backend.src.media.souvenir import inspect_image
    mime, _, _ = inspect_image(image)
    boundary = "LockultureSmoke" + uuid4().hex
    form = (f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="smoke-image"\r\nContent-Type: {mime}\r\n\r\n'.encode()
            + image + f"\r\n--{boundary}--\r\n".encode())
    key = str(uuid4())
    _, asset = api("/assets", method="POST", key=key, body=form, content_type=f"multipart/form-data; boundary={boundary}")
    verified = verify_asset(asset["id"], owner, check_expiry=True)
    _, replay = api("/assets", method="POST", key=key, body=form, content_type=f"multipart/form-data; boundary={boundary}")
    if replay["id"] != asset["id"]:
        raise SmokeError("Upload replay created a duplicate asset")
    state = {"project": os.environ["FIREBASE_PROJECT_ID"], "bucket": os.environ["STORAGE_BUCKET"],
             "owner": owner, "evidence": verified, "backend_before": marker(), "verified_after_restart": False}
    save_state(path, state)
    emit("storage_prepare", "PASS", asset_id=asset["id"], note="Write/read/replay only; restart verification still required")
    rules_indexes()
    return outsider_check(f"/assets/{asset['id']}/url")


def verify_phase(path, owner):
    state = json.loads(path.read_text())
    if state["owner"] != owner or state["project"] != os.environ["FIREBASE_PROJECT_ID"] or state["bucket"] != os.environ["STORAGE_BUCKET"]:
        raise SmokeError("Read-back account/project/bucket differs from prepare")
    before, after = state["backend_before"], marker()
    if before == after:
        raise SmokeError("Backend has not restarted; same PID/starttime")
    old = Path(f"/proc/{before['pid']}/stat")
    if old.exists():
        raw = old.read_text()
        if raw[raw.rindex(')')+2:].split()[19] == before["starttime"]:
            raise SmokeError("Old backend process is still running")
    verified = verify_asset(state["evidence"]["asset_id"], owner)
    if verified != state["evidence"]:
        raise SmokeError("Normalized evidence changed after restart")
    if state.get("souvenir"):
        if verify_asset(state["souvenir"]["asset_id"], owner) != state["souvenir"]:
            raise SmokeError("Souvenir changed after restart")
        _, celebration = api(f"/discoveries/{state['discovery_id']}/celebration")
        if celebration["souvenir"]["asset_id"] != state["souvenir"]["asset_id"]:
            raise SmokeError("Completion changed after restart")
    state["verified_after_restart"] = True
    state["backend_after"] = after
    save_state(path, state)
    emit("restart_readback", "PASS", evidence_asset_id=verified["asset_id"],
         completion_checked=bool(state.get("souvenir")), note="No provider calls; not a backup/restore test")
    return True


def completion_phase(path, owner):
    from backend.src.firebase import get_db
    from backend.src.social.core import digest
    discovery_id = os.getenv("SMOKE_DISCOVERY_ID", "")
    UUID(discovery_id)
    db = get_db()
    def read(collection, document):
        UUID(document) if collection != "reward_ledger" else None
        result = db.collection(collection).document(document).get().to_dict()
        if not result or result.get("owner_id") != owner:
            raise SmokeError(f"Missing or wrong-owner {collection}")
        return result
    discovery = read("discoveries", discovery_id)
    if discovery.get("mode") != "mission":
        raise SmokeError("Completion smoke requires a real completed mission")
    mission = read("missions", discovery["mission_id"])
    submission = read("submissions", discovery["submission_id"])
    completion = read("mission_completions", discovery_id)
    badge = read("earned_badges", completion["badge_id"])
    ledger = read("reward_ledger", digest([owner, f"mission:{discovery['mission_id']}"]))
    job = read("jobs", completion["souvenir_job_id"])
    if (mission.get("status") != "completed" or submission.get("verdict") != "completed"
            or ledger.get("discovery_id") != discovery_id or ledger.get("xp") != 100
            or badge.get("mission_id") != discovery["mission_id"] or job.get("kind") != "souvenir"
            or job.get("status") != "succeeded" or job.get("discovery_id") != discovery_id):
        raise SmokeError("Completion/ledger/badge/souvenir job invariant failed")
    _, celebration = api(f"/discoveries/{discovery_id}/celebration")
    if celebration["badge"]["id"] != completion["badge_id"] or celebration["souvenir"]["status"] != "succeeded":
        raise SmokeError("Celebration does not match persisted reward")
    if not celebration["heritage"].get("sources"):
        raise SmokeError("Historical context has no sources")
    evidence = verify_asset(discovery["asset_id"], owner)
    souvenir_id = celebration["souvenir"]["asset_id"]
    souvenir = verify_asset(souvenir_id, owner)
    souvenir_record = read("assets", souvenir_id)
    if souvenir_record.get("state") != "attached" or souvenir_record.get("purpose") != "souvenir":
        raise SmokeError("Souvenir is not attached; cleanup could remove it")
    if souvenir["sha256"] == evidence["sha256"]:
        raise SmokeError("Souvenir equals input evidence")
    if path.exists():
        raise SmokeError("Use a fresh state file for completion-before-restart evidence")
    save_state(path, {"project": os.environ["FIREBASE_PROJECT_ID"], "bucket": os.environ["STORAGE_BUCKET"],
                     "owner": owner, "discovery_id": discovery_id, "evidence": evidence, "souvenir": souvenir,
                     "backend_before": marker(), "verified_after_restart": False})
    emit("completion_readback", "PASS", discovery_id=discovery_id, mission_id=discovery["mission_id"],
         badge_id=completion["badge_id"], souvenir_job_id=completion["souvenir_job_id"],
         note="Real records only; concurrent/replay reward delivery must be verified by A, provider calls by preflight/job evidence")
    return outsider_check(f"/discoveries/{discovery_id}/celebration")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["storage", "verify", "completion"], required=True)
    parser.add_argument("--env-file")
    args = parser.parse_args()
    load_env(args.env_file)
    try:
        require_cloud()
        owner = require_test_account()
        path = state_path()
        passed = {"storage": storage_phase, "verify": verify_phase, "completion": completion_phase}[args.phase](path, owner)
        emit("F1_" + args.phase, "PASS" if passed else "BLOCKED")
        return 0 if passed else 1
    except SmokeBlocked as exc:
        emit("F1_" + args.phase, "BLOCKED", reason=str(exc))
    except SmokeError as exc:
        emit("F1_" + args.phase, "FAIL", reason=str(exc))
    except Exception as exc:
        emit("F1_" + args.phase, "FAIL", error=type(exc).__name__, note="Inspect server logs locally; no secrets dumped")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
