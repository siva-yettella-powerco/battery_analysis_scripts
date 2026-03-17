"""
run_all_config.py  —  TB_CPA_Extraction v1.2
Multi-project entry point.  Add one dict per project to PROJECTS, then run:

    python run_all_config.py

A per-PC lock file prevents overlapping runs on the same machine.
"""

import socket
from pathlib import Path

from extraction_run import run_extraction

# ── PROJECT LIST ──────────────────────────────────────────────────────────────

PROJECTS = [
    {
        "name":               "Project_B2-2",
        "base_path":          r"C:\Users\WYBT00P\OneDrive - Volkswagen AG\C48 Test data #2 - 02_CPA_DataBase\x_DataHandling\B2-2_sample",
        "zip_files":          None,          # None = all archives
        "copy_action":        "skip_copy",
        "generate_dashboard": True,
    },
    # ── Add more projects below ────────────────────────────────────────────────
    # {
    #     "name":               "Project_B3-1",
    #     "base_path":          r"C:\...\B3-1_sample",
    #     "zip_files":          None,
    #     "copy_action":        "skip_copy",
    #     "generate_dashboard": True,
    # },
]

# ── LOCK FILE (prevents concurrent runs on same PC) ───────────────────────────

_HOSTNAME  = socket.gethostname()
_LOCK_FILE = Path(__file__).parent / f"run_all_{_HOSTNAME}.lock"

if _LOCK_FILE.exists():
    raise RuntimeError(
        f"Lock file exists — another run may already be active on {_HOSTNAME}.\n"
        f"If no run is active, delete: {_LOCK_FILE}"
    )

_LOCK_FILE.touch()
try:
    for proj in PROJECTS:
        name = proj.get("name", "?")
        print(f"\n{'='*60}")
        print(f"  Project: {name}")
        print(f"{'='*60}")
        kwargs = {k: v for k, v in proj.items() if k != "name"}
        run_extraction(**kwargs)
finally:
    _LOCK_FILE.unlink(missing_ok=True)

print("\n[run_all] All projects finished.")
