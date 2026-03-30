"""
column_mapper.py
----------------
Scores raw source columns against COLUMN_REGISTRY keyword lists and
performs a greedy one-to-one assignment.

Scoring tiers
-------------
  exact match (lowercased col == keyword)  → 1.0
  starts-with keyword_high                 → 0.85
  contains keyword_high                    → 0.70
  starts-with keyword_med                  → 0.60
  contains keyword_med                     → 0.50
  no match                                 → 0.0

Override dict (from OverrideLoader) can force assignments before greedy step.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from harmonize.column_registry import (
    COLUMN_REGISTRY, MANDATORY_COLS, ALWAYS_DERIVED_COLS,
    TargetColumnDef,
)


def _normalise(col_name: str) -> str:
    """Lowercase, strip whitespace, collapse internal whitespace.

    Unit suffixes are kept so that keywords like 'u(v)' and 'i(a)'
    can match source columns 'U(V)' and 'I(A)' exactly.
    """
    s = str(col_name).lower().strip()
    s = re.sub(r'\s+', ' ', s)
    return s


@dataclass
class MappingResult:
    column_map: dict[str, str]          # {target_col: source_col}
    confidence: dict[str, float]        # {target_col: 0.0-1.0}
    unmatched_targets: list[str]        # mandatory targets not found above threshold
    unmatched_sources: list[str]        # source cols not assigned to any target
    is_valid: bool                      # True if all MANDATORY_COLS have a mapping
    notes: list[str] = field(default_factory=list)


class ColumnMapper:
    # Minimum confidence to accept a mandatory column assignment
    MANDATORY_THRESHOLD: float = 0.3
    # Minimum confidence for optional columns (slightly higher to avoid false positives)
    OPTIONAL_THRESHOLD: float = 0.4

    # ── Public API ─────────────────────────────────────────────────────────────

    def map(
        self,
        df_or_columns,       # pd.DataFrame OR list[str]
        overrides: dict = None,
    ) -> MappingResult:
        """
        Map source columns to target columns.

        Parameters
        ----------
        df_or_columns : pd.DataFrame or list[str]
            Raw data frame or just its column names.
        overrides : dict, optional
            Forced assignments from OverrideLoader, keyed by target column name.
            Each value must have a 'source' key (and optional 'confidence').

        Returns
        -------
        MappingResult
        """
        import pandas as pd

        if isinstance(df_or_columns, pd.DataFrame):
            source_cols = list(df_or_columns.columns)
        else:
            source_cols = list(df_or_columns)

        overrides = overrides or {}
        notes: list[str] = []

        # Normalise source col names for matching
        norm_map: dict[str, str] = {_normalise(c): c for c in source_cols}
        # Guard against collisions after normalisation
        if len(norm_map) < len(source_cols):
            notes.append("WARNING: Some source columns have identical normalised names; "
                         "duplicates were silently dropped from scoring.")

        # 1. Score all (target, source_norm) pairs
        scores: dict[tuple[str, str], float] = {}
        for target, defn in COLUMN_REGISTRY.items():
            if target in ALWAYS_DERIVED_COLS:
                continue   # never assigned from source
            for norm, orig in norm_map.items():
                sc = self._score(norm, defn)
                if sc > 0.0:
                    scores[(target, orig)] = sc

        # 2. Apply forced overrides (confidence = 1.0) — override before greedy
        forced_targets: set[str] = set()
        forced_sources: set[str] = set()
        column_map: dict[str, str] = {}
        confidence: dict[str, float] = {}

        for target, ov in overrides.items():
            src = ov.get('source')
            if src and src in source_cols:
                column_map[target] = src
                confidence[target] = ov.get('confidence', 1.0)
                forced_targets.add(target)
                forced_sources.add(src)
                notes.append(f"Override forced: {target} → '{src}'")
            elif src:
                notes.append(f"Override source '{src}' for {target} not found in file columns.")

        # 3. Greedy assignment (score-descending, one source per target)
        sorted_pairs = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        assigned_targets = set(forced_targets)
        assigned_sources = set(forced_sources)

        for (target, orig), sc in sorted_pairs:
            if target in assigned_targets:
                continue
            if orig in assigned_sources:
                continue

            defn = COLUMN_REGISTRY[target]
            threshold = (self.MANDATORY_THRESHOLD if defn.mandatory
                         else self.OPTIONAL_THRESHOLD)
            if sc < threshold:
                continue

            column_map[target] = orig
            confidence[target] = sc
            assigned_targets.add(target)
            assigned_sources.add(orig)

        # 4. Identify gaps
        mandatory_found = [
            t for t in MANDATORY_COLS
            if t in column_map and confidence.get(t, 0) >= self.MANDATORY_THRESHOLD
        ]
        unmatched_targets = [t for t in MANDATORY_COLS if t not in column_map]
        unmatched_sources = [c for c in source_cols if c not in assigned_sources]

        is_valid = len(unmatched_targets) == 0

        # 5. Log summary
        for t in unmatched_targets:
            logging.warning(f"ColumnMapper: mandatory target '{t}' not mapped.")
        for t, src in column_map.items():
            logging.debug(f"  {t:25s} ← '{src}'  (confidence={confidence[t]:.2f})")

        return MappingResult(
            column_map=column_map,
            confidence=confidence,
            unmatched_targets=unmatched_targets,
            unmatched_sources=unmatched_sources,
            is_valid=is_valid,
            notes=notes,
        )

    # ── Scoring ────────────────────────────────────────────────────────────────

    @staticmethod
    def _score(source_norm: str, defn: TargetColumnDef) -> float:
        """
        Score a normalised source column name against a TargetColumnDef.
        Returns a float in [0.0, 1.0].
        """
        # Exact keyword match (highest confidence)
        for kw in defn.keywords_exact:
            if source_norm == kw:
                return 1.0

        best = 0.0

        # High-tier keywords
        for kw in defn.keywords_high:
            if source_norm.startswith(kw):
                best = max(best, 0.85)
            elif kw in source_norm:
                best = max(best, 0.70)

        # Medium-tier keywords
        for kw in defn.keywords_med:
            if source_norm.startswith(kw):
                best = max(best, 0.60)
            elif kw in source_norm:
                best = max(best, 0.50)

        return best
