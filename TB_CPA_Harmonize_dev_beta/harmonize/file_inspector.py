"""
file_inspector.py
-----------------
Detects file format, encoding, sheet, and header row.
Returns a clean DataFrame ready for ColumnMapper.

Supported formats
-----------------
- .xlsx / .xlsm  → openpyxl via pandas
- .xls (binary)  → xlrd via pandas
- .xls (tab-sep) → MCM-style text file with .xls extension
- .csv / .txt    → auto-delimiter via csv.Sniffer
"""

from __future__ import annotations

import csv
import io
import logging
import re
from pathlib import Path

import pandas as pd


_ENCODING_CANDIDATES = ['utf-8', 'utf-8-sig', 'iso-8859-1', 'cp1252', 'latin-1']


class FileInspector:
    """Inspect a battery test data file and return a clean DataFrame."""

    def __init__(self, filepath: Path):
        self.filepath = Path(filepath)
        self._warnings: list[str] = []

    # ── Public API ─────────────────────────────────────────────────────────────

    def load_data(self) -> tuple[pd.DataFrame | None, dict]:
        """
        Full pipeline: detect format → load sheets → pick sheet → detect header → apply.

        Returns
        -------
        (data_df, inspection_report)
        inspection_report keys:
            format, encoding, delimiter, sheet, header_row,
            n_rows, n_cols, warnings
        """
        report: dict = {
            'format': None,
            'encoding': None,
            'delimiter': None,
            'sheet': None,
            'header_row': None,
            'n_rows': None,
            'n_cols': None,
            'warnings': self._warnings,
        }

        try:
            fmt = self.detect_file_format()
            report['format'] = fmt

            sheets = self._load_all_sheets(fmt, report)
            if not sheets:
                self._warn("No sheets could be loaded.")
                return None, report

            sheet_name = self.detect_data_sheet(sheets)
            report['sheet'] = sheet_name
            raw_df = sheets[sheet_name]

            header_row = self.detect_header_row(raw_df)
            report['header_row'] = header_row

            data_df = self._apply_header(raw_df, header_row)
            report['n_rows'] = len(data_df)
            report['n_cols'] = len(data_df.columns)

            return data_df, report

        except Exception as exc:
            self._warn(f"load_data() failed: {exc}")
            logging.exception("FileInspector.load_data() raised an exception")
            return None, report

    # ── Format detection ───────────────────────────────────────────────────────

    def detect_file_format(self) -> str:
        """
        Returns one of: 'xlsx', 'xls_binary', 'xls_tab', 'csv', 'unknown'.

        .xls files that are actually tab-separated text (MCM style) are
        identified by reading the first 512 bytes and checking for printable
        ASCII without the OLE2 magic bytes.
        """
        suffix = self.filepath.suffix.lower()

        if suffix in ('.xlsx', '.xlsm', '.xlsb'):
            return 'xlsx'

        if suffix == '.xls':
            return self._detect_xls_subtype()

        if suffix in ('.csv', '.txt', '.tsv'):
            return 'csv'

        # Unknown extension — try to guess from content
        return self._detect_by_content()

    def _detect_xls_subtype(self) -> str:
        """Distinguish true binary .xls from tab-separated text with .xls extension."""
        try:
            with open(self.filepath, 'rb') as fh:
                header = fh.read(8)
            # OLE2 compound document signature
            if header[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
                return 'xls_binary'
            # Check for UTF-16 BOM (some Windows text files)
            if header[:2] in (b'\xff\xfe', b'\xfe\xff'):
                return 'xls_tab'
            # Try decoding as ASCII text
            with open(self.filepath, 'rb') as fh:
                sample = fh.read(512)
            sample.decode('iso-8859-1')   # will not raise for tab-sep text
            return 'xls_tab'
        except Exception:
            return 'xls_binary'

    def _detect_by_content(self) -> str:
        try:
            with open(self.filepath, 'rb') as fh:
                header = fh.read(8)
            if header[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
                return 'xls_binary'
            if header[:4] == b'PK\x03\x04':
                return 'xlsx'
            return 'csv'
        except Exception:
            return 'unknown'

    # ── Encoding & delimiter ───────────────────────────────────────────────────

    def detect_encoding(self) -> str:
        """Try encodings in order; return first that parses the whole file."""
        for enc in _ENCODING_CANDIDATES:
            try:
                with open(self.filepath, encoding=enc, errors='strict') as fh:
                    fh.read(8192)   # read a sample
                return enc
            except (UnicodeDecodeError, LookupError):
                continue
        self._warn("Could not determine encoding; falling back to iso-8859-1")
        return 'iso-8859-1'

    def detect_csv_delimiter(self, encoding: str) -> str:
        """Use csv.Sniffer on first 2 KB; fallback order: comma → semicolon → tab."""
        try:
            with open(self.filepath, encoding=encoding, errors='replace') as fh:
                sample = fh.read(2048)
            dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
            return dialect.delimiter
        except csv.Error:
            pass

        # Manual fallback: count candidate delimiters in first non-empty line
        lines = []
        try:
            with open(self.filepath, encoding=encoding, errors='replace') as fh:
                for line in fh:
                    stripped = line.strip()
                    if stripped:
                        lines.append(stripped)
                    if len(lines) >= 5:
                        break
        except Exception:
            pass

        for delim in (',', ';', '\t'):
            if lines and all(delim in ln for ln in lines[:3]):
                return delim

        return ','

    # ── Sheet loading ──────────────────────────────────────────────────────────

    def _load_all_sheets(self, fmt: str, report: dict) -> dict[str, pd.DataFrame]:
        if fmt == 'xlsx':
            return self._load_excel(engine='openpyxl')

        if fmt == 'xls_binary':
            return self._load_excel(engine='xlrd')

        if fmt == 'xls_tab':
            return self._load_xls_tab(report)

        if fmt == 'csv':
            return self._load_csv(report)

        self._warn(f"Unknown format '{fmt}'; attempting Excel load.")
        return self._load_excel(engine=None)

    def _load_excel(self, engine: str | None) -> dict[str, pd.DataFrame]:
        kwargs = {'sheet_name': None, 'header': None, 'dtype': str}
        if engine:
            kwargs['engine'] = engine
        try:
            return pd.read_excel(self.filepath, **kwargs)
        except Exception as exc:
            self._warn(f"Excel load failed ({engine}): {exc}")
            return {}

    def _load_xls_tab(self, report: dict) -> dict[str, pd.DataFrame]:
        """Load MCM-style tab-separated .xls text files."""
        encoding = self.detect_encoding()
        report['encoding'] = encoding
        report['delimiter'] = '\t'
        try:
            df = pd.read_csv(
                self.filepath,
                sep='\t',
                encoding=encoding,
                header=None,
                dtype=str,
                on_bad_lines='warn',
            )
            return {'Sheet1': df}
        except Exception as exc:
            self._warn(f"xls_tab load failed: {exc}")
            return {}

    def _load_csv(self, report: dict) -> dict[str, pd.DataFrame]:
        encoding = self.detect_encoding()
        report['encoding'] = encoding
        delimiter = self.detect_csv_delimiter(encoding)
        report['delimiter'] = delimiter
        try:
            df = pd.read_csv(
                self.filepath,
                sep=delimiter,
                encoding=encoding,
                header=None,
                dtype=str,
                comment='#',       # skip comment lines (e.g. SZ export header)
                on_bad_lines='warn',
            )
            return {'Sheet1': df}
        except Exception as exc:
            self._warn(f"CSV load failed: {exc}")
            return {}

    # ── Sheet selection ────────────────────────────────────────────────────────

    @staticmethod
    def detect_data_sheet(sheets: dict[str, pd.DataFrame]) -> str:
        """Return name of the sheet with the most rows."""
        if not sheets:
            raise ValueError("No sheets provided.")
        return max(sheets, key=lambda s: sheets[s].shape[0])

    # ── Header detection ───────────────────────────────────────────────────────

    @staticmethod
    def detect_header_row(df: pd.DataFrame, max_scan: int = 20) -> int:
        """
        Scan the first `max_scan` rows and return the 1-based row index of the
        most likely header row.

        Scoring heuristic:
            score = n_string_labels * (n_string_labels / n_non_empty)

        The row with the highest score is chosen.  A row where every non-empty
        cell is a string (column label) scores highest.
        """
        best_idx = 0
        best_score = -1.0
        scan_limit = min(max_scan, len(df))

        for i in range(scan_limit):
            row = df.iloc[i]
            n_str = sum(
                1 for v in row
                if isinstance(v, str) and v.strip()
            )
            n_total = sum(1 for v in row if pd.notna(v) and str(v).strip())
            if n_total == 0:
                continue
            score = n_str * (n_str / n_total)
            if score > best_score:
                best_score = score
                best_idx = i

        return best_idx + 1   # 1-based

    # ── Header application ─────────────────────────────────────────────────────

    @staticmethod
    def _apply_header(df: pd.DataFrame, header_row: int) -> pd.DataFrame:
        """
        Set row (header_row - 1) as column names, drop rows above it,
        strip whitespace from all column names, and reset the index.
        """
        row_idx = header_row - 1
        if row_idx >= len(df):
            return df

        new_cols = [
            str(v).strip() if pd.notna(v) else f"_col_{i}"
            for i, v in enumerate(df.iloc[row_idx])
        ]
        data = df.iloc[row_idx + 1:].copy()
        data.columns = new_cols
        data.reset_index(drop=True, inplace=True)
        return data

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _warn(self, msg: str) -> None:
        self._warnings.append(msg)
        logging.warning(f"FileInspector [{self.filepath.name}]: {msg}")
