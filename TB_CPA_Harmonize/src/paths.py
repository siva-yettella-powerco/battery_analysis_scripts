import warnings
from pathlib import Path
import logging
import os

def long_path(anypath: Path, path_length_thresh=0) -> Path:
    # converts paths to \\?\ to support long paths
    normalized = os.fspath(anypath.resolve())
    if len(normalized) > path_length_thresh:
        if not normalized.startswith('\\\\?\\'):
            normalized = '\\\\?\\' + normalized
        return Path(normalized)
    return anypath

_DEFAULT_BASE_PATH = Path(r"C:\Users\WYBT00P\OneDrive - Volkswagen AG\C48 Test data #2 - 02_CPA_DataBase\x_DataHandling\B2-2_sample")

class PATHS_OBJ:
    # v1.2: base_path is now injectable via __init__ instead of hard-coded class attribute
    def __init__(self, base_path: Path = None):
        if base_path is None:
            base_path = _DEFAULT_BASE_PATH

        self.base_path = long_path(Path(base_path))

        # ----------------- DO NOT CHANGE FOLDER TEMPLATE -----------
        self.dump_path        = self.base_path / "01_Incoming_Compressed_Files"
        self.extract_path     = self.base_path / "02_Extracted_Raw_Files"
        self.harmonized_path  = self.base_path / "03_Harmonized_Data"
        self.config_path      = self.base_path / "05_Configuration"
        self.config_file_path = self.base_path / "05_Configuration" / "format_config.yaml"
        self.ETL_config_path  = self.base_path / "05_Configuration" / "supplier_data_ETL_config.xlsx"
        self.logs_path        = self.base_path / "06_Logs"
        self.archived_path    = self.base_path / "07_Archived"
        self.backlog_path     = self.base_path / "08_Backlog"

        # additional paths
        self.debug_path   = self.logs_path / "debug_logs"
        self.backend_path = self.logs_path / "backend_base"
        self.debug_path.mkdir(parents=False, exist_ok=True)
        self.backend_path.mkdir(parents=False, exist_ok=True)

        self.copy_action = 'skip_copy'  # ['replace', 'create_copy', 'skip_copy']
        #-------------------------------------------------------------

    def check_if_exists(self) -> bool:
        all_paths = {
            "extract_path":    self.extract_path,
            "harmonized_path": self.harmonized_path,
            "config_path":     self.config_path,
            "ETL_config_path": self.ETL_config_path,
            "logs_path":       self.logs_path,
            "debug_path":      self.debug_path,
            "backend_path":    self.backend_path,
        }

        all_exist = True
        for name, path in all_paths.items():
            if not path.exists():
                logging.critical(f"Missing path: {name} -> {path}")
                all_exist = False

        return all_exist
