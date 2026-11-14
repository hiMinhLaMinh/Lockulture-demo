"""Compose live API entry point; fails before starting HTTP when config is incomplete."""
import json
import os
import sys
from .config import live_errors

if __name__ == "__main__":
    errors = live_errors()
    if errors:
        print(json.dumps({"status": "BLOCKED", "reasons": errors}), flush=True)
        raise SystemExit(1)
    os.execv(sys.executable, [sys.executable, "-m", "uvicorn", "src.main:app",
                             "--host", "0.0.0.0", "--port", os.getenv("PORT", "8080")])
