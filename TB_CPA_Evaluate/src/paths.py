"""
paths.py  —  TB_CPA_Evaluate / src
=====================================
Derives standard CDS project folder paths from a single BASE_PATH.

Folder convention (fixed — not user-configurable):
    BASE_PATH/
    ├── 03_Harmonized_Data/        ← input CSVs
    ├── 04_Evaluated_Data/         ← pipeline outputs
    └── 06_Logs/
        └── debug_logs/            ← evaluation run logs
"""

import os
from pathlib import Path


class PATHS_OBJ:
    """Derives all standard CDS paths from a project BASE_PATH."""

    def __init__(self, base_path):
        base = Path(base_path)

        # ── Folder layout (do not change) ─────────────────────────────────────
        self.harmonized_path = base / "03_Harmonized_Data"
        self.evaluated_path  = base / "04_Evaluated_Data"
        self.logs_path       = base / "06_Logs"
        self.debug_path      = self.logs_path / "debug_logs"

        self.debug_path.mkdir(parents=True, exist_ok=True)


def long_path(anypath: Path, path_length_thresh: int = 0) -> Path:
    """Prepend \\?\\ to support Windows paths exceeding 260 characters."""
    normalized = os.fspath(anypath.absolute())
    if len(normalized) > path_length_thresh:
        if not normalized.startswith('\\\\?\\'):
            normalized = '\\\\?\\' + normalized
        return Path(normalized)
    return anypath
