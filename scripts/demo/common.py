"""Shared CLI support. Never print raw exceptions, request bodies, tokens or signed URLs."""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


class SmokeError(Exception):
    pass


class SmokeBlocked(SmokeError):
    pass


def load_env(path=None):
    from dotenv import load_dotenv
    env_path = Path(path or ROOT / "backend/.env").expanduser().resolve()
    load_dotenv(env_path, override=False)
    credential = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if credential and not Path(credential).is_absolute():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str((env_path.parent / credential).resolve())


def emit(item, status, **evidence):
    print(json.dumps({"item": item, "status": status, **evidence}, ensure_ascii=False), flush=True)


def cloud_errors():
    errors = []
    for key, value in os.environ.items():
        if key.endswith("EMULATOR_HOST") and value:
            errors.append(f"Unset {key} for cloud smoke")
    if os.getenv("STORAGE_TYPE", "firebase") != "firebase":
        errors.append("STORAGE_TYPE must be firebase for cloud smoke")
    for key in ("FIREBASE_PROJECT_ID", "STORAGE_BUCKET"):
        if not os.getenv(key):
            errors.append(f"Missing {key}")
    if os.getenv("LOCKULTURE_SOCIAL_FIXTURES") == "1" or os.getenv("ASSESSMENT_PROVIDER") == "fixture":
        errors.append("Fixture providers/actors are forbidden in cloud smoke")
    cred = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if cred and not Path(cred).is_file():
        errors.append("GOOGLE_APPLICATION_CREDENTIALS file does not exist")
    return errors


def require_cloud():
    errors = cloud_errors()
    if errors:
        raise SmokeBlocked("; ".join(errors))


def require_live_config():
    errors = cloud_errors()
    for key in ("GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_IMAGE_MODEL", "GOOGLE_MAPS_API_KEY"):
        value = os.getenv(key, "")
        if not value or value.startswith(("your_", "YOUR_", "SET_")):
            errors.append(f"Missing {key}")
    if os.getenv("ASSESSMENT_PROVIDER") != "gemini":
        errors.append("ASSESSMENT_PROVIDER must be gemini")
    if errors:
        raise SmokeBlocked("; ".join(errors))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http(url, *, method="GET", data=None, headers=None, limit=16 * 1024 * 1024, timeout=30):
    request = urllib.request.Request(url, method=method, data=data, headers=headers or {})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
            content = response.read(limit + 1)
            if len(content) > limit:
                raise SmokeError("HTTP response exceeds byte limit")
            return response.status, content
    except urllib.error.HTTPError as exc:
        raise SmokeError(f"HTTP {exc.code}") from None
    except (OSError, TimeoutError):
        raise SmokeError("Network connection failed or timed out") from None


def api(path, *, method="GET", body=None, key=None, token=None, content_type="application/json"):
    from urllib.parse import urlparse
    base = os.getenv("SMOKE_API_BASE_URL", "http://127.0.0.1:8080/api/v1").rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise SmokeError("Invalid SMOKE_API_BASE_URL")
    token = token or os.getenv("SMOKE_ID_TOKEN")
    if not token:
        raise SmokeBlocked("Missing SMOKE_ID_TOKEN (verified Firebase ID token)")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if key:
        headers["Idempotency-Key"] = key
    if body is not None:
        headers["Content-Type"] = content_type
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
    status, content = http(base + path, method=method, data=body, headers=headers)
    try:
        return status, json.loads(content)
    except (ValueError, UnicodeError):
        raise SmokeError("API returned invalid JSON") from None
