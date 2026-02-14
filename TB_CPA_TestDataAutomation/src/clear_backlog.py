import pandas as pd

from .dependencies import *
from .extract_archive import *
from .file_handling import *



def remove_empty_dirs(path: Path) -> None:
    '''
    # recursive function to call the end of tree & remove all empty folders only
    '''
    for sub in path.iterdir():
        if sub.is_dir():
            remove_empty_dirs(sub)

    # Remove the directory if it's empty
    if path.is_dir() and not any(path.iterdir()):
        try:
            path.rmdir()
        except Exception as e:
            logging.warning(f"Try to Delete Manually: Failed to remove empty folder <{path}> in backlog")
            logging.debug(f"Remove empty folder: <{e}>")
    return None

def clear_backlog_after_copy(overall_status_dict: dict, backlog_path: Path) -> dict:
    '''
    Clears backlog file duplicates after checking if files are copied to their respective folders
    :parameters:
        overall_status_dict: output from main_extract_archives()
    :return:
        modified overall_status_dict
    '''

    logging.info(f"\n<<<<<<<<<<<<<< Clearing backlog >>>>>>>>>>>>>>\n")

    for archive_path in overall_status_dict.keys():
        success_rem = []
        failure_rem = []
        not_same_rem = []
        not_compared = []
        failure_ignore_rem = []
        overall_status_dict[archive_path]['backlog_meta'] = {}

        for file_path in overall_status_dict[archive_path]["copied_files_meta"]:
            dest_path = Path(overall_status_dict[archive_path]["copied_files_meta"][file_path]['destination_file'])
            file_path = Path(file_path)
            if file_path.exists():
                # check if file in backlog and destination are same size & naming
                if compare_files_shallow(src_file=file_path, dest_file=dest_path):
                    #try to remove the file in backlog
                    if backlog_path in Path(file_path).parents:
                        try:
                            #os.remove(file_path)
                            file_path.unlink(missing_ok=False)
                            time.sleep(0.1)
                            success_rem.append(str(file_path))
                            logging.info(f"Removed file <{file_path.name}> from <{file_path.parent.stem}> from backlog")
                        except:
                            try:
                                logging.info(f"Shutil failed to remove file, trying os.remove(): <{file_path.name}>")
                                gc.collect()
                                os.remove(file_path)
                                time.sleep(0.1)
                            except Exception as e:
                                failure_rem.append(str(file_path))
                                logging.warning(f"Failed to delete already copied backlog file <{file_path.name}>, try post_run()")
                                logging.debug(f"Failed to delete Debug message: <{e}>")
                else:
                    not_same_rem.append(str(file_path))
                    logging.critical(f"Exception found: Matching file not found <{file_path.name}> and <{dest_path.name}>")
                    logging.warning("Unknown exception: Contact owner to Debug, Check log file")
            else:
                logging.debug(f"Exception found: <{file_path.name}> is missing in backlog before clearing, but already copied to <{dest_path.name}>")
                not_compared.append(str(file_path))
        # create log in status_dict for tracking
        overall_status_dict[archive_path]['backlog_meta']['cleared_in_backlog'] = success_rem
        overall_status_dict[archive_path]['backlog_meta']['failed_to_remove_copied_file'] = failure_rem
        overall_status_dict[archive_path]['backlog_meta']['mismatch_destination_file'] = not_same_rem
        overall_status_dict[archive_path]['backlog_meta']['src_not_avail'] = not_compared
        overall_status_dict[archive_path]['backlog_meta']['ignored_files_in_backlog'] = copy.deepcopy(
                                                                overall_status_dict[archive_path]["to_ignore"]["names"])
        if (len(failure_rem)+len(not_same_rem))>0:
            logging.info(f"Failed to delete <{len(failure_rem)}> in backlog for <{Path(archive_path).stem}>")
            logging.info(f"Failed to find copy of <{len(not_same_rem)}> files in extracted path")
            logging.debug(f"Manually check backlog for <temp_extract_{Path(archive_path).stem}>")
        #------------------------------------------------------------------------
        # Remove ignored files in backlog folder (includes splitted_ignore files)
        for ignored_file in overall_status_dict[archive_path]["to_ignore"]["names"]:
            ignored_file = Path(ignored_file)
            # try to remove the file in backlog
            if backlog_path in Path(ignored_file).parents:
                try:
                    ignored_file.unlink(missing_ok=False)
                    time.sleep(0.1)
                except:
                    try:
                        gc.collect()
                        os.remove(ignored_file)
                        time.sleep(0.1)
                    except Exception as e:
                        failure_ignore_rem.append(str(ignored_file))
                        logging.warning(f"Failed to delete ignored backlog file <{ignored_file.name}>: Try to delete manually")
                        logging.debug(f"Failed to delete Debug message: <{e}>")
        overall_status_dict[archive_path]['backlog_meta']['failed_remove_ignored_files'] = failure_ignore_rem
    gc.collect() # garbage collect to release memory resources
    logging.info(f"Removing empty folders in backlog")
    try:
        remove_empty_dirs(backlog_path)
    except Exception as e:
        logging.warning(f"Failed to remove empty folders in backlog")
        logging.debug(f"Debug message: <{e}>")
    return overall_status_dict

def retry_removing_copied_files(input_status_dict: dict, backlog_path: Path)->dict:
    overall_status_dict = copy.deepcopy(input_status_dict)
    cnt_rem = 0
    for archive_path in overall_status_dict.keys():
        if len(overall_status_dict[archive_path]['backlog_meta']['failed_to_remove_copied_file'])>0:
            logging.info(f"Retrying to remove "
                         f"<{len(overall_status_dict[archive_path]['backlog_meta']['failed_to_remove_copied_file'])}> "
                         f"files in backlog")
            success_rem = copy.deepcopy(overall_status_dict[archive_path]['backlog_meta']['cleared_in_backlog'])
            failure_rem = copy.deepcopy(overall_status_dict[archive_path]['backlog_meta']['failed_to_remove_copied_file'])
            for file_path in overall_status_dict[archive_path]['backlog_meta']['failed_to_remove_copied_file']:
                if backlog_path in Path(file_path).parents: # to ensure we delete file only from backlog
                    try:
                        gc.collect()
                        os.remove(file_path)
                        logging.info(f"Removed already copied file <{Path(file_path).name}> in backlog")
                        success_rem.append(file_path)
                        failure_rem.remove(file_path)
                    except:
                        if not Path(file_path).exists():
                            # when file is not there any more, it could be deleted manually, so it is acceptable
                            success_rem.append(file_path)
                            failure_rem.remove(file_path)
                        else:
                            logging.warning(f"Try Deleting Manually: Failed attempt to remove copied backlog file: \n<{file_path}>")
                        # try:
                        #     gc.collect()
                        #     file_path.unlink(missing_ok=False)
                        #     logging.info(f"Removed already copied file <{Path(file_path).name}> in backlog")
                        #     success_rem.append(file_path)
                        #     failure_rem.remove(file_path)
                        # except:
                        #     if not Path(file_path).exists():
                        #         success_rem.remove(file_path)
                        #         failure_rem.append(file_path)
                        #     else:
                        #         logging.warning(f"Try Deleting Manually: Failed attempt to remove copied backlog file: \n<{file_path}>")

            overall_status_dict[archive_path]['backlog_meta']['cleared_in_backlog'] = success_rem
            overall_status_dict[archive_path]['backlog_meta']['failed_to_remove_copied_file'] = failure_rem
            cnt_rem = cnt_rem + len(failure_rem)

    try:
        remove_empty_dirs(backlog_path)
    except Exception as e:
        logging.warning(f"Failed to remove empty folders in backlog")
        logging.debug(f"Debug message: <{e}>")

    if cnt_rem > 0:
        logging.info(f"Failed to remove <{cnt_rem}> files in backlog, try re-run post_run() after restarting python or manually delete")
    else:
        logging.info(f"Successfully removed all copied files in backlog")

    files_left = []
    for root, dirs, files in os.walk(backlog_path):
        files_left.append(files)
    files_left = [i for i in flatten_list(files_left) if '.ini' not in i]

    if len(files_left) > 0:
        logging.warning(f"Found {len(files_left)} files to be cleared manually in backlog: \n {files_left}")

    try:
        remove_empty_dirs(backlog_path)
    except Exception as e:
        logging.warning(f"Failed to remove empty folders in backlog")
        logging.debug(f"Debug message: <{e}>")

    return overall_status_dict

def log_summary(overall_status_dict:dict) -> None:
    logging.info("\n*************** Logging Summary ***************")

    status_dict = copy.deepcopy(overall_status_dict)
    log_df = pd.DataFrame([])

    temp = defaultdict(dict)
    for archive_path in overall_status_dict.keys():

        name = Path(archive_path).name
        #name = "{:.35}".format(name) + '...' if len(name) > 15 else name #truncate name if long
        temp[name]['#files'] = len(overall_status_dict[archive_path]['all_files']['names']) # after extract
        temp[name]['tocopy'] = len(overall_status_dict[archive_path]['to_copy']['post_split_meta'].keys()) # post split
        temp[name]['copied'] = len(overall_status_dict[archive_path]['copied_files_meta'].keys())
        temp[name]['splitted'] = len(overall_status_dict[archive_path]['to_copy']['splitting_info'].keys())  # post split
        temp[name]['unknown'] = len(overall_status_dict[archive_path]['unknown']['names'])
        temp[name]['ignored'] = len(overall_status_dict[archive_path]['to_ignore']['names'])
        temp[name]['corrupt'] = len(overall_status_dict[archive_path]['corrupted']['names'])
        temp[name]['08_mismatch'] = len(
            overall_status_dict[archive_path]['backlog_meta']['mismatch_destination_file'])
        temp[name]['08_fail_del'] = len(
            overall_status_dict[archive_path]['backlog_meta']['mismatch_destination_file'])
        temp[name]['08_src_miss'] = len(overall_status_dict[archive_path]['backlog_meta']['src_not_avail'])
        temp[name]['08_cleared'] = len(
            overall_status_dict[archive_path]['backlog_meta']['cleared_in_backlog'])

    log_df = pd.DataFrame.from_dict(temp).T
    log_df.reset_index(inplace=True)
    index_col = log_df.pop('index')  # Remove the index column
    log_df['Archive Name'] = index_col
    log_df.loc['Sum'] = log_df.sum(axis=0, skipna=True, numeric_only=True)

    logging.info(f"\n{tabulate(log_df, headers='keys', tablefmt='grid', showindex=True)}")

    logging.info("\n***********************************************")
    return None

def finished_tone():
    notes = [
        (500, 200),(650, 200), (800, 200),(650, 200),(800, 200), (650, 200),(500,200)]
    for freq, dur in notes:
        winsound.Beep(freq, dur)
        time.sleep(0.05)  # Short pause between notes