"""
run_evaluate.py  —  TB_CPA_Evaluate
======================================
Preprocessing pipeline: load harmonized data → fix steps → fix capacity →
calculate SOC → export processed_data.csv + overview HTML plot.

Mirrors Run_Base_evaluation.py from basic_evaluation_cop, adapted for the
TB_CPA_Evaluate package structure.

Run via:
    python TB_CPA_Evaluate/run_config.py
"""

import logging
import socket
import time
import numpy as np
from pathlib import Path

from src.paths import PATHS_OBJ, long_path
from src.data_io import read_harm_cell_data
from src.cleaning import fix_step_series, fix_capacity_counting, check_time_gap
from src.soc_calculations import calculate_SOC_reset_zero_full_dch
from src.interpolation import dynamic_resampling
from src.plotting import plot_cell_data
from src.eval_steps import extract_step_features
from src.meta import read_meta, write_meta, sources_changed, params_changed, build_gaps_info

logger = logging.getLogger(__name__)


def run_evaluate(
    base_path,
    nominal_capacity: float,
    max_cell_volt: float,
    min_cell_volt: float,
    skip_rerun: bool = True,
    skip_rerun_except_ids: list = None,
    run_cell_ids: list = None,
    log_path=None,   # None → auto-derived: BASE_PATH/06_Logs/debug_logs/
    source_size_change_threshold_kb: float = 1.0,
    plot_voltage_threshold_v: float = 0.002,
    plot_current_threshold_a: float = 1.0,
    plot_min_interval_s: int = 60,
) -> dict:
    """
    Batch preprocessing pipeline.

    Parameters
    ----------
    base_path            : Project root (contains 03_Harmonized_Data/, 04_Evaluated_Data/)
    nominal_capacity     : Nominal cell capacity in Ah
    max_cell_volt        : Upper voltage cutoff (V) — used for full-charge detection
    min_cell_volt        : Lower voltage cutoff (V) — used for full-discharge detection
    skip_rerun           : True → skip cells whose output files already exist
    skip_rerun_except_ids: Cell IDs to force-rerun even when skip_rerun=True
    run_cell_ids         : Restrict to these cell IDs; [] = process all cells
    log_path             : Folder for debug log file; None = console only

    Returns
    -------
    dict with keys: processed, skipped, failed, total
    """
    skip_rerun_except_ids = skip_rerun_except_ids or []
    run_cell_ids = run_cell_ids or []

    paths = PATHS_OBJ(base_path=base_path)
    harmonized_path = long_path(paths.harmonized_path)
    evaluated_path  = long_path(paths.evaluated_path)
    evaluated_path.mkdir(parents=True, exist_ok=True)

    if log_path is None:
        log_path = paths.debug_path

    # ── Logging ───────────────────────────────────────────────────────────────
    _setup_logging(log_path)
    run_ts = time.strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"\n>>>>>>>>>> TB_CPA_Evaluate  —  run started at {run_ts} <<<<<<<<<<\n")
    logger.info(f"Harmonized path  : {harmonized_path}")
    logger.info(f"Evaluated path   : {evaluated_path}")
    logger.info(
        f"skip_rerun={skip_rerun}  |  except={skip_rerun_except_ids}  |  "
        f"nominal_cap={nominal_capacity} Ah  |  V_max={max_cell_volt} V  |  V_min={min_cell_volt} V"
    )

    # ── Discover cell IDs ─────────────────────────────────────────────────────
    if run_cell_ids:
        cell_ids = [c for c in run_cell_ids if (harmonized_path / c).is_dir()]
    else:
        cell_ids = sorted([d.name for d in harmonized_path.iterdir() if d.is_dir()])

    logger.info(f"Found {len(cell_ids)} cell(s) to consider.")
    counts = dict(processed=0, skipped=0, failed=0, total=len(cell_ids))

    params = {
        "nominal_capacity_Ah": nominal_capacity,
        "max_cell_volt_V":     max_cell_volt,
        "min_cell_volt_V":     min_cell_volt,
    }

    # ── Main loop ─────────────────────────────────────────────────────────────
    for CELLID in cell_ids:
        out_path      = long_path(evaluated_path / CELLID)
        processed_csv = out_path / f"{CELLID}_processed_data.csv"
        overview_html = out_path / f"{CELLID}_Full_Test_overview_resampled_plot.html"

        # Skip logic — check meta for source/param changes if available
        if (
            processed_csv.exists()
            and overview_html.exists()
            and skip_rerun
            and CELLID not in skip_rerun_except_ids
        ):
            meta = read_meta(out_path, CELLID)
            if meta is None:
                # Pre-meta run: no meta file yet — fall back to file-existence check
                logger.info(f"  SKIP  {CELLID}  (already evaluated, no meta)")
                counts['skipped'] += 1
                continue
            src_changed, src_reason = sources_changed(
                meta, harmonized_path / CELLID,
                threshold_bytes=int(source_size_change_threshold_kb * 1024),
            )
            par_changed, par_reason = params_changed(meta, params)
            if not src_changed and not par_changed:
                logger.info(f"  SKIP  {CELLID}  (sources and params unchanged)")
                counts['skipped'] += 1
                continue
            logger.info(f"  RERUN {CELLID}  — {src_reason or par_reason}")

        logger.info(f"\n-------------- Running evaluation for {CELLID} --------------")
        t0 = time.perf_counter()

        try:
            logger.info(f"  >> loading harmonized data for {CELLID}")
            cell_df = read_harm_cell_data(harmonized_path, CELLID)

            if cell_df.empty:
                raise ValueError(f"No data loaded for cell {CELLID}")

            gap_flag, gap_indx, gap_time = check_time_gap(cell_df, threshold=3600)
            if gap_flag:
                logger.warning(
                    f"  !! Time gaps detected in {CELLID}: "
                    f"{np.round(gap_time / 60, 1)} min — check overview plot"
                )
            gaps_info = build_gaps_info(cell_df, gap_indx, gap_time) if gap_flag else []

            logger.info(f"  >> fixing step series")
            cell_df['Step_id'] = fix_step_series(cell_df['Step'])

            logger.info(f"  >> fixing capacity counting")
            cell_df = fix_capacity_counting(cell_df)

            logger.info(f"  >> calculating SOC")
            try:
                cell_df, full_charge_steps, c3_dch_steps, c3_cha_steps, all_c3_dch_steps, full_dch_steps = (
                    calculate_SOC_reset_zero_full_dch(
                        cell_df,
                        nominal_cap=nominal_capacity,
                        max_cell_volt=max_cell_volt,
                        min_cell_volt=min_cell_volt,
                    )
                )
                logger.info(
                    f"  >> SOC done  |  C3-dch RPT steps: {len(c3_dch_steps)}  "
                    f"|  full-dch steps: {len(full_dch_steps)}"
                )
            except Exception as e:
                logger.warning(f"  !! SOC calculation failed for {CELLID}: {e}")
                cell_df['SOC_corrected'] = np.nan
                cell_df['Q_std'] = np.nan

            out_path.mkdir(parents=True, exist_ok=True)

            # ── Export processed CSV ──────────────────────────────────────────
            n_rows = cell_df.shape[0]
            logger.info(f"  >> exporting processed_data.csv  ({round(n_rows / 1e6, 1)}M rows)")
            cell_df.to_csv(processed_csv)

            # ── Step feature extraction ───────────────────────────────────────
            today              = time.strftime('%Y%m%d')
            step_features_name = f"{today}_{CELLID}_step_features.csv"
            step_features_csv  = out_path / step_features_name
            n_steps = None
            try:
                logger.info(f"  >> extracting step features")
                step_df = extract_step_features(cell_df, time_col='Unix_time')
                step_df.to_csv(step_features_csv, index=False)
                n_steps = len(step_df)
                logger.info(f"  >> step features saved  ({n_steps} steps → {step_features_name})")
            except Exception as e:
                logger.warning(f"  !! Step feature extraction failed for {CELLID}: {e}")

            # ── Dynamic resampling + overview plot ────────────────────────────
            logger.info(f"  >> dynamic resampling for plot")
            dyn_cell_df = dynamic_resampling(
                cell_df,
                time_col="Unix_total_time",
                change_thresholds={
                    "Voltage_V": {"threshold": plot_voltage_threshold_v, "include_previous": False},
                    "Current_A": {"threshold": plot_current_threshold_a, "include_previous": False},
                    "Step_id":   {"threshold": 1,                        "include_previous": True},
                },
                min_interval_seconds=plot_min_interval_s,
            )
            compression = round(n_rows / max(len(dyn_cell_df), 1))
            logger.info(
                f"  >> overview plot: {n_rows} → {len(dyn_cell_df)} rows  "
                f"(compression {compression}x)"
            )

            fig = plot_cell_data(dyn_cell_df, skip_points=1, title=f'Test Overview : {CELLID}')
            with open(overview_html, 'w') as f:
                f.write(fig.to_html(full_html=False, include_mathjax='cdn', include_plotlyjs='cdn'))

            # ── Write meta ────────────────────────────────────────────────────
            write_meta(
                out_path=out_path,
                cell_id=CELLID,
                harm_cell_path=harmonized_path / CELLID,
                params=params,
                stats={
                    "n_input_rows":     n_rows,
                    "n_steps":          n_steps,
                    "n_resampled_rows": len(dyn_cell_df),
                },
                time_gaps=gaps_info,
                output_files=[
                    processed_csv.name,
                    step_features_name,
                    overview_html.name,
                ],
            )

            elapsed = time.perf_counter() - t0
            logger.info(f"  OK    {CELLID}  [{elapsed:.1f}s]")
            counts['processed'] += 1

        except Exception as exc:
            logger.error(f"  FAIL  {CELLID}  —  {exc}")
            counts['failed'] += 1
            continue

    logger.info(
        f"\n[Done]  processed={counts['processed']}  "
        f"skipped={counts['skipped']}  "
        f"failed={counts['failed']}  "
        f"total={counts['total']}\n"
    )
    logging.shutdown()
    return counts


# ── Helpers ───────────────────────────────────────────────────────────────────

def _setup_logging(log_path):
    handlers = [logging.StreamHandler()]
    if log_path is not None:
        log_path = Path(log_path)
        log_path.mkdir(parents=True, exist_ok=True)
        hostname = socket.gethostname()
        fh = logging.FileHandler(
            log_path / f"evaluate_debug_{hostname}.log", encoding='utf-8'
        )
        fh.setLevel(logging.DEBUG)
        handlers.append(fh)

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s  %(levelname)-8s  %(message)s',
        handlers=handlers,
    )
