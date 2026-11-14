#!/usr/bin/env python3
"""Read-only cloud checks and explicit billable provider smoke, each invoked at most once."""
import argparse
import json
import math
import os
import time
from pathlib import Path

from common import ROOT, SmokeError, cloud_errors, emit, http, load_env


def run(live=False):
    from backend.src.media.souvenir import gemini_request, generate_souvenir, image_part
    failed = False
    errors = cloud_errors()
    emit("cloud_config", "BLOCKED" if errors else "PASS", reasons=errors)
    failed |= bool(errors)
    if not errors:
        try:
            from backend.src.firebase import get_db, get_storage_bucket
            snap = get_db().collection("eras").document("ERA_ANCIENT").get(timeout=15)
            bucket = get_storage_bucket()
            bucket.reload(timeout=15, retry=None)
            policy = bucket.get_iam_policy(requested_policy_version=3, timeout=15, retry=None)
            public = any(any(member in {"allUsers", "allAuthenticatedUsers"} for member in binding["members"])
                         for binding in policy.bindings)
            if public:
                raise SmokeError("Bucket IAM is public; private storage required")
            emit("cloud_read_iam", "PASS", project=os.getenv("FIREBASE_PROJECT_ID"),
                 bucket=bucket.name, canonical_era_exists=snap.exists,
                 note="Bucket-level policy only; inherited IAM and write/read require F1")
        except Exception as exc:
            emit("cloud_read_iam", "FAIL", error=type(exc).__name__)
            failed = True
    for item in ("text", "vision", "image", "maps"):
        required = ["GOOGLE_MAPS_API_KEY", "SMOKE_LATITUDE", "SMOKE_LONGITUDE"] if item == "maps" else ["GEMINI_API_KEY", "GEMINI_IMAGE_MODEL" if item == "image" else "GEMINI_MODEL"]
        if item in {"vision", "image"}:
            required += ["SMOKE_IMAGE_PATH", "SMOKE_IMAGE_CONSENT"]
        if item == "image":
            required += ["SMOKE_PLACE_CONTEXT_FILE"]
        missing = [key for key in required if not os.getenv(key) or os.getenv(key, "").startswith(("your_", "YOUR_", "SET_"))]
        if missing or not live:
            emit(item, "BLOCKED" if missing else "NOT_RUN", missing=missing,
                 note="--live required for real provider calls; no model names are guessed")
            failed |= bool(missing)
            continue
        start = time.monotonic()
        try:
            if item == "maps":
                lat, lng = float(os.environ["SMOKE_LATITUDE"]), float(os.environ["SMOKE_LONGITUDE"])
                if not math.isfinite(lat) or not math.isfinite(lng) or abs(lat) > 90 or abs(lng) > 180:
                    raise SmokeError("Invalid smoke coordinates")
                _, raw = http("https://places.googleapis.com/v1/places:searchNearby", method="POST",
                    headers={"Content-Type": "application/json", "X-Goog-Api-Key": os.environ["GOOGLE_MAPS_API_KEY"],
                             "X-Goog-FieldMask": "places.id,places.location"},
                    data=json.dumps({"maxResultCount": 1, "locationRestriction": {"circle": {
                        "center": {"latitude": lat, "longitude": lng}, "radius": 1000.0}}}).encode())
                places = json.loads(raw).get("places", [])
                if not places or not places[0].get("id"):
                    raise SmokeError("Places returned no candidate")
                emit(item, "PASS", calls=1, candidate_count=len(places), latency_ms=round((time.monotonic()-start)*1000))
            else:
                parts = [{"text": "Reply OK."}]
                image = None
                if item in {"vision", "image"}:
                    if os.environ["SMOKE_IMAGE_CONSENT"] != "1":
                        raise SmokeError("Set SMOKE_IMAGE_CONSENT=1 only for an image you may send to AI")
                    image = Path(os.environ["SMOKE_IMAGE_PATH"]).read_bytes()
                    parts = [{"text": "Briefly describe the visible subject without identifying the person."}, image_part(image)]
                model = os.environ["GEMINI_IMAGE_MODEL" if item == "image" else "GEMINI_MODEL"]
                if item == "image":
                    context = json.loads(Path(os.environ["SMOKE_PLACE_CONTEXT_FILE"]).read_text())
                    portrait_path = os.getenv("SMOKE_PORTRAIT_PATH")
                    output, mime = generate_souvenir(evidence_images=[image], portrait=Path(portrait_path).read_bytes() if portrait_path else None,
                                                     place_context=context, timeout_s=60)
                    # No input/output bytes or preflight image artifacts are persisted as live rewards.
                    emit(item, "PASS", model=model, calls=1, mime_type=mime, byte_size=len(output), latency_ms=round((time.monotonic()-start)*1000))
                else:
                    result = gemini_request(model=model, timeout_s=60, body={"contents": [{"role": "user", "parts": parts}]})
                    texts = [p.get("text") for c in result.get("candidates", []) if c.get("finishReason") in (None,"STOP")
                             for p in c.get("content", {}).get("parts", []) if not p.get("thought")]
                    if result.get("promptFeedback", {}).get("blockReason") or not any(texts):
                        raise SmokeError("Provider returned no usable text")
                    emit(item, "PASS", model=model, calls=1, latency_ms=round((time.monotonic()-start)*1000))
        except Exception as exc:
            emit(item, "FAIL", error=type(exc).__name__, note="Provider/config error; no fallback and no retry")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    load_env(args.env_file)
    raise SystemExit(run(args.live))
