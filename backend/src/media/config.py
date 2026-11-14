"""Explicit live-demo startup checks. Imported by entry points, never at SDK import time."""
import os
from pathlib import Path


def live_errors():
    errors = []
    if any(value for key, value in os.environ.items() if key.endswith("EMULATOR_HOST")):
        errors.append("Cloud mode cannot use Emulator hosts")
    if os.getenv("STORAGE_TYPE", "firebase") != "firebase":
        errors.append("STORAGE_TYPE must be firebase")
    if os.getenv("LOCKULTURE_SOCIAL_FIXTURES") == "1" or os.getenv("ASSESSMENT_PROVIDER") != "gemini":
        errors.append("Live demo requires ASSESSMENT_PROVIDER=gemini and no fixture actors")
    for key in ("FIREBASE_PROJECT_ID", "STORAGE_BUCKET", "GEMINI_API_KEY", "GOOGLE_MAPS_API_KEY",
                "GEMINI_MODEL", "GEMINI_IMAGE_MODEL", "TASK_QUEUE_PATH", "TASK_SERVICE_ACCOUNT",
                "SCHEDULER_SERVICE_ACCOUNT", "INTERNAL_AUDIENCE"):
        value = os.getenv(key, "")
        if not value or value.startswith(("your_", "YOUR_", "SET_")):
            errors.append(f"Missing {key}")
    credential = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if credential and not Path(credential).is_file():
        errors.append("GOOGLE_APPLICATION_CREDENTIALS file does not exist")
    return errors
