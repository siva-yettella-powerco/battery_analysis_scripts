"""
harmonize_run.py  —  TB_CPA_Harmonize v1.2
Wraps the original flat harmonize pipeline into run_harmonize() so it can be
called from run_config.py with injected parameters.

All underlying functions in harmonize/ are unchanged.
"""

import logging
import socket
import warnings
from pathlib import Path


from src.dependencies import *
from harmonize.hm_supplier_config import detect_supplier
from harmonize.hm_import_data import *
from harmonize.supplier_support_func.hm_general_support import *
from src.paths import PATHS_OBJ
from src.trace_log import TraceLog
from src.dashboard import DashboardGenerator


def run_harmonize(
    base_path,
    skip_rerun: bool = True,
    skip_rerun_except_ids: list = None,
    copy_action: str = 'skip_copy',
    run_cell_ids: list = None,
    generate_dashboard: bool = True,
):
    """
    Main harmonization pipeline entry point (v1.2).

    Parameters
    ----------
    base_path            : str or Path — root data folder
    skip_rerun           : skip files whose CSV already exists in harmonized folder
    skip_rerun_except_ids: cell IDs to force-rerun even when skip_rerun=True
    copy_action          : 'skip_copy' | 'replace' | 'create_copy'
    run_cell_ids         : list of cell folder names to process; [] = all cells
    generate_dashboard   : write harmonize_dashboard.html to logs folder
    """
    warnings.filterwarnings("ignore")

    if skip_rerun_except_ids is None:
        skip_rerun_except_ids = []
    if run_cell_ids is None:
        run_cell_ids = []

    # ── Initialise paths ──────────────────────────────────────────────────────
    paths = PATHS_OBJ(base_path=base_path)
    extract_path      = paths.extract_path
    harmonized_folder = paths.harmonized_path
    debug_path        = paths.debug_path
    backend_path      = paths.backend_path
    logs_path         = paths.logs_path

    etl_config_path = paths.ETL_config_path
    etl_df = pd.read_excel(etl_config_path, sheet_name='config')

    # ── Logging ───────────────────────────────────────────────────────────────
    logging.basicConfig(
        filename=debug_path / "debug_logfile.log",
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
    )
    run_timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"\n >>>>>>>>>> Running harmonize() <<<<<<<<<<< \n")
    logging.info(
        f"Note: Skip Rerun is {skip_rerun}, Copy action is {copy_action}, "
        f"Rerun active on cells: {skip_rerun_except_ids}"
    )

    # ── TraceLog (per-PC file in pc_logs/ subfolder) ──────────────────────────
    hostname = socket.gethostname()
    pc_logs_path = logs_path / "pc_logs"
    pc_logs_path.mkdir(parents=False, exist_ok=True)
    trace_log = TraceLog(pc_logs_path / f"harmonize_trace_log_{hostname}.xlsx", hostname=hostname)

    hm_status_dict = defaultdict(dict)

    # ── Discover extracted files ───────────────────────────────────────────────
    extracted_files_paths = list(extract_path.rglob('*.*'))

    # Filter to .xlsx only; optionally restrict to specific cell IDs
    if run_cell_ids:
        logging.warning(f'Running on selected cells only: {run_cell_ids}')
        extracted_files_paths = [
            p for p in extracted_files_paths
            if p.suffix.lower() == '.xlsx' and p.parent.stem in run_cell_ids
        ]
    else:
        extracted_files_paths = [
            p for p in extracted_files_paths
            if p.suffix.lower() == '.xlsx'
        ]

    try:
        skip_samples = len([
            p for p in extracted_files_paths
            if (Path(harmonized_folder / p.parent.stem / (p.stem + '.csv')).exists()
                and skip_rerun
                and p.parent.stem not in skip_rerun_except_ids)
        ])
        logging.info(f"Detected {len(extracted_files_paths)} extracted files and {skip_samples} samples skipped")
    except Exception:
        logging.info(f"Detected {len(extracted_files_paths)} extracted files")

    # ── Main harmonization loop ────────────────────────────────────────────────
    for file_path in extracted_files_paths:
        cell_id = file_path.parent.stem
        csv_exists = Path(harmonized_folder / cell_id / (file_path.stem + '.csv')).exists()

        # Skip logic
        if csv_exists and skip_rerun and cell_id not in skip_rerun_except_ids:
            # logging.info(f"Skipped (already harmonized): {file_path.name}")
            trace_log.record(
                run_timestamp, cell_id, file_path,
                status='Skipped',
                skip_reason='already_harmonized',
            )
            continue

        file_id = str(file_path)
        print(f"Processing: {file_path.name}", flush=True)

        # Find matching configuration
        config_match_name, hm_status_dict = find_matching_config(
            file_path=file_path, etl_df=etl_df, hm_status_dict=hm_status_dict
        )
        status_entry = hm_status_dict.get(file_id, {})
        supplier = status_entry.get('supplier_name', '—')

        if config_match_name is not None:
            try:
                harmonized_data, hm_status_dict = run_harmonize_with_config(
                    file_path=file_path, etl_df=etl_df,
                    hm_status_dict=hm_status_dict, config_name=config_match_name
                )

                if harmonized_data.shape[0] > 0:
                    export_file_path = export_to_harmonized_folder(
                        file_path=file_path,
                        harmonized_data=harmonized_data,
                        harmonized_folder=harmonized_folder,
                        copy_action=copy_action,
                    )
                    hm_status_dict[file_id]['Harmonized_file'] = str(export_file_path)
                    logging.info(f"Harmonized data saved to {export_file_path.name}")
                    trace_log.record(
                        run_timestamp, cell_id, file_path,
                        supplier=supplier,
                        config_used=config_match_name,
                        status='Harmonized',
                        harmonized_file_path=export_file_path,
                        row_count=harmonized_data.shape[0],
                    )
                else:
                    logging.warning(f'Empty Table after run harmonize() in {file_path.name}')
                    trace_log.record(
                        run_timestamp, cell_id, file_path,
                        supplier=supplier,
                        config_used=config_match_name,
                        status='Failed',
                        skip_reason='empty_output',
                    )

            except Exception as e:
                logging.error(f'Could not run harmonize() on file {file_path.name} {e}')
                hm_status_dict[file_id]['Harmonized_file'] = None
                trace_log.record(
                    run_timestamp, cell_id, file_path,
                    supplier=supplier,
                    config_used=config_match_name,
                    status='Failed',
                    skip_reason='error',
                    error_message=str(e),
                )
        else:
            logging.warning(f"No matching config for {file_path}")
            trace_log.record(
                run_timestamp, cell_id, file_path,
                supplier=supplier,
                status='No_config',
                skip_reason='no_config_match',
            )

    # ── Persist status JSON (original behaviour) ───────────────────────────────
    timestr = time.strftime("%Y%m%d_%H%M%S")
    with open(backend_path / ("hm_" + timestr + "_status.json"), "w") as jf:
        json.dump(hm_status_dict, jf, indent=4)

    # ── Save trace log & generate dashboard ────────────────────────────────────
    trace_log.save()

    if generate_dashboard:
        bp = Path(base_path)
        project_name = "/".join(bp.parts[-2:]) if len(bp.parts) >= 2 else bp.name
        DashboardGenerator(trace_log, logs_path=logs_path,
                           extract_path=extract_path,
                           harmonized_path=harmonized_folder,
                           project_name=project_name).generate(logs_path / "harmonize_dashboard.html")

    logging.info(f"\n ----------- END OF RUN ----------- \n")
    logging.shutdown()
    print(f"\n[Done] Run complete. PC log: pc_logs/harmonize_trace_log_{hostname}.xlsx | Dashboard: harmonize_dashboard.html\n")
