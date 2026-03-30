"""
transform_engine.py
--------------------
Format-aware transforms for each column role.

Classes
-------
TimeFormatDetector      – detect time column format
TimeTransformer         – convert any time format to seconds / datetime
CurrentDirectionHandler – detect and normalise current sign convention
StepNameNormalizer      – map raw step names to Rest/Charge/Discharge/Control
CapacityTransformer     – compute step-level capacity from various source layouts
DerivedColumnsCalculator– Power = V*I, Unix_time = Date_time.timestamp()

Design principle
----------------
All classes are stateless (no __init__ required beyond standard Python).
Each public method takes a pd.Series or pd.DataFrame and returns a pd.Series.
Errors are logged and None is returned — never raised to the caller.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

import numpy as np
import pandas as pd


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

_D_HMS_MS_PAT = re.compile(
    r'^(?P<days>\d+)[\.:](?P<hours>\d{2}):(?P<minutes>\d{2}):(?P<seconds>\d{2})'
    r'(?:[\.:](?P<msecs>\d+))?$'
)


def _parse_d_hms_ms(series: pd.Series) -> pd.Series:
    """
    Parse strings of form  '0d 08:47:57.31'  OR  '0.08:47:57.310'
    into pandas Timedelta values.

    Handles:
        '0d 08:47:57.31'     (MCM format with space and 'd' suffix)
        '0.08:47:57.310'     (SRF format with period separator)
        '2.12:05:07'         (no milliseconds)

    Non-matching rows become NaT.
    """
    s = series.astype('string').str.strip()

    # Normalise: '0d 08:47:57.31' → '0.08:47:57.31'
    s = s.str.replace(r'^(\d+)d\s+', r'\1.', regex=True)

    pat = (r'^(?P<days>\d+)\.(?P<hours>\d{2}):(?P<minutes>\d{2}):(?P<seconds>\d{2})'
           r'(?:\.(?P<msecs>\d+))?$')

    parts = s.str.extract(pat)

    if parts.isna().all(axis=None):
        return pd.Series(pd.NaT, index=series.index, dtype='timedelta64[ns]')

    days    = pd.to_numeric(parts['days'],    errors='coerce').fillna(0)
    hours   = pd.to_numeric(parts['hours'],   errors='coerce').fillna(0)
    minutes = pd.to_numeric(parts['minutes'], errors='coerce').fillna(0)
    seconds = pd.to_numeric(parts['seconds'], errors='coerce').fillna(0)
    msecs   = pd.to_numeric(parts['msecs'],   errors='coerce').fillna(0)

    td = (
        pd.to_timedelta(days,    unit='D') +
        pd.to_timedelta(hours,   unit='h') +
        pd.to_timedelta(minutes, unit='m') +
        pd.to_timedelta(seconds, unit='s') +
        pd.to_timedelta(msecs,   unit='ms')
    )

    matched = s.str.match(pat, na=False)
    out = pd.Series(pd.NaT, index=series.index, dtype='timedelta64[ns]')
    out.loc[matched] = td.loc[matched].values
    return out


# ────────────────────────────────────────────────────────────────────────────
# TimeFormatDetector
# ────────────────────────────────────────────────────────────────────────────

class TimeFormatDetector:
    """
    Inspect a series and return one of:
        'float_seconds'      – numeric values already in seconds
        'timedelta_pandas'   – "0 days 00:01:30.000000000" style
        'd_hms_ms'           – "0d 08:47:57.31" or "0.08:47:57.310"
        'datetime'           – ISO datetime strings
        'unknown'            – could not determine
    """

    _D_HMS_PATTERN = re.compile(
        r'^\d+[d\.][\s\.]?\d{2}:\d{2}:\d{2}', re.IGNORECASE
    )

    def detect(self, series: pd.Series) -> str:
        sample = series.dropna().astype(str).head(20)
        if sample.empty:
            return 'unknown'

        # --- float seconds ---
        try:
            numeric = pd.to_numeric(sample, errors='coerce')
            if numeric.notna().mean() >= 0.8:
                return 'float_seconds'
        except Exception:
            pass

        # --- d_hms_ms pattern (check before timedelta: "0 days …" would match timedelta) ---
        if sample.str.match(self._D_HMS_PATTERN, na=False).mean() >= 0.7:
            return 'd_hms_ms'

        # --- pandas timedelta string ---
        try:
            td = pd.to_timedelta(sample, errors='coerce')
            if td.notna().mean() >= 0.8:
                return 'timedelta_pandas'
        except Exception:
            pass

        # --- datetime ---
        # Try format='mixed' first (handles mixed ISO/microsecond values),
        # then fall back to standard parsing.
        try:
            cleaned = sample.str.rstrip('.,-')
            try:
                dt = pd.to_datetime(cleaned, errors='coerce', format='mixed')
            except TypeError:
                dt = pd.to_datetime(cleaned, errors='coerce')
            if dt.notna().mean() >= 0.6:
                return 'datetime'
        except Exception:
            pass

        return 'unknown'


# ────────────────────────────────────────────────────────────────────────────
# TimeTransformer
# ────────────────────────────────────────────────────────────────────────────

class TimeTransformer:
    """Convert any detected time format into total seconds or datetime."""

    def to_total_seconds(self, series: pd.Series, fmt: str) -> Optional[pd.Series]:
        """
        Convert `series` to a float Series of elapsed seconds (starting near 0).
        """
        try:
            if fmt == 'float_seconds':
                s = pd.to_numeric(series, errors='coerce')
                return s - s.iloc[0]   # make relative if not already

            if fmt == 'timedelta_pandas':
                td = pd.to_timedelta(series, errors='coerce')
                secs = td.dt.total_seconds()
                return secs - secs.iloc[0]

            if fmt == 'd_hms_ms':
                td = _parse_d_hms_ms(series)
                secs = pd.to_timedelta(td).dt.total_seconds()
                return secs - secs.iloc[0]

            if fmt == 'datetime':
                dt = pd.to_datetime(series, errors='coerce')
                return (dt - dt.iloc[0]).dt.total_seconds()

            logging.warning(f"TimeTransformer: unknown format '{fmt}', returning None")
            return None

        except Exception as exc:
            logging.warning(f"TimeTransformer.to_total_seconds() failed: {exc}")
            return None

    def to_datetime(self, series: pd.Series, fmt: str) -> Optional[pd.Series]:
        """
        Convert `series` to a datetime Series.
        Only works if fmt == 'datetime'; otherwise returns None.
        """
        try:
            if fmt == 'datetime':
                cleaned = series.astype(str).str.rstrip('.,-')
                try:
                    return pd.to_datetime(cleaned, errors='coerce', format='mixed')
                except TypeError:
                    return pd.to_datetime(cleaned, errors='coerce')
            return None
        except Exception as exc:
            logging.warning(f"TimeTransformer.to_datetime() failed: {exc}")
            return None

    # ── Stubs for user to implement ───────────────────────────────────────────

    def build_total_time_from_step_plus_test(
        self,
        step_series: pd.Series,
        test_series: pd.Series,
        step_fmt: str = 'd_hms_ms',
        test_fmt: str = 'd_hms_ms',
    ) -> pd.Series:
        """
        MCM/SRF combined time logic:
        Use step_time as higher-resolution counter and test_time for step boundaries.

        Steps:
        1. Convert step_series → seconds using step_fmt
        2. Convert test_series → seconds using test_fmt
        3. Cumsum of step_time deltas (clipped to ≥0 on step resets),
           corrected at each step-reset using test_time boundary.

        STUB — raise NotImplementedError until implemented.
        """
        raise NotImplementedError(
            "Implement build_total_time_from_step_plus_test() "
            "for MCM/SRF combined step+test time logic."
        )

    def build_datetime_with_gap_correction(
        self,
        abs_datetime_series: pd.Series,
        rel_seconds_series: pd.Series,
        gap_threshold_s: float = 60.0,
    ) -> Optional[pd.Series]:
        """
        Build a gap-corrected datetime series from an RTC clock column and a
        relative time counter.

        Parameters
        ----------
        abs_datetime_series : pd.Series
            Absolute wall-clock datetime from the test equipment (RTC).
            Includes pauses/gaps between test segments.
            Parseable by pd.to_datetime (ISO strings, mixed microseconds, etc.).

        rel_seconds_series : pd.Series
            Relative time in seconds.  Two valid conventions:
            • Monotonically increasing  — total test time since first row.
            • Resetting at step changes — step time (restarts from ~0 each step).
            Both are handled automatically.

        gap_threshold_s : float
            Minimum difference (abs_delta − rel_delta) in seconds that counts as
            a test pause.  Default 60 s matches the original per-supplier logic.

        Returns
        -------
        pd.Series of Timestamps (datetime64)
            Gap-corrected datetime.  Falls back to raw abs_datetime_series if
            final validation fails.  Returns None only on unrecoverable error.

        Algorithm
        ---------
        1. Parse abs_datetime → DPT_Time (Timestamps).
        2. Convert rel_seconds to a monotonically increasing series:
             • If rel_seconds already monotonic → subtract first value (start at 0).
             • If step-resetting → clip negative diffs, carry the step-start value
               (e.g. reset from 120 s to 0.5 s contributes +0.5 s, not −119.5 s),
               then cumsum.  This matches MCM/SRF step-time reconstruction.
        3. Compute row-level deltas:
             rel_delta  = diff(test_time)
             abs_delta  = diff((DPT_Time − base_time).total_seconds())
        4. Detect gaps (vectorised):
             gap where (abs_delta − rel_delta) > gap_threshold_s
        5. Vectorised gap correction (replaces the original per-supplier for-loop):
             • For each gap row i, the full abs_delta[i] is added to all rows ≥ i.
             • Equivalent to cumsum(gap_additions) added to test_time.
        6. Reconstruct: result = base_time + to_timedelta(corrected_test_time).
        7. Validate last-value alignment (within gap_threshold_s).
             OK  → return result.
             Fail→ log warning, return raw DPT_Time as fallback.
        """
        try:
            # ── 1. Parse absolute datetime ────────────────────────────────────
            try:
                dpt = pd.to_datetime(
                    abs_datetime_series.astype(str).str.rstrip('.,-'),
                    errors='coerce', format='mixed',
                )
            except TypeError:
                dpt = pd.to_datetime(
                    abs_datetime_series.astype(str).str.rstrip('.,-'),
                    errors='coerce',
                )

            if dpt.notna().sum() == 0:
                logging.warning(
                    "build_datetime_with_gap_correction: abs_datetime is all NaT — "
                    "cannot build corrected datetime."
                )
                return None

            base_time = dpt.dropna().iloc[0]

            # ── 2. Relative seconds → monotonically increasing series ─────────
            rel = pd.to_numeric(rel_seconds_series, errors='coerce')

            if rel.notna().sum() == 0:
                logging.warning(
                    "build_datetime_with_gap_correction: rel_seconds is all NaN — "
                    "returning raw abs_datetime."
                )
                return dpt

            rel_delta = rel.diff()
            is_resetting = (rel_delta < 0).any()

            if is_resetting:
                # Step-resetting: negative diff means step changed.
                # On reset, carry the small positive value at the start of the
                # new step (e.g. 0.5 s) rather than clipping to 0.
                corrected_delta = rel_delta.copy()
                reset_mask = rel_delta < 0
                # At reset rows, the new step-start value is the real elapsed time
                # within that new step — use it as the forward delta.
                corrected_delta.loc[reset_mask] = rel.loc[reset_mask].clip(lower=0)
                # Safety clip: discard any remaining negatives (e.g. first row NaN)
                corrected_delta = corrected_delta.clip(lower=0)
                # First row: use its own value (no predecessor)
                first_val = rel.iloc[0]
                corrected_delta.iloc[0] = max(float(first_val), 0.0) if pd.notna(first_val) else 0.0
                test_time = corrected_delta.cumsum()
                logging.debug(
                    "build_datetime_with_gap_correction: rel_seconds resets at steps — "
                    "converted to cumulative."
                )
            else:
                # Already monotonic — normalise to start at 0
                test_time = (rel - rel.iloc[0]).clip(lower=0)

            # ── 3. Row-level deltas ───────────────────────────────────────────
            abs_from_base = (dpt - base_time).dt.total_seconds()
            abs_delta     = abs_from_base.diff()
            rel_time_delta = test_time.diff()

            # ── 4. Detect gaps (vectorised) ───────────────────────────────────
            # Only rows where RTC jumped significantly more than the rel timer.
            diff = (abs_delta - rel_time_delta).fillna(0.0)
            gap_mask = diff > gap_threshold_s
            n_gaps = int(gap_mask.sum())

            if n_gaps > 0:
                logging.info(
                    f"build_datetime_with_gap_correction: {n_gaps} test gap(s) detected "
                    f"(threshold={gap_threshold_s:.0f}s). Largest gap: "
                    f"{diff[gap_mask].max():.1f}s."
                )

            # ── 5. Vectorised gap correction ──────────────────────────────────
            # Add abs_delta[i] to all rows from i onward for each gap row i.
            # Equivalent to the original supplier-specific for-loop but O(n) not O(n·k).
            if n_gaps > 0:
                gap_additions = pd.Series(0.0, index=test_time.index)
                gap_additions.loc[gap_mask] = abs_delta.loc[gap_mask].fillna(0.0)
                cumulative_gap = gap_additions.cumsum()
                test_time_corrected = test_time + cumulative_gap
            else:
                test_time_corrected = test_time

            # ── 6. Reconstruct datetime ───────────────────────────────────────
            result = base_time + pd.to_timedelta(test_time_corrected, unit='s')

            # ── 7. Validate ───────────────────────────────────────────────────
            last_abs    = dpt.dropna().iloc[-1]
            valid_result = result.dropna()
            if valid_result.empty:
                logging.warning(
                    "build_datetime_with_gap_correction: result is all NaT — "
                    "returning raw abs_datetime."
                )
                return dpt

            last_result = valid_result.iloc[-1]
            drift_s = abs((last_abs - last_result).total_seconds())

            if drift_s <= gap_threshold_s:
                logging.debug(
                    f"build_datetime_with_gap_correction: validation OK — "
                    f"final drift={drift_s:.2f}s."
                )
                return result
            else:
                logging.warning(
                    f"build_datetime_with_gap_correction: final drift {drift_s:.1f}s "
                    f"exceeds threshold {gap_threshold_s:.0f}s after {n_gaps} correction(s). "
                    "Falling back to raw abs_datetime."
                )
                return dpt

        except Exception as exc:
            logging.warning(f"build_datetime_with_gap_correction() failed: {exc}")
            return None


# ────────────────────────────────────────────────────────────────────────────
# CurrentDirectionHandler
# ────────────────────────────────────────────────────────────────────────────

class CurrentDirectionHandler:
    """
    Detect whether current is bipolar (±) or unipolar with a state column,
    then normalise to signed convention (discharge = negative).
    """

    DISCHARGE_VALS = frozenset([
        'd', 'dch', 'dis', 'discharge', 'ccdischarge', 'cccdischarge',
        'ccdischarge', 'cccvdischarge', 'cccdischarge', 'entladung',
        'discharging', 'entladen', '放电', 'cccdischarge', 'cccvdischarge',
        'ccdischarge', 'ccdischarge',
    ])
    CHARGE_VALS = frozenset([
        'c', 'ch', 'chg', 'charge', 'cccharge', 'cccvcharge', 'ladung',
        'charging', 'laden', '充电', 'cvccharge',
    ])
    REST_VALS = frozenset([
        'r', 'rest', 'pause', 'ocp', '静置', 'relaxation', 'idle',
    ])

    def detect(
        self,
        df,
        current_col: str,
    ) -> tuple[str, Optional[str]]:
        """
        Determine current direction convention.

        Returns
        -------
        (convention, state_col_name)
        convention: 'bipolar' | 'unipolar_with_state_col' | 'unknown'
        state_col_name: str or None
        """
        try:
            curr = pd.to_numeric(df[current_col], errors='coerce').dropna()
            if curr.empty:
                return 'unknown', None

            has_positive = (curr > 0).any()
            has_negative = (curr < 0).any()

            if has_positive and has_negative:
                return 'bipolar', None

            # Unipolar — look for a state column
            state_col = self.find_state_column(df)
            if state_col:
                return 'unipolar_with_state_col', state_col

            return 'unknown', None

        except Exception as exc:
            logging.warning(f"CurrentDirectionHandler.detect() failed: {exc}")
            return 'unknown', None

    def find_state_column(self, df, sample_rows: int = 500) -> Optional[str]:
        """
        Heuristic: find a low-cardinality string column where at least one
        unique value matches known charge/discharge keywords.

        Two-stage filter to minimise work on large files:

        Stage 1 — dtype gate (O(1) per column, zero data access):
            Skip numeric and datetime columns immediately.
            State columns are always object/string dtype.

        Stage 2 — unique-value check on a small head sample only:
            State labels repeat every few rows, so 500 rows is more than
            enough to see all unique values.
        """
        all_vals = self.DISCHARGE_VALS | self.CHARGE_VALS | self.REST_VALS
        sample = df.iloc[:sample_rows]

        for col in df.columns:
            # Stage 1: free dtype check — skip numeric and datetime columns
            col_dtype = df[col].dtype
            if pd.api.types.is_numeric_dtype(col_dtype):
                continue
            if pd.api.types.is_datetime64_any_dtype(col_dtype):
                continue

            # Stage 2: unique-value scan on the small sample only
            try:
                uniq = (
                    sample[col]
                    .dropna()
                    .astype(str)
                    .str.strip()
                    .str.lower()
                    .unique()
                )
                if len(uniq) == 0 or len(uniq) > 10:
                    continue
                if any(v in all_vals for v in uniq):
                    return col
            except Exception:
                continue

        return None

    def normalize(
        self,
        df,
        current_col: str,
        convention: str,
        state_col: Optional[str] = None,
        discharge_vals: Optional[list[str]] = None,
    ) -> pd.Series:
        """
        Return a signed current Series (discharge = negative).

        Parameters
        ----------
        discharge_vals : override list of state values that mean "discharge"
        """
        try:
            curr = pd.to_numeric(df[current_col], errors='coerce')

            if convention == 'bipolar':
                return curr

            if convention == 'unipolar_with_state_col' and state_col:
                dch_set = frozenset(
                    v.lower().strip() for v in (discharge_vals or self.DISCHARGE_VALS)
                )
                state_norm = df[state_col].astype(str).str.strip().str.lower()
                is_discharge = state_norm.isin(dch_set)
                result = curr.copy()
                result.loc[is_discharge] = result.loc[is_discharge].abs() * -1
                return result

            # Fallback: return as-is with a warning
            logging.warning(
                "CurrentDirectionHandler.normalize(): convention='%s', "
                "state_col='%s' — returning raw values unchanged.",
                convention, state_col,
            )
            return pd.to_numeric(df[current_col], errors='coerce')

        except Exception as exc:
            logging.warning(f"CurrentDirectionHandler.normalize() failed: {exc}")
            return pd.to_numeric(df[current_col], errors='coerce')


# ────────────────────────────────────────────────────────────────────────────
# StepNameNormalizer
# ────────────────────────────────────────────────────────────────────────────

class StepNameNormalizer:
    """Map raw step name values to: 'Rest' | 'Charge' | 'Discharge' | 'Control'."""

    # Patterns checked in order; first match wins
    _CHARGE_PATS = [
        r'^c$', r'^ch$', r'^chg$', r'charge', r'laden', r'ladung',
        r'充电', r'cvccharge',
    ]
    _DISCHARGE_PATS = [
        r'^d$', r'^dch$', r'^dis$', r'discharge', r'entladen', r'entladung',
        r'放电',
    ]
    _REST_PATS = [
        r'^r$', r'^o$', r'^ocp$', r'rest', r'pause', r'relaxation',
        r'idle', r'静置',
    ]
    _CONTROL_PATS = [
        r'^ctrl$', r'^ctl$', r'control', r'formation', r'controlstep',
    ]

    _COMPILED: dict = {}

    def __init__(self):
        self._COMPILED = {
            'Charge':    [re.compile(p, re.IGNORECASE) for p in self._CHARGE_PATS],
            'Discharge': [re.compile(p, re.IGNORECASE) for p in self._DISCHARGE_PATS],
            'Rest':      [re.compile(p, re.IGNORECASE) for p in self._REST_PATS],
            'Control':   [re.compile(p, re.IGNORECASE) for p in self._CONTROL_PATS],
        }

    def normalize(self, series: pd.Series) -> pd.Series:
        """
        Map each unique raw value to a normalised step name.
        Unknown values become None (NaN).
        """
        unique_vals = series.dropna().unique()
        mapping: dict = {}

        for val in unique_vals:
            norm_val = str(val).strip().lower()
            mapped = self._match(norm_val)
            mapping[val] = mapped

        return series.map(mapping)

    def _match(self, norm_val: str) -> Optional[str]:
        for label, patterns in self._COMPILED.items():
            for pat in patterns:
                if pat.search(norm_val):
                    return label
        return None

    def infer_from_current(self, current_series: pd.Series) -> pd.Series:
        """
        Infer step name from current sign:
            > 0 → Charge
            < 0 → Discharge
            = 0 → Rest
        Used when no Step_name column is found.
        """
        curr = pd.to_numeric(current_series, errors='coerce')
        return curr.apply(
            lambda x: 'Charge' if x > 0 else ('Discharge' if x < 0 else 'Rest')
        )


# ────────────────────────────────────────────────────────────────────────────
# CapacityTransformer
# ────────────────────────────────────────────────────────────────────────────

class CapacityTransformer:
    """
    Compute step-level signed capacity (Ah) from various source layouts.

    Conventions
    -----------
    'direct_signed'    – single column, values reset at each step, bipolar signed
    'direct_unsigned'  – single column, values reset at each step, always positive
    'split_ch_dch'     – separate charge / discharge capacity columns (TRURON/GOT)
    'cumulative'       – monotonically increasing; need to diff within each step
    """

    def detect_convention(
        self,
        df,
        cap_col: str,
        step_col: Optional[str] = None,
    ) -> str:
        """
        Heuristic to pick the right capacity convention.
        """
        try:
            cap = pd.to_numeric(df[cap_col], errors='coerce').dropna()

            # Check for split ch/dch columns by name inspection
            col_lower = [c.lower() for c in df.columns]
            has_chg = any('charge cap' in c or 'charge capacity' in c for c in col_lower)
            has_dch = any('discharge cap' in c or 'discharge capacity' in c for c in col_lower)
            if has_chg and has_dch:
                return 'split_ch_dch'

            # Check monotonicity (cumulative)
            if step_col and step_col in df.columns:
                # if values never reset across steps, likely cumulative
                step = pd.to_numeric(df[step_col], errors='coerce')
                if step.notna().any():
                    first_step = step.dropna().iloc[0]
                    step_mask = step == first_step
                    step_cap = cap[step_mask]
                    if step_cap.is_monotonic_increasing and step_cap.max() > 1.0:
                        return 'cumulative'

            # Default
            if (cap < 0).any():
                return 'direct_signed'
            return 'direct_unsigned'

        except Exception as exc:
            logging.warning(f"CapacityTransformer.detect_convention() failed: {exc}")
            return 'direct_signed'

    def compute_step_capacity(
        self,
        df,
        cap_col: str,
        convention: str,
        step_col: Optional[str] = None,
        ch_col: Optional[str] = None,
        dch_col: Optional[str] = None,
    ) -> Optional[pd.Series]:
        """
        Compute step-level signed capacity.

        Parameters
        ----------
        ch_col, dch_col : required for 'split_ch_dch' convention
        step_col        : required for 'cumulative' convention
        """
        try:
            if convention in ('direct_signed', 'direct_unsigned'):
                cap = pd.to_numeric(df[cap_col], errors='coerce')
                if step_col and step_col in df.columns:
                    return self._reset_per_step(cap, df[step_col])
                return cap

            if convention == 'split_ch_dch':
                if not (ch_col and dch_col):
                    ch_col, dch_col = self._find_ch_dch_cols(df)
                if not (ch_col and dch_col):
                    logging.warning("split_ch_dch: could not find charge/discharge cols.")
                    return pd.to_numeric(df[cap_col], errors='coerce')

                ch  = pd.to_numeric(df[ch_col],  errors='coerce')
                dch = pd.to_numeric(df[dch_col], errors='coerce')

                if step_col and step_col in df.columns:
                    step = pd.to_numeric(df[step_col], errors='coerce')
                    out = pd.Series(index=df.index, dtype='float64')
                    for sv in step.dropna().unique():
                        mask = step == sv
                        ch_s  = ch[mask]
                        dch_s = dch[mask]
                        out.loc[mask] = (ch_s - ch_s.iloc[0]) - (dch_s - dch_s.iloc[0])
                    return out
                else:
                    return (ch - ch.iloc[0]) - (dch - dch.iloc[0])

            if convention == 'cumulative':
                cap = pd.to_numeric(df[cap_col], errors='coerce')
                if step_col and step_col in df.columns:
                    return self._reset_per_step(cap, df[step_col])
                return cap.diff().clip(lower=0).cumsum()

            logging.warning(f"CapacityTransformer: unknown convention '{convention}'")
            return pd.to_numeric(df[cap_col], errors='coerce')

        except Exception as exc:
            logging.warning(f"CapacityTransformer.compute_step_capacity() failed: {exc}")
            return None

    @staticmethod
    def _reset_per_step(cap: pd.Series, step_series) -> pd.Series:
        """Reset capacity to zero at the start of each step."""
        step = pd.to_numeric(step_series, errors='coerce')
        out = pd.Series(index=cap.index, dtype='float64')
        for sv in step.dropna().unique():
            mask = step == sv
            s = cap[mask]
            out.loc[mask] = s - s.iloc[0]
        return out

    @staticmethod
    def _find_ch_dch_cols(df) -> tuple[Optional[str], Optional[str]]:
        """Heuristically find charge and discharge capacity columns."""
        ch_col = dch_col = None
        for c in df.columns:
            cl = c.lower()
            if 'charge cap' in cl or 'charge capacity' in cl:
                if 'discharge' not in cl:
                    ch_col = c
                else:
                    dch_col = c
        return ch_col, dch_col


# ────────────────────────────────────────────────────────────────────────────
# DerivedColumnsCalculator
# ────────────────────────────────────────────────────────────────────────────

class DerivedColumnsCalculator:
    """Compute Power and Unix_time from already-assembled harmonized DataFrame."""

    @staticmethod
    def calc_power(df) -> Optional[pd.Series]:
        """P = V * I."""
        try:
            if 'Voltage_V' in df.columns and 'Current_A' in df.columns:
                v = pd.to_numeric(df['Voltage_V'], errors='coerce')
                i = pd.to_numeric(df['Current_A'], errors='coerce')
                return v * i
            return None
        except Exception as exc:
            logging.warning(f"DerivedColumnsCalculator.calc_power() failed: {exc}")
            return None

    @staticmethod
    def calc_unix_time(df) -> Optional[pd.Series]:
        """Unix timestamp (seconds since epoch) from Date_time column."""
        try:
            if 'Date_time' in df.columns:
                dt = pd.to_datetime(df['Date_time'], errors='coerce')
                return dt.apply(lambda x: x.timestamp() if pd.notna(x) else float('nan'))
            return None
        except Exception as exc:
            logging.warning(f"DerivedColumnsCalculator.calc_unix_time() failed: {exc}")
            return None
