"""
_dashboard_runner.py  —  Subprocess shim for dashboard-only regeneration.
Reads a JSON file passed as argv[1] with {"base_path": "..."} and regenerates
harmonize_dashboard.html without running the full pipeline.
DO NOT run this file directly.
"""

import sys
import json
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.paths import PATHS_OBJ
from src.dashboard import DashboardGenerator

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("[ERROR] Usage: _dashboard_runner.py <config_json_path>", flush=True)
        sys.exit(1)

    config_path = Path(sys.argv[1])
    if not config_path.exists():
        print(f"[ERROR] Config file not found: {config_path}", flush=True)
        sys.exit(1)

    kwargs = json.loads(config_path.read_text(encoding="utf-8"))
    base_path = kwargs.get("base_path", "")
    if not base_path:
        print("[ERROR] base_path is empty.", flush=True)
        sys.exit(1)

    try:
        paths = PATHS_OBJ(base_path=base_path)
        gen = DashboardGenerator(
            None,
            logs_path=paths.logs_path,
            extract_path=paths.extract_path,
            harmonized_path=paths.harmonized_path,
        )
        out = paths.logs_path / "harmonize_dashboard.html"
        gen.generate(out)
        print(f"[Dashboard] Updated → {out.name}", flush=True)
        sys.exit(0)
    except Exception as e:
        print(f"[Dashboard] ERROR: {e}", flush=True)
        sys.exit(1)
