import warnings
from pathlib import Path
import logging
import os

def long_path(anypath:Path, path_length_thresh=0)->Path:
    # converts paths to \\?\ to support long paths
    normalized = os.fspath(anypath.resolve())
    if len(normalized) > path_length_thresh:
        if not normalized.startswith('\\\\?\\'):
            normalized = '\\\\?\\' + normalized
        return Path(normalized)
    return anypath

class PATHS_OBJ:
    # ----------------- INPUT PATH HERE -----------------
    base_path = Path(r"C:\Users\WYBT00P\OneDrive - Volkswagen AG\C48 Test data #2 - 02_CPA_DataBase\x_DataHandling\B2-2_sample")

    base_path = long_path(base_path)

    # ----------------- DO NOT CHANGE FOLDER TEMPLATE -----------
    dump_path = base_path / "01_Incoming_Compressed_Files"
    extract_path = base_path / "02_Extracted_Raw_Files"

    harmonized_path = base_path / "03_Harmonized_Data"
    config_path = base_path / "05_Configuration"
    config_file_path = base_path / "05_Configuration" / "format_config.yaml"
    ETL_config_path = base_path / "05_Configuration" / "supplier_data_ETL_config.xlsx"
    logs_path = base_path / "06_Logs"
    archived_path = base_path / "07_Archived"
    backlog_path = base_path / "08_Backlog"

    # additional variables or initialization
    debug_path = logs_path / "debug_logs"
    backend_path = logs_path / "backend_base"
    debug_path.mkdir(parents=False, exist_ok=True)
    backend_path.mkdir(parents=False, exist_ok=True)

    copy_action =  'skip_copy' # ['replace', 'create_copy', 'skip_copy'] - only applicable if files are exact match
    #-------------------------------------------------------------

    def check_if_exists(self)->bool:


        all_paths = {
            "dump_path": self.dump_path,
            "extract_path": self.extract_path,
            "config_path": self.config_path,
            "config_file_path": self.config_file_path,
            "logs_path": self.logs_path,
            "archived_path": self.archived_path,
            "backlog_path": self.backlog_path,
            "debug_path": self.debug_path,
            "backend_path": self.backend_path,
        }


        all_exist = True
        for name, path in all_paths.items():
            if not path.exists():
                logging.critical(f"Missing path: {name} -> {path}")
                all_exist = False

        return all_exist

#r"\\volkswagengroup.sharepoint.com@SSL\DavWWWRoot\sites\C48T\Shared Documents\General\03_Testing_Database