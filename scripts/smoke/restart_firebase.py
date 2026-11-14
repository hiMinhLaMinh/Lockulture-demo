#!/usr/bin/env python3
"""Own two isolated demo API processes to prove storage read-back after restart (Linux).

Never stops an existing service. No worker/provider invocation; A owns worker restart.
"""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/demo"))
from common import SmokeError, emit, http, load_env, require_cloud


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file")
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--phase", choices=["storage", "completion"], default="storage")
    args = parser.parse_args()
    load_env(args.env_file)
    process = None
    try:
        require_cloud()
        if not os.getenv("SMOKE_ID_TOKEN") or os.getenv("SMOKE_TEST_ACCOUNT_CONFIRMED") != "1":
            raise SmokeError("Missing authorized SMOKE_ID_TOKEN / SMOKE_TEST_ACCOUNT_CONFIRMED=1")
        # Bind first: refuse to touch a running service or take ownership of another process.
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", args.port))
        env = dict(os.environ, SMOKE_API_BASE_URL=f"http://127.0.0.1:{args.port}/api/v1")
        for phase in (args.phase, "verify"):
            process = subprocess.Popen([sys.executable, "-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", str(args.port)],
                cwd=ROOT / "backend", env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            env["SMOKE_BACKEND_PID"] = str(process.pid)
            for _ in range(60):
                if process.poll() is not None:
                    raise SmokeError("Managed backend exited; inspect configuration locally")
                try:
                    http(f"http://127.0.0.1:{args.port}/health", timeout=1)
                    break
                except SmokeError:
                    time.sleep(0.25)
            else:
                raise SmokeError("Managed backend did not become healthy")
            result = subprocess.run([sys.executable, str(ROOT / "scripts/smoke/smoke_firebase.py"), "--phase", phase], env=env)
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            process = None
            if result.returncode:
                return result.returncode
        emit("F1_managed_api_restart", "PASS", note="Cloud persistence with local API execution; no worker/app restart evidence")
        return 0
    except SmokeError as exc:
        emit("F1_managed_api_restart", "BLOCKED", reason=str(exc))
        return 1
    except Exception as exc:
        emit("F1_managed_api_restart", "FAIL", error=type(exc).__name__)
        return 1
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(run())
