# initialise
import logging

import winsound

from src.dependencies import *
from src.paths import PATHS_OBJ
from src.extract_archive import *
from src.clear_backlog import *
from src.file_handling import *
from src.consistency_check import *
import warnings

PATHS_OBJ = PATHS_OBJ()

base_path = PATHS_OBJ.base_path
dump_path = PATHS_OBJ.dump_path
extract_path = PATHS_OBJ.extract_path
config_path = PATHS_OBJ.config_path
config_file_path = PATHS_OBJ.config_file_path
logs_path = PATHS_OBJ.logs_path
backlog_path = PATHS_OBJ.backlog_path
debug_path = PATHS_OBJ.debug_path
backend_path = PATHS_OBJ.backend_path
archived_path = PATHS_OBJ.archived_path

copy_action = PATHS_OBJ.copy_action

# additional variables or initialization
timestr = time.strftime("%Y%m%d_%H%M%S")

# Run on specific zip files only
ZIP_FILES = None#["Peak"] # else use None

# Configure logging
logging.basicConfig(filename=debug_path / "debug_logfile.log",  # Log file name
                    level=logging.DEBUG,  # Minimum level to log
                    format='%(asctime)s - %(levelname)s - %(message)s'
                    )

logging.info(f"\n ---------------------------------- New run -------------------------------------- \n ")
if ZIP_FILES:
    logging.warning(f"ZIP Files filtering by substrings is active : {ZIP_FILES}")
USER_STOPS = False #if true it would ask for user input whether to continue after each significant step

# check if backlog folder is empty to proceed
# This code forces user to clear backlog before proceeding next one, also avoids duplicates of zip extracts
if count_files_in_folder(backlog_path) > 0:
    logging.critical(f"Please Work on Backlog & Clear it to proceed")
    warnings.warn('\033[91m'+f"Please work on Backlog files to proceed: \n >> {backlog_path}"+'\033[0m', UserWarning)
elif PATHS_OBJ.check_if_exists() is False:
    logging.info(f"Please correct the Folder structure & config file")
    warnings.warn('\033[91m'+f"Please correct Folder structure & config file to proceed: \n >> {base_path}"+'\033[0m', UserWarning)
else:
    # main run starts here:
    archives_dict = detect_archive(dump_path, recursive=True, include_substrings=ZIP_FILES)
    # extract archive files as per config & copy them to right folder
    extract_status_dict = main_extract_archives(archives_dict['TestedArchives'], out_dir=extract_path,
                                                backlog_dir= backlog_path, config_path=config_file_path)

    # copies the files into respective cell folders and it doesn't overwrite if destination has same file already
    if (USER_STOPS):
        user_input = input("Files extracted. Press Enter to continue with copying or type 'q' to quit: ").strip().lower()
        if (user_input == 'q'):
            log_summary(overall_status_dict=extract_status_dict)
            logging.debug('Process aborted before copying files')
            sys.exit(0)
    main_status_dict = copy_files_matching_id(extract_status_dict, out_dir=extract_path,
                                                         copy_action=copy_action)
    # check if copied files are of right size then remove
    time.sleep(1)
    gc.collect() # garbage collect to release memory resources

    if (USER_STOPS):
        user_input = input("Files copied. Press Enter to continue to clear backlog or type 'q' to quit: ").strip().lower()
        if (user_input == 'q') & (USER_STOPS):
            log_summary(overall_status_dict=main_status_dict)
            logging.warning('Process aborted before clearing backlog')
            sys.exit(0)

    main_status_dict = clear_backlog_after_copy(main_status_dict, backlog_path=backlog_path)
    #main_status_dict = retry_removing_copied_files(main_status_dict, backlog_path=backlog_path)



    if (USER_STOPS):
        user_input = input(
            "Files copied. Press Enter to continue to move archive or type 'q' to quit: ").strip().lower()
        if (user_input == 'q') & (USER_STOPS):
            user_input2 = input(
                "Warning: Do you want to abort now, files are copied, cannot reverse that, type 'quit' to quit, any other key to 'continue'").strip().lower()
            if user_input2 == 'quit':
                log_summary(overall_status_dict=main_status_dict)
                logging.critical('Process aborted before moving archive')
                sys.exit(0)

    # move archive files to archived folder from incoming compressed folder, if all files are copied without exceptions
    try:
        main_status_dict = move_archive(input_status_dict=main_status_dict, destination_dir=archived_path)
    except Exception as e:
        logging.critical(f"Error while running move_archive() function: contact admin")
        logging.debug(f"Debug message: {e}")

    with open(backend_path/ (timestr+"_status.json"), "w") as jf:
        json.dump(main_status_dict, jf, indent=4)

    log_summary(overall_status_dict=main_status_dict)
    try:
        append_status_to_excel(status_dict=main_status_dict, logs_path=logs_path, backend_path=backend_path)
    except Exception as e:
        logging.critical(f"Error while running append_status_to_excel() function: contact admin")
        logging.debug(f"Debug message: {e}")

    #file_consistency_check(backend_path=backend_path, extract_path=extract_path)

print("Finished main() run. Refer further in log files.")
logging.info("\n-------------------------------- End Of main() -----------------------------------------\n")
finished_tone()

'''
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
extracted_files_paths = list(extract_path.rglob('*.*'))

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
            logging.warning(f"No matching config for {file_path}")

# additional variables or initialization
timestr = time.strftime("%Y%m%d_%H%M%S")
with open(backend_path/ ("hm_"+timestr+"_status.json"), "w") as jf:
    json.dump(hm_status_dict, jf, indent=4)


logging.info(f"\n ----------- END OF RUN ----------- \n")
logging.shutdown()

'''