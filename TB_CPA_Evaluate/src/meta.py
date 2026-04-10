"""
meta.py  —  TB_CPA_Evaluate / src
===================================
Read/write per-cell JSON metadata alongside evaluated outputs.
Stored as {CELLID}_meta.json in the cell's 04_Evaluated_Data folder.

Used by run_evaluate.py to:
  - Record which source files were used (name, size, mtime stored for reference)
  - Enable smart skip-rerun: rerun when source size changes (> 1 KB) or pipeline params changed
  - Store time-gap and processing statistics for reference
"""

import json
import socket
import time as _time
from pathlib import Path
from typing import Dict, List, Optional, Tuple


_META_SUFFIX = "_meta.json"

# Minimum size difference (bytes) to count as a real file change.
# Avoids false positives from metadata-only writes or filesystem rounding.
# Default: 1 KB.  Raise if your harmonized files grow in very small increments.
_SIZE_CHANGE_THRESHOLD_BYTES = 1024


# ── Public API ────────────────────────────────────────────────────────────────

def write_meta(
    out_path: Path,
    cell_id: str,
    harm_cell_path: Path,
    params: dict,
    stats: dict,
    time_gaps: list,
    output_files: list,
) -> Path:
    """
    Write pipeline run metadata to {cell_id}_meta.json inside out_path.

    Parameters
    ----------
    out_path       : Output folder for this cell (04_Evaluated_Data/{CELLID}/)
    cell_id        : Cell identifier string
    harm_cell_path : Harmonized data folder for this cell (03_Harmonized_Data/{CELLID}/)
    params         : Pipeline parameter dict (nominal_capacity, voltage limits)
    stats          : Processing stats (n_input_rows, n_steps, n_resampled_rows)
    time_gaps      : List of gap dicts from build_gaps_info()
    output_files   : List of output filenames written in this run

    Returns
    -------
    Path to the written meta file
    """
    meta = {
        "cell_id":          cell_id,
        "last_run":         _time.strftime("%Y-%m-%dT%H:%M:%S"),
        "run_host":         socket.gethostname(),
        "pipeline_params":  params,
        "source_files":     _scan_source_files(harm_cell_path, cell_id),
        "time_gaps":        time_gaps,
        "output_files":     output_files,
        "processing_stats": stats,
    }
    meta_path = out_path / f"{cell_id}{_META_SUFFIX}"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)
    return meta_path


def read_meta(out_path: Path, cell_id: str) -> Optional[dict]:
    """Load existing meta JSON for cell_id, or return None if absent/unreadable."""
    meta_path = out_path / f"{cell_id}{_META_SUFFIX}"
    if not meta_path.exists():
        return None
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def sources_changed(
    meta: dict,
    harm_cell_path: Path,
    threshold_bytes: int = _SIZE_CHANGE_THRESHOLD_BYTES,
) -> Tuple[bool, str]:
    """
    Compare current source files against what was recorded in meta.

    Checks: new files added, files removed, size change > threshold_bytes.
    mtime is stored in meta for reference but not used for comparison.
    Returns (changed: bool, reason: str).
    """
    cell_id  = meta.get('cell_id')
    current  = {f['name']: f for f in _scan_source_files(harm_cell_path, cell_id)}
    recorded = {f['name']: f for f in meta.get('source_files', [])}

    new_files = set(current) - set(recorded)
    if new_files:
        return True, f"new source file(s): {sorted(new_files)}"

    removed = set(recorded) - set(current)
    if removed:
        return True, f"source file(s) removed: {sorted(removed)}"

    for name, cur in current.items():
        rec = recorded[name]
        delta = abs(cur['size_bytes'] - rec['size_bytes'])
        if delta > threshold_bytes:
            return True, (
                f"size changed: {name}  "
                f"({rec['size_bytes']} → {cur['size_bytes']} bytes, Δ{delta} bytes)"
            )

    return False, ""


def params_changed(meta: dict, params: dict) -> Tuple[bool, str]:
    """
    Check if pipeline parameters differ from what is recorded in meta.
    Returns (changed: bool, reason: str).
    """
    recorded = meta.get('pipeline_params', {})
    diffs = [
        f"{k}: {recorded.get(k)} → {v}"
        for k, v in params.items()
        if recorded.get(k) != v
    ]
    if diffs:
        return True, f"pipeline params changed — {', '.join(diffs)}"
    return False, ""


def build_gaps_info(cell_df, gap_indx, gap_time) -> list:
    """
    Convert raw check_time_gap output into a list of serialisable gap dicts.

    Parameters
    ----------
    cell_df   : Full cell DataFrame (needs Unix_time and Unix_datetime columns)
    gap_indx  : Index values returned by check_time_gap (row index after each gap)
    gap_time  : Duration array returned by check_time_gap (seconds per gap)

    Returns
    -------
    List of dicts, one per detected gap:
        gap_start_datetime  — ISO-8601 datetime of the last data point before the gap
        gap_start_unix      — Unix timestamp (int) of the same point
        gap_resume_datetime — ISO-8601 datetime of the first data point after the gap
        gap_resume_unix     — Unix timestamp (int) of the same point
        gap_duration_s      — gap duration in seconds
        gap_duration_h      — gap duration in hours (2 d.p.)
    """
    gaps = []
    for idx, duration in zip(gap_indx, gap_time):
        try:
            pos = cell_df.index.get_loc(idx)
            if pos == 0:
                continue  # gap at very first row — skip
            row_before = cell_df.iloc[pos - 1]
            row_after  = cell_df.iloc[pos]
            gaps.append({
                "gap_start_datetime":  row_before['Unix_datetime'].strftime("%Y-%m-%dT%H:%M:%S"),
                "gap_start_unix":      int(row_before['Unix_time']),
                "gap_resume_datetime": row_after['Unix_datetime'].strftime("%Y-%m-%dT%H:%M:%S"),
                "gap_resume_unix":     int(row_after['Unix_time']),
                "gap_duration_s":      round(float(duration), 1),
                "gap_duration_h":      round(float(duration) / 3600, 2),
            })
        except Exception:
            pass  # malformed index — skip silently
    return gaps


# ── Internal ──────────────────────────────────────────────────────────────────

def _scan_source_files(harm_cell_path: Path, cell_id: str = None) -> List[dict]:
    """
    Return name/size/mtime metadata for all source CSVs under harm_cell_path.
    Mirrors the rglob pattern used by read_harm_cell_data.
    """
    pattern = f"*{cell_id}*.csv" if cell_id else "*.csv"
    files = []
    for f in sorted(harm_cell_path.rglob(pattern)):
        stat = f.stat()
        files.append({
            "name":          f.name,
            "last_modified": _time.strftime(
                "%Y-%m-%dT%H:%M:%S", _time.localtime(stat.st_mtime)
            ),
            "size_bytes":    stat.st_size,
        })
    return files
