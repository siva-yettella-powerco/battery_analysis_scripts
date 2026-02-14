from src.dependencies import *
from src.paths import PATHS_OBJ
from src.extract_archive import *
from src.clear_backlog import *
from src.file_handling import *

# -------------------- Initialise paths --------------------------------

base_path = PATHS_OBJ.base_path
dump_path = PATHS_OBJ.dump_path
extract_path = PATHS_OBJ.extract_path
config_path = PATHS_OBJ.config_path
config_file_path = PATHS_OBJ.config_file_path
logs_path = PATHS_OBJ.logs_path
backlog_path = PATHS_OBJ.backlog_path
debug_path = PATHS_OBJ.debug_path
backend_path = PATHS_OBJ.backend_path

# Configure logging
logging.basicConfig(filename=debug_path/"debug_logfile.log", # Log file name
                    level=logging.DEBUG, # Minimum level to log
                    format='%(asctime)s - %(levelname)s - %(message)s'
                    )

# -------------- removing already copied files from backlog ------------------
# load the latest json file
logging.info(f"\n >>>>>>>>>> Running post_run() <<<<<<<<<<< \n")
latest_json = find_latest_file_in_folder(backend_path, suffix='*.json')

gc.collect()
with open(latest_json, 'r', encoding='utf-8') as f:
    status_data = json.load(f)
new_status_data = retry_removing_copied_files(input_status_dict = status_data, backlog_path=backlog_path)

if new_status_data != status_data:
    # save the updated .json file
    with open(latest_json, "w") as jf:
        json.dump(new_status_data, jf, indent=4)
# -----------------------------------------------------------------------------

logging.shutdown()