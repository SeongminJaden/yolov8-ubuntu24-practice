#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
SIM_PYTHON="${ISAAC_PYTHON:-/home/seongmin/isaacsim6_venv/bin/python}"
if [[ ! -f work/mission-inputs/maze/maze.usda ]]; then
  "$SIM_PYTHON" - <<'PY'
from pathlib import Path
import zipfile
archive=Path.home()/'Downloads/maze.zip'
with zipfile.ZipFile(archive) as z:
    for member in ('maze/maze.usda','maze/geo.usd'):
        dest=Path('work/mission-inputs')/member
        dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():dest.write_bytes(z.read(member))
PY
fi
exec "$SIM_PYTHON" scripts/randomize_mission.py --usd "$@"
