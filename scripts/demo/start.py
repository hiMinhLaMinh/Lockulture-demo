"""Start a live-configured API. Cloud Tasks/Scheduler worker must be provisioned by A/B."""
import argparse
import os
import sys
from common import ROOT, SmokeError, emit, load_env, require_live_config

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--env-file")
parser.add_argument("--port", type=int, default=8080)
args = parser.parse_args()
load_env(args.env_file)
try:
    require_live_config()
    missing = [key for key in ("TASK_QUEUE_PATH", "TASK_SERVICE_ACCOUNT", "SCHEDULER_SERVICE_ACCOUNT", "INTERNAL_AUDIENCE") if not os.getenv(key)]
    if missing:
        raise SmokeError("Cloud worker dispatch config missing: " + ", ".join(missing))
except SmokeError as exc:
    emit("startup", "BLOCKED", reason=str(exc))
    raise SystemExit(1)
emit("startup", "PASS", port=args.port, note="API starts; provision Cloud Tasks/Scheduler separately. No OIDC bypass or fixture worker.")
os.chdir(ROOT / "backend")
os.execv(sys.executable, [sys.executable, "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", str(args.port)])
