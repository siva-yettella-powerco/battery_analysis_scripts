"""
harmonize_run.py
----------------
Entry point for TB_CPA_Harmonize_v2.

Run from the repo root:
    python harmonize_run.py

What it does
------------
1. Discovers all files in PATHS.extract_path
2. For each file: runs Harmonizer.run() (no supplier detection required)
3. Exports valid results to PATHS.harmonized_path as CSV
4. Writes a status JSON to PATHS.backend_path

Configuration
-------------
- hm_skip_rerun         : skip files that already have a harmonized CSV
- hm_skip_rerun_except  : list of cell IDs to force reprocess despite skip flag
- override_dir          : YAML overrides folder (optional; pass None to disable)
"""

import json
import logging
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ── Logging setup (do this before any local imports) ──────────────────────────
LOG_FORMAT = '%(asctime)s [%(levelname)s] %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler(sys.stdout)],
)

# ── Local imports ─────────────────────────────────────────────────────────────
from src.paths import PATHS_OBJ
from harmonize.harmonizer import Harmonizer


# ── Run parameters ─────────────────────────────────────────────────────────────
hm_skip_rerun = True
hm_skip_rerun_except = []   # list of strings matched against filepath stem

# Path to YAML overrides directory (or None to disable overrides entirely)
OVERRIDE_DIR = Path(__file__).parent / 'harmonize' / 'overrides'

# ── Initialise ─────────────────────────────────────────────────────────────────
PATHS = PATHS_OBJ()

if not PATHS.check_if_exists():
    logging.critical("One or more required paths are missing. Aborting.")
    sys.exit(1)

# File-based logging
ts = datetime.now().strftime('%Y%m%d_%H%M%S')
log_file = PATHS.debug_path / f'hm_{ts}_v2.log'
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
file_handler.setLevel(logging.DEBUG)
logging.getLogger().addHandler(file_handler)
logging.getLogger().setLevel(logging.DEBUG)

# Harmonizer (instantiated once; override_dir is scanned once)
h = Harmonizer(override_dir=OVERRIDE_DIR if OVERRIDE_DIR.is_dir() else None)


# ── Helper: export DataFrame to CSV ───────────────────────────────────────────

def export_to_harmonized_folder(result, copy_action: str = 'skip_copy') -> Path | None:
    """
    Write result.data to a CSV in PATHS.harmonized_path, mirroring the
    subfolder structure under PATHS.extract_path.
    """
    try:
        rel = result.filepath.relative_to(PATHS.extract_path)
    except ValueError:
        rel = Path(result.filepath.name)

    # Replace the file extension with .csv
    out_rel = rel.with_suffix('.csv')
    out_path = PATHS.harmonized_path / out_rel

    if hm_skip_rerun and out_path.exists():
        # Check if the stem is in the force-reprocess list
        if not any(exc in result.filepath.stem for exc in hm_skip_rerun_except):
            logging.debug(f"Skip (already harmonized): {out_path.name}")
            return out_path   # return existing path

    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists():
        if copy_action == 'skip_copy':
            logging.info(f"Skip (exists, skip_copy mode): {out_path.name}")
            return out_path
        elif copy_action == 'replace':
            pass   # will overwrite below
        # create_copy not meaningful for outputs; treat as replace

    result.data.to_csv(out_path, index=False)
    logging.info(f"Exported: {out_path}")
    return out_path


# ── Main loop ──────────────────────────────────────────────────────────────────

def main():
    hm_status: dict = defaultdict(dict)

    all_files = [
        p for p in PATHS.extract_path.rglob('*')
        if p.is_file() and p.suffix.lower() in {
            '.xlsx', '.xlsm', '.xls', '.csv', '.txt', '.tsv'
        }
    ]

    logging.info(f"Found {len(all_files)} file(s) to process.")

    for file_path in all_files:
        key = str(file_path)
        logging.info(f"Processing: {file_path.name}")
        t0 = time.perf_counter()

        try:
            result = h.run(file_path)
            elapsed = time.perf_counter() - t0

            if result.is_valid and result.data is not None and result.data.shape[0] > 0:
                out_path = export_to_harmonized_folder(result, copy_action=PATHS.copy_action)
                hm_status[key] = {
                    'result': 'ok',
                    'rows': result.data.shape[0],
                    'cols': result.data.shape[1],
                    'elapsed_s': round(elapsed, 2),
                    'sheet': result.inspection.get('sheet'),
                    'header_row': result.inspection.get('header_row'),
                    'format': result.inspection.get('format'),
                    'mapped_cols': list(result.mapping.column_map.keys()) if result.mapping else [],
                    'warnings': result.warnings,
                    'output': str(out_path) if out_path else None,
                }
            else:
                hm_status[key] = {
                    'result': 'failed',
                    'elapsed_s': round(elapsed, 2),
                    'errors': result.errors,
                    'warnings': result.warnings,
                    'unmatched_mandatory': (
                        result.mapping.unmatched_targets if result.mapping else []
                    ),
                }
                logging.warning(f"Failed [{file_path.name}]: {result.errors}")

        except Exception as exc:
            elapsed = time.perf_counter() - t0
            hm_status[key] = {
                'result': 'exception',
                'elapsed_s': round(elapsed, 2),
                'error': str(exc),
            }
            logging.exception(f"Unhandled exception for {file_path.name}")

    # ── Write status JSON ──────────────────────────────────────────────────────
    status_path = PATHS.backend_path / f'hm_{ts}_v2_status.json'
    with open(status_path, 'w', encoding='utf-8') as fh:
        json.dump(hm_status, fh, indent=2, default=str)

    n_ok   = sum(1 for v in hm_status.values() if v.get('result') == 'ok')
    n_fail = len(hm_status) - n_ok
    logging.info(
        f"Done. {n_ok}/{len(hm_status)} files harmonized successfully. "
        f"{n_fail} failed. Status: {status_path}"
    )


if __name__ == '__main__':
    main()
