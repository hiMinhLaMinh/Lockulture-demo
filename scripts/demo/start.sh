#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
python_bin="${DEMO_PYTHON:-$repo_dir/backend/.venv/bin/python}"
exec "$python_bin" "$repo_dir/scripts/demo/start.py" "$@"
