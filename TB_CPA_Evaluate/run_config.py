"""
run_config.py  —  TB_CPA_Evaluate
====================================
SINGLE ENTRY POINT — edit only the USER CONFIGURATION section below.

Run with:
    python TB_CPA_Evaluate/run_config.py

Outputs per cell (under 04_Evaluated_Data/{CELLID}/):
    {CELLID}_processed_data.csv
    {CELLID}_Full_Test_overview_resampled_plot.html
    {YYYYMMDD}_{CELLID}_step_features.csv
    {CELLID}_meta.json

Run log (auto-created):
    06_Logs/debug_logs/evaluate_debug_{hostname}.log
"""

# ============================================================
# USER CONFIGURATION — edit this section only
# ============================================================

# Path to the project root folder (contains 03_Harmonized_Data/, 04_Evaluated_Data/, ...)
BASE_PATH = r"C:\path\to\project"

# ── Cell parameters ───────────────────────────────────────────────────────────
NOMINAL_CAPACITY = 215   # Ah
MAX_CELL_VOLT    = 3.8   # V  — upper cutoff (used for full-charge detection)
MIN_CELL_VOLT    = 2.5   # V  — lower cutoff (used for full-discharge detection)

# ── Skip / rerun control ──────────────────────────────────────────────────────
# True  → skip cells whose _processed_data.csv + HTML already exist
# False → re-evaluate every cell
SKIP_RERUN = True

# Cell IDs listed here will be force-re-evaluated even when SKIP_RERUN = True.
# Leave empty [] to apply SKIP_RERUN to all cells.
SKIP_RERUN_EXCEPT_IDs = []

# ── Cell filter ───────────────────────────────────────────────────────────────
# List specific cell IDs to process. Leave empty [] to process ALL cells.
# Example: ["EYG1T4600583", "EYFC34605954"]
RUN_CELL_IDs = []

# ── Source change detection ───────────────────────────────────────────────────
# Minimum file size increase (KB) in a harmonized source CSV to trigger a
# re-evaluation when SKIP_RERUN = True. Avoids false reruns from metadata-only
# filesystem writes. Raise this if your files grow in very small increments.
SOURCE_SIZE_CHANGE_THRESHOLD_KB = 1

# ── Overview plot settings ────────────────────────────────────────────────────
# Dynamic resampling keeps a row whenever Voltage or Current changes by more
# than these thresholds, and always keeps at least one row per interval.
# Tighten thresholds (smaller values) for denser plots; loosen for faster rendering.
PLOT_VOLTAGE_THRESHOLD_V = 0.002   # V  — keep row on voltage change > this
PLOT_CURRENT_THRESHOLD_A = 1       # A  — keep row on current change > this
PLOT_MIN_INTERVAL_S      = 60      # s  — force-keep at least 1 row per this interval

# ============================================================
# DO NOT EDIT BELOW THIS LINE
# ============================================================
import sys
import os

# Ensure TB_CPA_Evaluate/ is on sys.path so src.* imports resolve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_evaluate import run_evaluate

result = run_evaluate(
    base_path=BASE_PATH,
    nominal_capacity=NOMINAL_CAPACITY,
    max_cell_volt=MAX_CELL_VOLT,
    min_cell_volt=MIN_CELL_VOLT,
    skip_rerun=SKIP_RERUN,
    skip_rerun_except_ids=SKIP_RERUN_EXCEPT_IDs,
    run_cell_ids=RUN_CELL_IDs,
    source_size_change_threshold_kb=SOURCE_SIZE_CHANGE_THRESHOLD_KB,
    plot_voltage_threshold_v=PLOT_VOLTAGE_THRESHOLD_V,
    plot_current_threshold_a=PLOT_CURRENT_THRESHOLD_A,
    plot_min_interval_s=PLOT_MIN_INTERVAL_S,
)

print(
    f"\n[Done]  processed={result['processed']}  "
    f"skipped={result['skipped']}  "
    f"failed={result['failed']}\n"
)
