"""
run_config.py  —  TB_CPA_Extraction v1.2
Single-project entry point.  Edit the variables below, then run:

    python run_config.py
"""

from extraction_run import run_extraction

# ── USER SETTINGS ─────────────────────────────────────────────────────────────

BASE_PATH = r"C:\Users\WYBT00P\OneDrive - Volkswagen AG\C48 Test data #2 - 02_CPA_DataBase\x_DataHandling\B2-2_sample"
# Root folder — must contain: 01_Incoming_Compressed_Files/, 02_Extracted_Raw_Files/,
#                              05_Configuration/, 06_Logs/, 07_Archived/, 08_Backlog/

ZIP_FILES = None
# None  → process ALL archives in 01_Incoming_Compressed_Files/
# list  → only process archives whose filename contains one of these substrings
# e.g.  ZIP_FILES = ["Peak", "Cycle_01"]

COPY_ACTION = "skip_copy"
# "skip_copy"   — leave the destination file untouched if it already exists (recommended)
# "replace"     — overwrite the destination file
# "create_copy" — save alongside existing file with a _copy suffix

GENERATE_DASHBOARD = True
# True  → write extraction_dashboard.html to 06_Logs/ after the run
# False → skip dashboard generation

# ── RUN ───────────────────────────────────────────────────────────────────────

run_extraction(
    base_path=BASE_PATH,
    zip_files=ZIP_FILES,
    copy_action=COPY_ACTION,
    generate_dashboard=GENERATE_DASHBOARD,
)
