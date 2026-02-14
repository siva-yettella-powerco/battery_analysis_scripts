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

# --------------------------- RUN PARAM ----------------------------
''' !! WARNING :: PLEASE CHECK THE BASE PATH BEFORE RUNNING !! '''

sz_data_path = Path(r"//vw.vwg/vwdfs/PowerCo/Salzgitter/0560-datashare/02_RawData/096/096_006_P/")
Chosen_CellIDs = ["096_006_P_019", "096_006_P_020", "096_006_P_021"]


hm_skip_rerun = True
hm_skip_rerun_except_ids = [] #leave it [] for no exceptions, these cells will be rerun
hm_copy_action =  'skip_copy' # ['replace', 'create_copy', 'skip_copy'] only valid for not skipped cells
#------------------------------LOG----------------------------------------

# Configure logging
logging.basicConfig(filename=debug_path/"debug_logfile.log", # Log file name
                    level=logging.DEBUG, # Minimum level to log
                    format='%(asctime)s - %(levelname)s - %(message)s'
                    )
logging.info(f"\n >>>>>>>>>> Running harmonize() <<<<<<<<<<< \n")

logging.info(f"Note: Skip Rerun is {hm_skip_rerun}, Copy action is {hm_copy_action}\n, "
             f"Rerun active on cells: {hm_skip_rerun_except_ids}")

hm_status_dict = defaultdict(dict)

#---------------------------Harmonize data-----------------------------------

# Find all files and get supplier name and method based on file name #
extracted_files_paths = list(sz_data_path.rglob('*dyn*.csv'))
extracted_files_paths = [file for file in extracted_files_paths if file.parent.stem in Chosen_CellIDs]

# logging.warning('Running on selected cells only:')
# extracted_files_paths = [i for i in extracted_files_paths if (i.parent.stem in ['GOT0006','GOT0009','GOT0015',
#                                                                                 'GOT0045','GOT0072','GOT0144',
#                                                                                 'GOT0160','GOT0006','GOT0009',
#                                                 'GOT0014','GOT0058','GOT0132']) & (i.suffix.lower() == '.xls')]
# logging info to show how many cells are to be harmonized
try:
    skip_samples = len([file_path for file_path in extracted_files_paths if
                        ((Path(harmonized_folder / file_path.parent.stem / (file_path.stem + '.csv')).exists() and
                          hm_skip_rerun) and (file_path.parent.stem not in hm_skip_rerun_except_ids))])
    logging.info(f"Detected {len(extracted_files_paths)} extracted files and {len(skip_samples)} samples skipped")
except:
    logging.info(f"Detected {len(extracted_files_paths)} extracted files")

# start of harmonization
for file_path in extracted_files_paths:

    if ((Path(harmonized_folder / file_path.parent.stem / (file_path.stem + '.csv')).exists() and hm_skip_rerun) and
            (file_path.parent.stem not in hm_skip_rerun_except_ids)):
        continue
    else:
        file_id = str(file_path)
        # Find matching configuration for the file, given the supplier_config file excel
        config_match_name, hm_status_dict = find_matching_config(file_path=file_path,etl_df=etl_df,
                                                                 hm_status_dict=hm_status_dict)

        if config_match_name is not None:
            # Run the matching config on data
            try:
                # Get harmonized data file
                harmonized_data, hm_status_dict = run_harmonize_with_config(file_path=file_path,etl_df=etl_df,
                                        hm_status_dict=hm_status_dict, config_name = config_match_name)

                # export to harmonized folder
                if harmonized_data.shape[0]>0:
                    export_file_path = export_to_harmonized_folder(file_path=file_path, harmonized_data=harmonized_data,
                                                harmonized_folder=harmonized_folder,
                                                copy_action=hm_copy_action)
                    hm_status_dict[file_id]['Harmonized_file'] = str(export_file_path)
                    logging.info(f"Harmonized data saved to {export_file_path.name}")
                else:
                    logging.warning(f'Empty Table after run harmonize() in {file_path.name}')
            except Exception as e:
                logging.error(f'Could not run harmonize() on file {file_path.name} {e}')
                hm_status_dict[file_id]['Harmonized_file'] = None
        else:
            logging.warning(f"No matching config for {file_path}, check detect_supplier() function")

# additional variables or initialization
timestr = time.strftime("%Y%m%d_%H%M%S")
with open(backend_path/ ("hm_"+timestr+"_status.json"), "w") as jf:
    json.dump(hm_status_dict, jf, indent=4)


logging.info(f"\n ----------- END OF RUN ----------- \n")
logging.shutdown()