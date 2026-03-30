"""
override_loader.py
------------------
Load YAML override files and merge them into FileInspector / ColumnMapper outputs.

Override YAML format
--------------------
match_pattern: "*MCM*_FC*.xlsx"          # fnmatch against filename
description: "MCM standard FC format"   # human-readable

sheet: "Record"          # optional: force sheet name
header_row: 3            # optional: force header row (1-based)

column_overrides:
  Total_time_s:
    source: "Test Time"
    time_format: "d_hms_ms"

  Current_A:
    source: "Current(A)"
    direction_convention: "unipolar_with_state_col"
    direction_state_col: "Step Type"
    direction_discharge_vals: ["D"]

  Capacity_step_Ah:
    source: "Capacity(Ah)"
    capacity_convention: "direct_unsigned"

Design
------
- Additive: override patches specific fields, never replaces whole auto-detection
- First YAML file whose match_pattern matches the filename wins
- OverrideLoader is instantiated once; match() is called per file
"""

from __future__ import annotations

import fnmatch
import logging
from pathlib import Path
from typing import Optional

import yaml

from harmonize.column_mapper import MappingResult


class OverrideLoader:
    """Load all *.yaml files in override_dir; match against filenames."""

    def __init__(self, override_dir: Path):
        self.override_dir = Path(override_dir)
        self._overrides: list[dict] = []
        self._load_all()

    # ── Initialisation ─────────────────────────────────────────────────────────

    def _load_all(self) -> None:
        if not self.override_dir.is_dir():
            logging.warning(f"OverrideLoader: directory does not exist: {self.override_dir}")
            return

        for yaml_path in sorted(self.override_dir.glob('**/*.yaml')):
            try:
                with open(yaml_path, encoding='utf-8') as fh:
                    data = yaml.safe_load(fh)
                if isinstance(data, dict) and 'match_pattern' in data:
                    self._overrides.append(data)
                    logging.debug(f"Loaded override: {yaml_path.name}")
                else:
                    logging.warning(f"Override file missing 'match_pattern': {yaml_path}")
            except Exception as exc:
                logging.warning(f"Failed to load override '{yaml_path}': {exc}")

        logging.info(f"OverrideLoader: {len(self._overrides)} override(s) loaded.")

    # ── Public API ─────────────────────────────────────────────────────────────

    def match(self, filepath: Path) -> dict:
        """
        Find first override whose match_pattern matches filepath.name.
        Returns the override dict or {} if none match.
        """
        fname = Path(filepath).name
        for ov in self._overrides:
            pattern = ov.get('match_pattern', '')
            if fnmatch.fnmatch(fname, pattern):
                logging.info(
                    f"Override matched: '{pattern}' → '{fname}' "
                    f"({ov.get('description', 'no description')})"
                )
                return ov
        return {}

    def apply_to_inspection(self, inspection: dict, override: dict) -> dict:
        """
        Patch FileInspector report with forced sheet / header_row from override.
        Returns a new dict (original not mutated).
        """
        patched = dict(inspection)
        if 'sheet' in override:
            patched['_forced_sheet'] = override['sheet']
            logging.info(f"Override: forcing sheet = '{override['sheet']}'")
        if 'header_row' in override:
            patched['_forced_header_row'] = int(override['header_row'])
            logging.info(f"Override: forcing header_row = {override['header_row']}")
        return patched

    def apply_to_mapping(
        self,
        mapping: MappingResult,
        override: dict,
    ) -> MappingResult:
        """
        Patch MappingResult with forced column assignments from override.
        Returns a new MappingResult (original not mutated).
        """
        col_overrides = override.get('column_overrides', {})
        if not col_overrides:
            return mapping

        new_col_map  = dict(mapping.column_map)
        new_conf     = dict(mapping.confidence)
        new_notes    = list(mapping.notes)

        for target, ov in col_overrides.items():
            src = ov.get('source')
            if src:
                new_col_map[target]  = src
                new_conf[target]     = 1.0
                new_notes.append(f"Override: {target} → '{src}'")

        # Re-check validity
        from harmonize.column_registry import MANDATORY_COLS
        unmatched = [t for t in MANDATORY_COLS if t not in new_col_map]

        return MappingResult(
            column_map=new_col_map,
            confidence=new_conf,
            unmatched_targets=unmatched,
            unmatched_sources=mapping.unmatched_sources,
            is_valid=(len(unmatched) == 0),
            notes=new_notes,
        )

    # ── Convenience: extract per-column hints ──────────────────────────────────

    @staticmethod
    def get_time_format_hint(override: dict, target_col: str) -> Optional[str]:
        """Return 'time_format' hint for a target col, or None."""
        return override.get('column_overrides', {}).get(target_col, {}).get('time_format')

    @staticmethod
    def get_direction_hint(override: dict) -> dict:
        """
        Return direction-related hints for Current_A:
            {convention, state_col, discharge_vals}
        """
        ov = override.get('column_overrides', {}).get('Current_A', {})
        return {
            'convention':    ov.get('direction_convention'),
            'state_col':     ov.get('direction_state_col'),
            'discharge_vals': ov.get('direction_discharge_vals', []),
        }

    @staticmethod
    def get_capacity_hint(override: dict) -> Optional[str]:
        """Return capacity convention hint, or None."""
        return (override.get('column_overrides', {})
                        .get('Capacity_step_Ah', {})
                        .get('capacity_convention'))
