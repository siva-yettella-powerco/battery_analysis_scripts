"""
_gui_runner.py  —  Subprocess shim for extraction_gui.py
Reads a JSON config file passed as argv[1], calls run_extraction(**kwargs).
stdout/stderr are captured by the parent GUI process.
DO NOT run this file directly.
"""

import sys
import json
from pathlib import Path

# Package root is one level up from src/
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from extraction_run import run_extraction

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("[ERROR] Usage: _gui_runner.py <config_json_path>", flush=True)
        sys.exit(1)

    config_path = Path(sys.argv[1])
    if not config_path.exists():
        print(f"[ERROR] Config file not found: {config_path}", flush=True)
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        kwargs = json.load(f)

    print(f"[GUI Runner] Starting extraction: {kwargs.get('name', '?')}", flush=True)
    print(f"[GUI Runner] Base path : {kwargs.get('base_path', '?')}", flush=True)
    zip_f = kwargs.get("zip_files") or []
    if zip_f:
        print(f"[GUI Runner] ZIP filter: {zip_f}", flush=True)

    # Remove GUI-only keys not accepted by run_extraction
    kwargs.pop("name", None)

    # Normalise zip_files: empty list → None (process all)
    if not kwargs.get("zip_files"):
        kwargs["zip_files"] = None

    try:
        run_extraction(**kwargs)
        print("[GUI Runner] Finished successfully.", flush=True)
        sys.exit(0)
    except Exception as e:
        print(f"[GUI Runner] ERROR: {e}", flush=True)
        sys.exit(1)
