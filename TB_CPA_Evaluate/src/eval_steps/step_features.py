"""
step_features.py  —  TB_CPA_Evaluate / src/eval_steps
=======================================================
Per-step summary feature extraction from a processed cell DataFrame.
Each row in the output represents one Step_id.

Call extract_step_features() after Step_id is assigned and capacity
counting is complete (i.e. after fix_step_series + fix_capacity_counting,
ideally after SOC calculation too so SOC columns are also present).
"""

import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# ── Column configuration ──────────────────────────────────────────────────────

# Elapsed times (seconds from step start) sampled for all main signals
_ELAPSED_MAIN = [1, 10, 18, 180]

# Additional elapsed times for Voltage_V only
_ELAPSED_VOLTAGE_EXTRA = [1800, 3600]

# start / end / elapsed extracted for each of these
_MAIN_SIGNAL_COLS = ['Voltage_V', 'Current_A', 'Capacity_step_Ah', 'Energy_step_Wh']

# Cell temperature columns: mean, start, end
_CELL_TEMP_COLS = ['T_Cell_degC', 'T_Anode_degC', 'T_Cathode_degC', 'T_cold_degC']

# Chamber temperature column: start, end, mean, unique set
_CHAMBER_TEMP_COL = 'T_Chamber_degC'


# ── Public API ────────────────────────────────────────────────────────────────

def extract_step_features(cell_df: pd.DataFrame, time_col: str = 'Unix_time') -> pd.DataFrame:
    """
    Extract a per-step summary table from a processed cell DataFrame.

    Parameters
    ----------
    cell_df  : DataFrame with Step_id assigned (after fix_step_series +
               fix_capacity_counting). All columns are optional except
               Step_id and time_col — missing ones produce NaN.
    time_col : Column name holding Unix epoch time in seconds.

    Returns
    -------
    pd.DataFrame — one row per Step_id, columns described in module docstring.
    """
    if 'Step_id' not in cell_df.columns:
        raise ValueError("'Step_id' column not found. Run fix_step_series() first.")
    if time_col not in cell_df.columns:
        raise ValueError(f"Time column '{time_col}' not found in DataFrame.")

    available_cols = set(cell_df.columns)
    rows = []

    for step_id, grp in cell_df.groupby('Step_id', sort=True):
        try:
            row = _extract_step_row(grp, step_id, time_col, available_cols)
        except Exception as e:
            logger.warning(f"Step {step_id}: feature extraction failed — {e}")
            row = {'step_id': step_id}
        rows.append(row)

    return pd.DataFrame(rows)


# ── Per-step row builder ──────────────────────────────────────────────────────

def _extract_step_row(grp: pd.DataFrame, step_id, time_col: str, cols: set) -> dict:
    row = {}

    # ── Identity ──────────────────────────────────────────────────────────────
    row['step_id']      = step_id
    row['cycle_number'] = _safe_first(grp, 'Cycle')
    row['n_rows']       = len(grp)
    row['step_name']    = _safe_first(grp, 'Step_name')

    # ── Time ──────────────────────────────────────────────────────────────────
    t = grp[time_col]
    t_valid = t.dropna()
    if not t_valid.empty:
        row['time_start_s']           = t_valid.iloc[0]
        row['time_end_s']             = t_valid.iloc[-1]
        row['time_duration_s']        = t_valid.iloc[-1] - t_valid.iloc[0]
        row['time_median_interval_s'] = t_valid.diff().dropna().median() if len(t_valid) > 1 else np.nan
    else:
        row['time_start_s']           = np.nan
        row['time_end_s']             = np.nan
        row['time_duration_s']        = np.nan
        row['time_median_interval_s'] = np.nan

    # ── Main signals: start / end / at elapsed times ──────────────────────────
    for col in _MAIN_SIGNAL_COLS:
        elapsed = _ELAPSED_MAIN + (_ELAPSED_VOLTAGE_EXTRA if col == 'Voltage_V' else [])

        if col not in cols:
            row[f'{col}_start'] = np.nan
            row[f'{col}_end']   = np.nan
            for e in elapsed:
                row[f'{col}_at_{e}s'] = np.nan
            continue

        sig = grp[col]
        row[f'{col}_start'] = sig.iloc[0]  if not sig.empty else np.nan
        row[f'{col}_end']   = sig.iloc[-1] if not sig.empty else np.nan
        for e in elapsed:
            row[f'{col}_at_{e}s'] = _val_at_elapsed(t, sig, e)

    # ── Cell temperatures: mean / start / end ─────────────────────────────────
    for col in _CELL_TEMP_COLS:
        if col not in cols:
            row[f'{col}_mean']  = np.nan
            row[f'{col}_start'] = np.nan
            row[f'{col}_end']   = np.nan
            continue
        s = grp[col]
        s_valid = s.dropna()
        row[f'{col}_mean']  = s_valid.mean() if not s_valid.empty else np.nan
        row[f'{col}_start'] = s.iloc[0]  if not s.empty else np.nan
        row[f'{col}_end']   = s.iloc[-1] if not s.empty else np.nan

    # ── Chamber temperature: start / end / mean / unique ─────────────────────
    if _CHAMBER_TEMP_COL not in cols:
        row[f'{_CHAMBER_TEMP_COL}_start']  = np.nan
        row[f'{_CHAMBER_TEMP_COL}_end']    = np.nan
        row[f'{_CHAMBER_TEMP_COL}_mean']   = np.nan
        row[f'{_CHAMBER_TEMP_COL}_unique'] = '[]'
    else:
        ch = grp[_CHAMBER_TEMP_COL]
        ch_valid = ch.dropna()
        row[f'{_CHAMBER_TEMP_COL}_start']  = ch.iloc[0]  if not ch.empty else np.nan
        row[f'{_CHAMBER_TEMP_COL}_end']    = ch.iloc[-1] if not ch.empty else np.nan
        row[f'{_CHAMBER_TEMP_COL}_mean']   = ch_valid.mean() if not ch_valid.empty else np.nan
        row[f'{_CHAMBER_TEMP_COL}_unique'] = str(_unique_chamber_temps(ch_valid))

    return row


# ── Helpers ───────────────────────────────────────────────────────────────────

def _val_at_elapsed(grp_time: pd.Series, grp_val: pd.Series, elapsed_s: float):
    """
    Return the signal value at the row closest to t_start + elapsed_s.
    Returns NaN if the step is shorter than elapsed_s.
    """
    t_valid = grp_time.dropna()
    if t_valid.empty or grp_val.empty:
        return np.nan
    t_target = t_valid.iloc[0] + elapsed_s
    if t_valid.iloc[-1] < t_target:
        return np.nan
    idx = (grp_time - t_target).abs().idxmin()
    return grp_val.loc[idx]


def _safe_first(grp: pd.DataFrame, col: str):
    """Return first value of col if the column exists, else NaN."""
    if col in grp.columns and not grp[col].empty:
        return grp[col].iloc[0]
    return np.nan


def _unique_chamber_temps(series: pd.Series, round_to: int = 5, min_freq: float = 0.05) -> list:
    """
    Return a sorted list of representative chamber temperatures.

    Rounds each value to the nearest multiple of round_to, then keeps only
    those rounded values whose relative frequency is >= min_freq.
    """
    if series.empty:
        return []
    rounded = (series / round_to).round() * round_to
    freq = rounded.value_counts(normalize=True)
    return sorted(freq[freq >= min_freq].index.tolist())
