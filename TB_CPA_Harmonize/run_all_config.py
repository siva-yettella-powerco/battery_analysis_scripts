"""
run_all_config.py  —  TB_CPA_Harmonize v1.2
=============================================
MULTI-PROJECT entry point. Add one dict per project to PROJECTS below.
Run with:
    python battery_analysis_scripts/TB_CPA_Harmonize_v1.2/run_all_config.py

For automated daily scheduling, point Windows Task Scheduler at run_all.bat.

Lock file: prevents a second instance from starting if the previous run is still
in progress. Lock is stored as  run_all_{HOSTNAME}.lock  next to this script.
"""

# ============================================================
# USER CONFIGURATION — edit this section only
# ============================================================

PROJECTS = [
    {
        # ── Friendly name (shown in console output) ──────────────────────────
        "name":    "Project_B2-2",

        # ── Root data folder containing 02_Extracted_Raw_Files, 06_Logs, etc.
        "base_path": r"C:\Users\WYBT00P\OneDrive - Volkswagen AG\C48 Test data #2 - 02_CPA_DataBase\x_DataHandling\B2-2_sample",

        # ── Run parameters (same as run_config.py) ───────────────────────────
        "skip_rerun":            True,
        "skip_rerun_except_ids": [],    # e.g. ["LFP44X_001"]
        "copy_action":           'skip_copy',   # 'replace' | 'create_copy' | 'skip_copy'
        "run_cell_ids":          [],    # [] = all cells
        "generate_dashboard":    True,
    },
    # ── Add more projects below (duplicate the block above) ─────────────────
    # {
    #     "name":    "Project_B2-3",
    #     "base_path": r"C:\...\B2-3_sample",
    #     "skip_rerun":            True,
    #     "skip_rerun_except_ids": [],
    #     "copy_action":           'skip_copy',
    #     "run_cell_ids":          [],
    #     "generate_dashboard":    True,
    # },
]

# ============================================================
# DO NOT EDIT BELOW THIS LINE
# ============================================================
import sys
import os
import socket
from pathlib import Path
from datetime import datetime

# Ensure the package root (TB_CPA_Harmonize_v1.2/) is on sys.path
_SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(_SCRIPT_DIR))

from harmonize_run import run_harmonize

# ── Lock file: one per PC, prevents overlapping runs ─────────────────────────
_HOSTNAME = socket.gethostname()
_LOCK_FILE = _SCRIPT_DIR / f"run_all_{_HOSTNAME}.lock"


def _acquire_lock() -> bool:
    """Return True if lock acquired, False if another instance is running."""
    if _LOCK_FILE.exists():
        try:
            started = _LOCK_FILE.read_text().strip()
            print(f"\n[LOCK] Another instance is already running on {_HOSTNAME} (started: {started}).")
            print(f"[LOCK] If this is wrong, delete: {_LOCK_FILE}\n")
        except Exception:
            pass
        return False
    _LOCK_FILE.write_text(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    return True


def _release_lock():
    try:
        _LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def main():
    if not _acquire_lock():
        sys.exit(1)

    try:
        total = len(PROJECTS)
        for i, proj in enumerate(PROJECTS, start=1):
            name      = proj.get("name", f"Project_{i}")
            base_path = proj.get("base_path", "")

            print(f"\n{'='*62}")
            print(f"  [{i}/{total}] Running project: {name}")
            print(f"  Base path: {base_path}")
            print(f"{'='*62}")

            if not base_path:
                print(f"  [SKIP] No base_path defined for project '{name}'.")
                continue

            run_harmonize(
                base_path             = base_path,
                skip_rerun            = proj.get("skip_rerun", True),
                skip_rerun_except_ids = proj.get("skip_rerun_except_ids", []),
                copy_action           = proj.get("copy_action", "skip_copy"),
                run_cell_ids          = proj.get("run_cell_ids", []),
                generate_dashboard    = proj.get("generate_dashboard", True),
            )

        print(f"\n{'='*62}")
        print(f"  All {total} project(s) complete.")
        print(f"{'='*62}\n")

    finally:
        _release_lock()


if __name__ == "__main__":
    main()
