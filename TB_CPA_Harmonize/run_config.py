"""
run_config.py  —  TB_CPA_Harmonize v1.2
========================================
SINGLE ENTRY POINT — edit only the USER CONFIGURATION section below.

Run with:
    python battery_analysis_scripts/TB_CPA_Harmonize_v1.2/run_config.py
"""

# ============================================================
# USER CONFIGURATION — edit this section only
# ============================================================

# Path to the root data folder (the folder that contains 02_Extracted_Raw_Files,
# 03_Harmonized_Data, 05_Configuration, 06_Logs, etc.)
BASE_PATH = r"C:\Users\WYBT00P\OneDrive - Volkswagen AG\C48 Test data #2 - 02_CPA_DataBase\x_DataHandling\B2-2_sample"

# ── Skip / rerun control ──────────────────────────────────────────────────────
# True  → skip files whose CSV already exists in 03_Harmonized_Data
# False → process every file regardless
SKIP_RERUN = True

# Cell IDs listed here will be force-processed even when SKIP_RERUN = True.
# Leave empty [] to apply SKIP_RERUN to all cells.
# Example: ["LFP44X_001", "LFP44X_002"]
SKIP_RERUN_EXCEPT_IDs = []

# ── File copy action (for files that already exist in harmonized folder) ──────
# 'skip_copy'   → do not overwrite; keep existing file  (default)
# 'replace'     → overwrite existing file
# 'create_copy' → save as filename_copy1.csv, filename_copy2.csv, …
COPY_ACTION = 'skip_copy'

# ── Cell filter ───────────────────────────────────────────────────────────────
# List specific cell folder names to process. Leave empty [] to process ALL cells.
# Example: ["LFP44X_001", "096_DQ_P_002"]
RUN_CELL_IDs = []

# ── Dashboard ─────────────────────────────────────────────────────────────────
# True → generate harmonize_dashboard.html in 06_Logs after the run
GENERATE_DASHBOARD = True

# ============================================================
# DO NOT EDIT BELOW THIS LINE
# ============================================================
import sys
import os

# Ensure the package root (TB_CPA_Harmonize_v1.2/) is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harmonize_run import run_harmonize

run_harmonize(
    base_path=BASE_PATH,
    skip_rerun=SKIP_RERUN,
    skip_rerun_except_ids=SKIP_RERUN_EXCEPT_IDs,
    copy_action=COPY_ACTION,
    run_cell_ids=RUN_CELL_IDs,
    generate_dashboard=GENERATE_DASHBOARD,
)
