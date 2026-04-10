import warnings
from pathlib import Path
import logging
import os

def long_path(anypath: Path, path_length_thresh=0) -> Path:
    """Converts paths to \\?\ to support Windows long paths (>260 chars)."""
    normalized = os.fspath(anypath.absolute())
    if len(normalized) > path_length_thresh:
        if not normalized.startswith('\\\\?\\'):
            normalized = '\\\\?\\' + normalized
        return Path(normalized)
    return anypath

class PATHS_OBJ:
    """
    All folder paths for one project.
    Pass base_path as a constructor argument — no hardcoding required.

    Usage:
        paths = PATHS_OBJ(r"C:\\...\\B2-2_sample")
    """

    def __init__(self, base_path: str | Path):
        self.base_path = long_path(Path(base_path))

        # ── Folder layout (do not change) ─────────────────────────────────────
        self.dump_path          = self.base_path / "01_Incoming_Compressed_Files"
        self.extract_path       = self.base_path / "02_Extracted_Raw_Files"
        self.harmonized_path    = self.base_path / "03_Harmonized_Data"
        self.config_path        = self.base_path / "05_Configuration"
        self.config_file_path   = self.base_path / "05_Configuration" / "format_config.yaml"
        self.ETL_config_path    = self.base_path / "05_Configuration" / "supplier_data_ETL_config.xlsx"
        self.logs_path          = self.base_path / "06_Logs"
        self.archived_path      = self.base_path / "07_Archived"
        self.backlog_path       = self.base_path / "08_Backlog"

        # Additional sub-folders
        self.debug_path   = self.logs_path / "debug_logs"
        self.backend_path = self.logs_path / "backend_base"

        self.debug_path.mkdir(parents=True, exist_ok=True)
        self.backend_path.mkdir(parents=True, exist_ok=True)

    def check_if_exists(self) -> bool:
        all_paths = {
            "dump_path":       self.dump_path,
            "extract_path":    self.extract_path,
            "config_path":     self.config_path,
            "config_file_path": self.config_file_path,
            "logs_path":       self.logs_path,
            "archived_path":   self.archived_path,
            "backlog_path":    self.backlog_path,
            "debug_path":      self.debug_path,
            "backend_path":    self.backend_path,
        }
        all_exist = True
        for name, path in all_paths.items():
            if not path.exists():
                logging.critical(f"Missing path: {name} -> {path}")
                all_exist = False
        return all_exist
