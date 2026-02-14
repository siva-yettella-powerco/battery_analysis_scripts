import logging

from src.dependencies import *
from harmonize.hm_supplier_config import detect_supplier
from harmonize.hm_import_data import *
from harmonize.supplier_support_func.hm_general_support import *
from src.paths import PATHS_OBJ

# -------------------- Initialise paths --------------------------------
base_path = PATHS_OBJ.base_path
dump_path = PATHS_OBJ.dump_path
extract_path = PATHS_OBJ.extract_path
harmonized_folder = PATHS_OBJ.harmonized_path
config_path = PATHS_OBJ.config_path
config_file_path = PATHS_OBJ.config_file_path
logs_path = PATHS_OBJ.logs_path
backlog_path = PATHS_OBJ.backlog_path
debug_path = PATHS_OBJ.debug_path
backend_path = PATHS_OBJ.backend_path

etl_config_path = PATHS_OBJ.ETL_config_path
etl_df = pd.read_excel(etl_config_path,sheet_name='config')