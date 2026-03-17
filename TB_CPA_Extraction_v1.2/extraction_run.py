"""
extraction_run.py  —  TB_CPA_Extraction v1.2
Parameterized pipeline entry point.

Called from:
    run_config.py          (single project)
    run_all_config.py      (multi-project loop)
    src/_gui_runner.py     (GUI subprocess shim)
"""

import gc
import json
import logging
import socket
import time
import warnings
from pathlib import Path

from src.paths import PATHS_OBJ
from src.dependencies import *
from src.extract_archive import detect_archive, main_extract_archives
from src.clear_backlog import clear_backlog_after_copy, log_summary, finished_tone
from src.file_handling import copy_files_matching_id, count_files_in_folder, move_archive, append_status_to_excel


def run_extraction(
    base_path: str,
    zip_files: list[str] | None = None,
    copy_action: str = "skip_copy",
    generate_dashboard: bool = True,
) -> dict:
    """
    Run the full extraction pipeline for one project folder.

    Parameters
    ----------
    base_path : str
        Root data folder (must contain 01_Incoming_Compressed_Files/, 08_Backlog/, etc.)
    zip_files : list[str] | None
        Substrings to filter which ZIP archives to process.  None = process all.
    copy_action : str
        How to handle duplicate files: 'skip_copy' | 'replace' | 'create_copy'
    generate_dashboard : bool
        Write extraction_dashboard.html to 06_Logs/ after the run.

    Returns
    -------
    dict  — the final status dict (keyed by archive path)
    """

    # ── Initialise paths ──────────────────────────────────────────────────────
    paths = PATHS_OBJ(base_path)
    timestr = time.strftime("%Y%m%d_%H%M%S")

    # ── Logging ───────────────────────────────────────────────────────────────
    logging.basicConfig(
        filename=paths.debug_path / "debug_logfile.log",
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    logging.info("\n ---- New run (extraction_run.py) ---- ")
    if zip_files:
        logging.warning(f"ZIP_FILES filter active: {zip_files}")

    print(f"[Extraction] Base path  : {paths.base_path}")
    print(f"[Extraction] copy_action: {copy_action}")
    if zip_files:
        print(f"[Extraction] ZIP filter : {zip_files}")

    # ── Pre-flight checks ─────────────────────────────────────────────────────
    if count_files_in_folder(paths.backlog_path) > 0:
        msg = f"Backlog is not empty — clear it before running.\n >> {paths.backlog_path}"
        logging.critical(msg)
        warnings.warn("\033[91m" + msg + "\033[0m", UserWarning)
        return {}

    if not paths.check_if_exists():
        msg = f"Folder structure is incomplete — check base_path.\n >> {paths.base_path}"
        logging.critical(msg)
        warnings.warn("\033[91m" + msg + "\033[0m", UserWarning)
        return {}

    # ── Stage 1: Detect & test archives ───────────────────────────────────────
    print("[Extraction] Stage 1/4 — Detecting archives …")
    archives_dict = detect_archive(paths.dump_path, recursive=True, include_substrings=zip_files)

    # ── Stage 2: Extract + filter by config ───────────────────────────────────
    print("[Extraction] Stage 2/4 — Extracting archives …")
    extract_status_dict = main_extract_archives(
        archives_dict["TestedArchives"],
        out_dir=paths.extract_path,
        backlog_dir=paths.backlog_path,
        config_path=paths.config_file_path,
    )

    # ── Stage 3: Copy files to cell folders ───────────────────────────────────
    print("[Extraction] Stage 3/4 — Copying files to cell folders …")
    main_status_dict = copy_files_matching_id(
        extract_status_dict,
        out_dir=paths.extract_path,
        copy_action=copy_action,
    )
    time.sleep(1)
    gc.collect()

    # ── Stage 4: Clear backlog (verify then delete) ───────────────────────────
    print("[Extraction] Stage 4/4 — Clearing backlog …")
    main_status_dict = clear_backlog_after_copy(main_status_dict, backlog_path=paths.backlog_path)

    # ── Archive move (only if no exceptions) ──────────────────────────────────
    try:
        main_status_dict = move_archive(
            input_status_dict=main_status_dict,
            destination_dir=paths.archived_path,
        )
    except Exception as e:
        logging.critical("Error in move_archive() — contact admin")
        logging.debug(f"move_archive error: {e}")

    # ── Persist status JSON ───────────────────────────────────────────────────
    status_file = paths.backend_path / f"{timestr}_status.json"
    with open(status_file, "w") as jf:
        json.dump(main_status_dict, jf, indent=4, default=str)
    print(f"[Extraction] Status JSON → {status_file.name}")

    # ── Console summary ───────────────────────────────────────────────────────
    log_summary(overall_status_dict=main_status_dict)

    # ── Excel trace log (legacy — one row per archive run) ────────────────────
    try:
        append_status_to_excel(
            status_dict=main_status_dict,
            logs_path=paths.logs_path,
            backend_path=paths.backend_path,
        )
    except Exception as e:
        logging.critical("Error in append_status_to_excel() — contact admin")
        logging.debug(f"append_status_to_excel error: {e}")

    # ── Per-PC trace log (upsert) ─────────────────────────────────────────────
    try:
        from src.trace_log import ExtractionTraceLog
        hostname = socket.gethostname()
        pc_logs_dir = paths.logs_path / "pc_logs"
        pc_logs_dir.mkdir(exist_ok=True)
        trace = ExtractionTraceLog(pc_logs_dir / f"extraction_trace_log_{hostname}.xlsx", hostname)
        trace.record_run(main_status_dict, timestr)
        trace.save()
    except Exception as e:
        logging.warning(f"TraceLog write failed: {e}")

    # ── HTML dashboard ────────────────────────────────────────────────────────
    if generate_dashboard:
        try:
            from src.dashboard import DashboardGenerator
            gen = DashboardGenerator(main_status_dict, paths.logs_path)
            gen.generate(paths.logs_path / "extraction_dashboard.html")
        except Exception as e:
            logging.warning(f"Dashboard generation failed: {e}")
            print(f"[Extraction] Dashboard warning: {e}")

    logging.info("\n---- End of run_extraction() ----\n")
    print("[Extraction] Run complete.")
    finished_tone()

    return main_status_dict
