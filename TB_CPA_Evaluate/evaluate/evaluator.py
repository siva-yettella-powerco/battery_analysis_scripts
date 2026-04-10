"""
evaluator.py  —  TB_CPA_Evaluate
==================================
Orchestrates per-step feature extraction.

Usage
-----
    from evaluate.evaluator import StepEvaluator
    result = StepEvaluator().run(Path("some_harmonized.csv"))
    result.summary.to_csv("output.csv", index=False)
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from step_loader import (
    TEMP_SUFFIX_MAP,
    load_and_prepare,
)
from signal_features import (
    STANDARD_OFFSETS,
    STANDARD_SUFFIXES,
    VOLTAGE_OFFSETS,
    VOLTAGE_SUFFIXES,
    offset_features,
    stat_features,
    time_features,
)
from step_classifier import classify_step

logger = logging.getLogger(__name__)

# ── Output column order ───────────────────────────────────────────────────────
_FIXED_COLS = [
    # Metadata
    'Step_ID', 'Cycle', 'Step_name_raw', 'n_rows', 'Step_type',
    # Time
    'unix_start', 'unix_end', 'duration_s', 'dt_median_s', 'dt_min_s', 'dt_max_s',
    # Voltage (7 offsets + final)
    'V_t0', 'V_t1s', 'V_t10s', 'V_t18s', 'V_t180s', 'V_t1800s', 'V_t3600s', 'V_final',
    # Current (5 offsets + final + stats)
    'I_t0', 'I_t1s', 'I_t10s', 'I_t18s', 'I_t180s', 'I_final', 'I_mean', 'I_median',
    # Power (5 offsets + final + stats)
    'P_t0', 'P_t1s', 'P_t10s', 'P_t18s', 'P_t180s', 'P_final', 'P_mean', 'P_median',
    # Capacity (5 offsets + final)
    'Ah_t0', 'Ah_t1s', 'Ah_t10s', 'Ah_t18s', 'Ah_t180s', 'Ah_final',
    # Energy (5 offsets + final — omitted if column absent)
    'Wh_t0', 'Wh_t1s', 'Wh_t10s', 'Wh_t18s', 'Wh_t180s', 'Wh_final',
    # Temperature columns appended dynamically
]


@dataclass
class EvaluateResult:
    summary:   pd.DataFrame
    filepath:  Path
    is_valid:  bool
    n_steps:   int
    warnings:  list = field(default_factory=list)
    errors:    list = field(default_factory=list)


class StepEvaluator:
    """
    Per-step evaluation orchestrator.

    Parameters
    ----------
    current_threshold_a : |I_mean| below this is classified as Rest (passed
                          through to step_classifier constants — for reference;
                          classifier uses its own module-level constant).
    """

    def __init__(self, current_threshold_a: float = 0.05):
        self.current_threshold_a = current_threshold_a

    # ── Public ────────────────────────────────────────────────────────────────

    def run(self, filepath: Path) -> EvaluateResult:
        """
        Full evaluation pipeline for a single harmonized CSV.

        1. Load & prepare (step_loader)
        2. GroupBy Step → _evaluate_group() for each group
        3. Assemble output DataFrame
        4. Return EvaluateResult
        """
        filepath = Path(filepath)
        errors: list[str] = []
        warnings: list[str] = []

        try:
            df, temp_cols, load_warnings = load_and_prepare(filepath)
            warnings.extend(load_warnings)
        except ValueError as exc:
            return EvaluateResult(
                summary=pd.DataFrame(),
                filepath=filepath,
                is_valid=False,
                n_steps=0,
                warnings=warnings,
                errors=[str(exc)],
            )
        except Exception as exc:
            return EvaluateResult(
                summary=pd.DataFrame(),
                filepath=filepath,
                is_valid=False,
                n_steps=0,
                warnings=warnings,
                errors=[f"Unexpected error loading file: {exc}"],
            )

        has_energy = 'Energy_step_Wh' in df.columns and not df['Energy_step_Wh'].isna().all()

        rows = []
        for step_id, grp in df.groupby('Step', sort=True):
            grp = grp.reset_index(drop=True)
            try:
                row = self._evaluate_group(step_id, grp, temp_cols, has_energy)
                rows.append(row)
            except Exception as exc:
                warnings.append(f"Step {step_id}: evaluation failed — {exc}")

        if not rows:
            return EvaluateResult(
                summary=pd.DataFrame(),
                filepath=filepath,
                is_valid=False,
                n_steps=0,
                warnings=warnings,
                errors=['No step groups produced output.'],
            )

        summary = pd.DataFrame(rows)
        summary = self._order_columns(summary, temp_cols, has_energy)

        logger.info(
            f"Evaluated {filepath.name}: {len(summary)} steps, "
            f"{len(summary.columns)} output columns"
        )

        return EvaluateResult(
            summary=summary,
            filepath=filepath,
            is_valid=True,
            n_steps=len(summary),
            warnings=warnings,
            errors=errors,
        )

    # ── Private ───────────────────────────────────────────────────────────────

    def _evaluate_group(
        self,
        step_id,
        grp: pd.DataFrame,
        temp_cols: list[str],
        has_energy: bool,
    ) -> dict:
        """Produce one output row (flat dict) for a single step group."""
        row: dict = {}

        # ── Metadata ──────────────────────────────────────────────────────────
        row['Step_ID'] = int(step_id) if pd.notna(step_id) else step_id

        row['Cycle'] = (
            float(grp['Cycle'].dropna().iloc[0])
            if 'Cycle' in grp.columns and not grp['Cycle'].isna().all()
            else float('nan')
        )
        row['Step_name_raw'] = (
            str(grp['Step_name'].dropna().iloc[0])
            if 'Step_name' in grp.columns and not grp['Step_name'].isna().all()
            else None
        )
        row['n_rows'] = len(grp)
        row['Step_type'] = classify_step(grp)

        # ── Time features ─────────────────────────────────────────────────────
        row.update(time_features(grp))

        # ── Voltage (extended offsets: 0, 1, 10, 18, 180, 1800, 3600 + final) ─
        row.update(offset_features(
            grp, col='Voltage_V', prefix='V_',
            offsets=VOLTAGE_OFFSETS, suffix_names=VOLTAGE_SUFFIXES,
            include_final=True,
        ))

        # ── Current (standard offsets + final + mean/median) ──────────────────
        row.update(offset_features(
            grp, col='Current_A', prefix='I_',
            offsets=STANDARD_OFFSETS, suffix_names=STANDARD_SUFFIXES,
            include_final=True,
        ))
        row.update(stat_features(grp, col='Current_A', prefix='I_'))

        # ── Power (standard offsets + final + mean/median) ────────────────────
        row.update(offset_features(
            grp, col='Power_W', prefix='P_',
            offsets=STANDARD_OFFSETS, suffix_names=STANDARD_SUFFIXES,
            include_final=True,
        ))
        row.update(stat_features(grp, col='Power_W', prefix='P_'))

        # ── Capacity (standard offsets + final; no stats — resets per step) ───
        row.update(offset_features(
            grp, col='Capacity_step_Ah', prefix='Ah_',
            offsets=STANDARD_OFFSETS, suffix_names=STANDARD_SUFFIXES,
            include_final=True,
        ))

        # ── Energy (standard offsets + final; only if column present) ─────────
        if has_energy:
            row.update(offset_features(
                grp, col='Energy_step_Wh', prefix='Wh_',
                offsets=STANDARD_OFFSETS, suffix_names=STANDARD_SUFFIXES,
                include_final=True,
            ))

        # ── Temperature (per-channel, dynamic set) ────────────────────────────
        for col in temp_cols:
            suffix = TEMP_SUFFIX_MAP.get(col, col)
            prefix = f'T_{suffix}_'
            row.update(offset_features(
                grp, col=col, prefix=prefix,
                offsets=STANDARD_OFFSETS, suffix_names=STANDARD_SUFFIXES,
                include_final=True,
            ))
            row.update(stat_features(grp, col=col, prefix=prefix))

        return row

    @staticmethod
    def _order_columns(
        df: pd.DataFrame,
        temp_cols: list[str],
        has_energy: bool,
    ) -> pd.DataFrame:
        """Enforce a predictable column order in the output."""
        ordered = []

        # Fixed block (drop energy cols if not present)
        for col in _FIXED_COLS:
            if col.startswith('Wh_') and not has_energy:
                continue
            if col in df.columns:
                ordered.append(col)

        # Dynamic temperature columns (in TEMP_SUFFIX_MAP order)
        for src_col in temp_cols:
            suffix = TEMP_SUFFIX_MAP.get(src_col, src_col)
            prefix = f'T_{suffix}_'
            t_cols = [c for c in df.columns if c.startswith(prefix)]
            ordered.extend(t_cols)

        # Any remaining columns not covered above
        remaining = [c for c in df.columns if c not in ordered]
        ordered.extend(remaining)

        return df[ordered]
