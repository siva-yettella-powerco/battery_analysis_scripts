"""
harmonizer.py
-------------
Orchestrates FileInspector → ColumnMapper → TransformEngine → output DataFrame.

Usage
-----
    from harmonize.harmonizer import Harmonizer

    h = Harmonizer(override_dir=Path('harmonize/overrides'))
    result = h.run(Path('some_file.xlsx'))
    if result.is_valid:
        result.data.to_csv('output.csv', index=False)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

from harmonize.column_registry import FOCUS_COLS, MANDATORY_COLS
from harmonize.column_mapper import ColumnMapper, MappingResult
from harmonize.file_inspector import FileInspector
from harmonize.transform_engine import (
    TimeFormatDetector,
    TimeTransformer,
    CurrentDirectionHandler,
    StepNameNormalizer,
    CapacityTransformer,
    DerivedColumnsCalculator,
)
from harmonize.overrides.override_loader import OverrideLoader

# Minimum confidence to copy a non-mandatory column
_OPTIONAL_CONFIDENCE_THRESHOLD = 0.4


@dataclass
class HarmonizeResult:
    data: Optional[pd.DataFrame]       # unified output (may be None on failure)
    filepath: Path
    is_valid: bool                     # True if all mandatory cols present with data
    inspection: dict = field(default_factory=dict)
    mapping: Optional[MappingResult] = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class Harmonizer:
    """Supplier-agnostic harmonization orchestrator."""

    def __init__(self, override_dir: Optional[Path] = None):
        self.override_loader = (
            OverrideLoader(override_dir) if override_dir else None
        )
        self.mapper = ColumnMapper()

    # ── Public API ─────────────────────────────────────────────────────────────

    def run(self, filepath: Path) -> HarmonizeResult:
        """
        Full harmonization pipeline.

        Returns a HarmonizeResult; is_valid=False signals a skipped file.
        """
        filepath = Path(filepath)
        warnings: list[str] = []
        errors:   list[str] = []

        # ── Step 1: Inspect file ───────────────────────────────────────────────
        inspector = FileInspector(filepath)
        data, inspection = inspector.load_data()
        warnings.extend(inspection.get('warnings', []))

        if data is None or data.empty:
            errors.append(f"Failed to load file or file is empty: {filepath.name}")
            return HarmonizeResult(
                data=None, filepath=filepath, is_valid=False,
                inspection=inspection, warnings=warnings, errors=errors,
            )

        # ── Step 2: Load + apply overrides ────────────────────────────────────
        override = {}
        if self.override_loader:
            override = self.override_loader.match(filepath)
            inspection = self.override_loader.apply_to_inspection(inspection, override)

        # Re-load a specific sheet/header if override forces it
        if '_forced_sheet' in inspection or '_forced_header_row' in inspection:
            data = self._reload_with_forced_params(filepath, inspection, warnings)
            if data is None:
                errors.append("Forced sheet/header reload failed.")
                return HarmonizeResult(
                    data=None, filepath=filepath, is_valid=False,
                    inspection=inspection, warnings=warnings, errors=errors,
                )

        # ── Step 3: Map columns ───────────────────────────────────────────────
        col_overrides = override.get('column_overrides', {})
        # Build source-only overrides (just the 'source' key) for ColumnMapper
        mapper_overrides = {
            t: {'source': v['source'], 'confidence': 1.0}
            for t, v in col_overrides.items()
            if 'source' in v
        }
        mapping = self.mapper.map(data, overrides=mapper_overrides)

        if not mapping.is_valid:
            missing = ', '.join(mapping.unmatched_targets)
            errors.append(f"Mandatory columns not found: {missing}")
            logging.error(f"[{filepath.name}] Mandatory columns missing: {missing}")
            return HarmonizeResult(
                data=None, filepath=filepath, is_valid=False,
                inspection=inspection, mapping=mapping,
                warnings=warnings, errors=errors,
            )

        # ── Step 4: Build unified DataFrame ───────────────────────────────────
        try:
            out_df, build_warnings = self._build_unified(data, mapping, override, col_overrides)
            warnings.extend(build_warnings)
        except Exception as exc:
            errors.append(f"Build unified failed: {exc}")
            logging.exception(f"[{filepath.name}] _build_unified raised")
            return HarmonizeResult(
                data=None, filepath=filepath, is_valid=False,
                inspection=inspection, mapping=mapping,
                warnings=warnings, errors=errors,
            )

        # ── Step 5: Final validation ──────────────────────────────────────────
        is_valid = all(
            col in out_df.columns and out_df[col].notna().any()
            for col in MANDATORY_COLS
        )
        if not is_valid:
            errors.append("Output is missing data in mandatory columns after transform.")

        return HarmonizeResult(
            data=out_df,
            filepath=filepath,
            is_valid=is_valid,
            inspection=inspection,
            mapping=mapping,
            warnings=warnings,
            errors=errors,
        )

    # ── Build unified DataFrame ────────────────────────────────────────────────

    def _build_unified(
        self,
        data: pd.DataFrame,
        mapping: MappingResult,
        override: dict,
        col_overrides: dict,
    ) -> tuple[pd.DataFrame, list[str]]:
        df = pd.DataFrame(index=data.index)
        build_warnings: list[str] = []

        tfd = TimeFormatDetector()
        tt  = TimeTransformer()

        # ── 1. Direct copies (non-specialised columns) ─────────────────────────
        skip_cols = {
            'Total_time_s', 'Date_time', 'Current_A',
            'Step_name', 'Capacity_step_Ah', 'Power_W', 'Unix_time',
        }
        for target, source in mapping.column_map.items():
            if target in skip_cols:
                continue
            conf = mapping.confidence.get(target, 0.0)
            if conf < _OPTIONAL_CONFIDENCE_THRESHOLD:
                build_warnings.append(
                    f"Skipping '{target}' (confidence={conf:.2f} < threshold)"
                )
                continue
            df[target] = pd.to_numeric(data[source], errors='coerce')

        # ── 2. Total_time_s ────────────────────────────────────────────────────
        if 'Total_time_s' in mapping.column_map:
            src = mapping.column_map['Total_time_s']
            fmt_hint = OverrideLoader.get_time_format_hint(override, 'Total_time_s')
            fmt = fmt_hint or tfd.detect(data[src])
            result = tt.to_total_seconds(data[src], fmt)
            if result is not None:
                df['Total_time_s'] = result
            else:
                build_warnings.append(f"Could not convert '{src}' to seconds (fmt='{fmt}')")
        else:
            build_warnings.append("No source for Total_time_s; column will be absent.")

        # ── 3. Date_time ───────────────────────────────────────────────────────
        if 'Date_time' in mapping.column_map:
            src = mapping.column_map['Date_time']
            fmt_hint = OverrideLoader.get_time_format_hint(override, 'Date_time')
            fmt = fmt_hint or tfd.detect(data[src])
            result = tt.to_datetime(data[src], fmt)
            if result is not None:
                df['Date_time'] = result
            else:
                build_warnings.append(
                    f"Could not parse '{src}' as datetime (fmt='{fmt}'). "
                    "Date_time will be absent."
                )

        # ── 4. Current_A ───────────────────────────────────────────────────────
        if 'Current_A' in mapping.column_map:
            src = mapping.column_map['Current_A']
            cdh = CurrentDirectionHandler()
            dir_hint = OverrideLoader.get_direction_hint(override)

            convention = dir_hint.get('convention') or None
            state_col  = dir_hint.get('state_col')  or None
            dch_vals   = dir_hint.get('discharge_vals') or None

            if convention is None:
                convention, state_col = cdh.detect(data, src)

            df['Current_A'] = cdh.normalize(
                data, src, convention,
                state_col=state_col,
                discharge_vals=dch_vals or None,
            )
        else:
            build_warnings.append("No source for Current_A; column will be absent.")

        # ── 5. Step_name ───────────────────────────────────────────────────────
        snn = StepNameNormalizer()
        if 'Step_name' in mapping.column_map:
            src = mapping.column_map['Step_name']
            df['Step_name'] = snn.normalize(data[src])
        elif 'Current_A' in df.columns:
            build_warnings.append(
                "Step_name not found; inferring from Current_A sign."
            )
            df['Step_name'] = snn.infer_from_current(df['Current_A'])

        # ── 6. Capacity_step_Ah ────────────────────────────────────────────────
        if 'Capacity_step_Ah' in mapping.column_map:
            src = mapping.column_map['Capacity_step_Ah']
            ct  = CapacityTransformer()
            step_col = mapping.column_map.get('Step')
            cap_hint = OverrideLoader.get_capacity_hint(override)

            # Resolve split ch/dch columns if available
            ch_col  = mapping.column_map.get('_ch_cap_col')   # internal key (set by mapper if found)
            dch_col = mapping.column_map.get('_dch_cap_col')

            convention = cap_hint or ct.detect_convention(data, src, step_col)
            result = ct.compute_step_capacity(
                data, src, convention, step_col=step_col,
                ch_col=ch_col, dch_col=dch_col,
            )
            if result is not None:
                df['Capacity_step_Ah'] = result
            else:
                build_warnings.append("Capacity computation failed; column will be absent.")
        else:
            build_warnings.append("No source for Capacity_step_Ah; column will be absent.")

        # ── 7. Derived: Power_W ────────────────────────────────────────────────
        if 'Power_W' in mapping.column_map:
            src = mapping.column_map['Power_W']
            df['Power_W'] = pd.to_numeric(data[src], errors='coerce')
        else:
            dc = DerivedColumnsCalculator()
            power = dc.calc_power(df)
            if power is not None:
                df['Power_W'] = power

        # ── 8. Derived: Unix_time ─────────────────────────────────────────────
        dc = DerivedColumnsCalculator()
        unix = dc.calc_unix_time(df)
        if unix is not None:
            df['Unix_time'] = unix

        # ── 9. Reorder to standard schema ─────────────────────────────────────
        out_cols = [c for c in FOCUS_COLS if c in df.columns]
        return df[out_cols], build_warnings

    # ── Reload with forced params ─────────────────────────────────────────────

    @staticmethod
    def _reload_with_forced_params(
        filepath: Path,
        inspection: dict,
        warnings: list[str],
    ) -> Optional[pd.DataFrame]:
        """
        Re-run FileInspector but override sheet and/or header_row from inspection dict.
        """
        try:
            inspector = FileInspector(filepath)
            fmt = inspector.detect_file_format()
            sheets = inspector._load_all_sheets(fmt, {})

            forced_sheet = inspection.get('_forced_sheet')
            if forced_sheet:
                if forced_sheet not in sheets:
                    warnings.append(f"Forced sheet '{forced_sheet}' not found in file.")
                    return None
                raw = sheets[forced_sheet]
            else:
                raw = sheets[inspector.detect_data_sheet(sheets)]

            forced_header = inspection.get('_forced_header_row')
            header_row = forced_header if forced_header else inspector.detect_header_row(raw)

            return inspector._apply_header(raw, header_row)

        except Exception as exc:
            warnings.append(f"_reload_with_forced_params failed: {exc}")
            return None
