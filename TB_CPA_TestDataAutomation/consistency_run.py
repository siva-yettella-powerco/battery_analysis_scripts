from src.consistency_check import *
from src.paths import PATHS_OBJ

backend_path = PATHS_OBJ.backend_path
extract_path = PATHS_OBJ.extract_path
debug_path = PATHS_OBJ.debug_path

# Configure logging
logging.basicConfig(filename=debug_path / "debug_logfile.log",  # Log file name
                    level=logging.DEBUG,  # Minimum level to log
                    format='%(asctime)s - %(levelname)s - %(message)s'
                    )


consistency_dict = file_consistency_check(backend_path=backend_path, extract_path=extract_path)