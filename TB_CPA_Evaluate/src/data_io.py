import pandas as pd
from pathlib import Path
import os
import numpy as np
import re
from typing import List, Tuple, Dict, Optional, Union


def long_path(anypath: Path, path_length_thresh=0) -> Path:
    # converts paths to \\?\ to support long paths
    normalized = os.fspath(anypath.absolute())
    if len(normalized) > path_length_thresh:
        if not normalized.startswith('\\\\?\\'):
            normalized = '\\\\?\\' + normalized
        return Path(normalized)
    return anypath


def read_harm_cell_data(harm_path, cellid, suffixes=None):
    cell_path = harm_path / cellid
    cell_df = pd.DataFrame([])
    cell_files_paths = []

    if cell_path.exists():
        if suffixes:
            for suffix in suffixes:
                temp = list(cell_path.rglob(fr"*{cellid}*{suffix}*.csv"))
                cell_files_paths.extend(temp)
        else:
            cell_files_paths = list(cell_path.rglob(fr"*{cellid}*.csv"))
        dfs = []
        for file in cell_files_paths:
            temp = pd.read_csv(file)
            temp['file_name'] = file.name
            dfs.append(temp)
        cell_df = pd.concat(dfs, axis=0, ignore_index=True) if dfs else pd.DataFrame()
        cell_df = cell_df.reset_index()
        cell_df = cell_df.sort_values(by=['Unix_time', 'index'], ascending=[True, True])
        cell_df = cell_df.drop(columns=['index'])

        cell_df['Unix_datetime'] = pd.to_datetime(cell_df['Unix_time'], unit='s')
        cell_df['Unix_total_time'] = (cell_df['Unix_datetime'] - cell_df['Unix_datetime'].min()).dt.total_seconds()
        cell_df = cell_df.drop_duplicates(subset=['Unix_time', 'Current_A'], keep='last', inplace=False, ignore_index=True)
        cell_df = cell_df.reset_index(inplace=False).drop(columns=['index'])
    else:
        print("Cell does not exist")
    return cell_df


def export_to_excel(data_dict, output_path):
    """Export dictionary of DataFrames to multi-sheet Excel file.

    Parameters:
    - data_dict: dict of {sheet_name: DataFrame}
    - output_path: Path or str to output .xlsx file
    """
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for sheet_name, df in data_dict.items():
            df.to_excel(writer, sheet_name=sheet_name, index=True)


def extract_2D_table_from_excel(
    excel_path: str,
    sheet_name: Union[str, int],
    heading_substrings: List[str],
    match_mode: str = "any",
    case_insensitive: bool = True,
    value_map: Optional[Dict[str, float]] = None,
    clean_headers_and_index: bool = False,
    skip_rows: Optional[List[int]] = None,
) -> Optional[pd.DataFrame]:

    # ---------- Helpers ----------
    def _norm(s):
        if pd.isna(s): return ""
        s = str(s).strip()
        return s.lower() if case_insensitive else s

    def _matches(cell):
        cv = _norm(cell)
        subs = [_norm(s) for s in heading_substrings]
        return all(ss in cv for ss in subs) if match_mode == "all" else any(ss in cv for ss in subs)

    def _strip_units(x):
        if pd.isna(x): return x
        s = str(x).strip().replace("−", "-")
        s = re.sub(r'(?<=\d),(?=\d{3}(\D|$))', "", s)
        cleaned = re.sub(r"[^0-9.\-]+", "", s)
        return np.nan if cleaned in {"", "-", ".", "-.", ".-"} else cleaned

    def _preclean(dfblock):
        if value_map:
            vm = {str(k).strip(): v for k, v in value_map.items()}
            dfblock = dfblock.map(lambda x: vm.get(str(x).strip(), x) if not pd.isna(x) else x)
        return dfblock.map(_strip_units)

    # ---------- Load sheet ----------
    df = pd.read_excel(excel_path, sheet_name=sheet_name, header=None, engine="openpyxl")

    # ---------- Remove skipped rows ----------
    if skip_rows:
        df = df.drop(index=skip_rows).reset_index(drop=True)

    # ---------- Find heading ----------
    hits = [
        (r, c)
        for r in range(df.shape[0])
        for c in range(df.shape[1])
        if _matches(df.iat[r, c])
    ]
    if not hits:
        print("No heading found that matches the given substrings.")
        return None

    start_row, start_col = hits[0]
    header_row_index = start_row + 1

    # ---------- Detect table vertical bounds ----------
    end_row = header_row_index
    while end_row < df.shape[0] and not df.iloc[end_row].isna().all():
        end_row += 1

    # ---------- Detect horizontal bounds ----------
    end_col = start_col + 1
    while end_col < df.shape[1] and not pd.isna(df.iat[header_row_index, end_col]):
        end_col += 1

    # Extract block
    raw = df.iloc[header_row_index:end_row, start_col:end_col].copy()
    if raw.shape[0] < 1 or raw.shape[1] < 2:
        print("Detected table is too small or malformed.")
        return None

    # ---------- Pre-clean (mapping + strip units) ----------
    pre = _preclean(raw)

    # ---------- Create header ----------
    header_clean = pre.iloc[0]
    header_orig = raw.iloc[0]

    header = (
        [("" if pd.isna(x) else str(x).strip()) for x in header_clean]
        if clean_headers_and_index
        else [("" if pd.isna(x) else str(x).strip()) for x in header_orig]
    )

    # ---------- Build body ----------
    table = pre.iloc[1:].copy()
    table.columns = header

    # ---------- Index ----------
    idx_col = table.columns[0]

    if clean_headers_and_index:
        table[idx_col] = table[idx_col].map(lambda x: "" if pd.isna(x) else str(x).strip())
    else:
        table[idx_col] = raw.iloc[1:, 0].map(lambda x: "" if pd.isna(x) else str(x).strip())

    table = table.set_index(idx_col)

    # ---------- Convert data to float ----------
    table = table.apply(lambda col: pd.to_numeric(col, errors="coerce"))

    # Try numeric index
    try:
        table.index = pd.to_numeric(table.index, errors="coerce")
    except:
        pass

    return table
