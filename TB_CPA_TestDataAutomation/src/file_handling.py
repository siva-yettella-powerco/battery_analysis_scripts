from .dependencies import *
from .extract_archive import *
from .clear_backlog import *

'''
# Code notes:
#     > all paths input or output are handled as strings inside dictionaries or dataframes
#     > all paths are handled as pathlib.Path and not strings inside function for robustness
'''

# %%
def count_files_in_folder(folder_path: Path) -> int:
    cnt = 0
    all_files = list(folder_path.rglob("*"))
    for f in all_files:
        if f.is_file() & (f.suffix.lower() not in ['.ini','.lnk','.tmp']):
            cnt += 1
    return cnt


def load_config(config_path: Path) -> dict:
    '''
    loads the config file into dictionary
    Parameters:
    -----------
    config_path is the path to yaml config file for the sample stage
    :return: dictionary object with config information
    '''
    config_dict = defaultdict()
    try:
        logging.info(f"Running load_config: <{config_path.name}>")
        with open(config_path, 'r') as config_file:
            config = yaml.safe_load(config_file)
        config_dict['format_include'] = list(config["RawDataHandling"]["format_to_import"].keys())
        config_dict['meta_include'] = config["RawDataHandling"]["format_to_import"]
        config_dict['format_exclude'] = list(config["RawDataHandling"]["format_to_ignore"].keys())
        config_dict['meta_exclude'] = config["RawDataHandling"]["format_to_ignore"]
    except Exception as e:
        logging.critical(f"Failed to load config file <{config_path}>")
        logging.debug(f"Failed configload: {e}")

    return config_dict


def filter_files_byConfig(extracted_folder: Path, config_dict: dict) -> dict:
    '''
    finds which files are matching with configuration requirements to include or exclude for a single archive
    :param extracted_folder: folder path to extracted files (same as temp folder)
    :param config_dict: (configuration dict from load_config())
    :return: dictionary of list of file paths to copy or ignored based on configuration
    '''

    file_paths = defaultdict(dict)
    file_paths['all_files'] = {}
    file_paths['to_copy'] = {}
    file_paths['to_ignore'] = {}
    file_paths['unknown'] = {}
    file_paths['corrupted'] = {} #only filled in split_files_by_config()

    extracted_folder = Path(extracted_folder)
    # listed all possible files -> recursive search
    all_files = [p for p in extracted_folder.rglob("*") if
                 (p.is_file() and (p.suffix.lower() not in ['.ini','.lnk','.tmp']))]

    # listed if any file matches the config include format
    include_files = [p for p in all_files if
                     any([fnmatch.fnmatch(p.name, pattern) for pattern in config_dict['format_include']])]
    print([p.name for p in all_files if
                     any([fnmatch.fnmatch(p.name, pattern) for pattern in config_dict['format_include']])])
    # listed if any file matches with exclude format
    exclude_files = [p for p in include_files if
                     any([fnmatch.fnmatch(p.name, pattern) for pattern in config_dict['format_exclude']])]
    to_copy_files = [i for i in include_files if i not in set(exclude_files)]
    #files which are neither in include or exclude - happens if config doesnt consider all files
    unknown_files = [i for i in all_files if i not in set(include_files+exclude_files)]

    if len(unknown_files) > 0:
        logging.critical(f"These files doesn't match config include or exclude formats: \n{unknown_files}")
        logging.debug(f"Extracted in folder: \n{str(extracted_folder)}")

    # config.yaml meta is attached to the names,
    # the reason to separate names and meta is if multiple patterns match then it is easier to deal later
    file_paths['all_files']['names'] = [str(i) for i in all_files]
    file_paths['to_copy']['meta'] = {str(i):config_dict['meta_include'][pattern] for i in to_copy_files
                                     for pattern in config_dict['format_include']
                                     if fnmatch.fnmatch(i.name, pattern)}
    ''' only for debug '''
    if len(file_paths['to_copy']['meta'].keys()) < len(all_files)-1:
        logging.debug(f"Found exception files in folder: {extracted_folder.stem}"
                      f"\n to_copy_files variable: {to_copy_files}\n"
                      f"\n exclude_files variable: {exclude_files}\n"
                      f"\n include_files variable: {include_files}\n")

    ''''''
    file_paths['to_ignore']['names'] = [str(i) for i in exclude_files]
    file_paths['unknown']['names'] = [str(i) for i in unknown_files]

    return file_paths


def split_excel_by_data_sheets(input_file:str, output_dir:str, sheet_prefix:str ='RecordInfo') -> tuple[str, list[str], bool]:
    """
        Behavior:
        ---------
        - Identifies all sheets in the input Excel file.
        - Filters sheets whose names start with the given prefix.
        - For each data-related sheet, creates a new Excel file:
        - Saves the new files in the specified output directory.

        Parameters:
        -----------
        input_file : str or Path
            Path to the input Excel file.
        output_dir : str or Path
            Directory where the output Excel files will be saved.
        sheet_prefix : str, optional
            Prefix used to identify data-related sheets
        output :
        ----------
        dictionary of input file name after rename as key and splitted files names as value
        """
    splitted_file_names = [] # list of splitted files names
    input_file = Path(input_file)
    output_dir = Path(output_dir)
    corrupted_flg = False
    # Load the Excel file
    if input_file.is_file():
        try:
            excel = pd.ExcelFile(input_file, engine='openpyxl')
        except Exception as e:
            corrupted_flg = True
            logging.critical(f"Failed to load excel file: <{input_file.name}> is possibly corrupted")
            return (str(input_file), splitted_file_names, corrupted_flg)
    else:
        logging.critical(f"Failed to find file in path: <{input_file}>,\n hence moved the file_path to corrupted")
        corrupted_flg = True
        return (str(input_file), splitted_file_names, corrupted_flg)
    all_sheet_names = excel.sheet_names

    # Identify all data-related sheets using fnmatch
    data_sheets = fnmatch.filter(all_sheet_names, sheet_prefix + '*')
    other_sheets = list(set(all_sheet_names)-set(data_sheets))

    # Create output directory
    if not output_dir.is_dir():
        output_dir.mkdir(parents=False, exist_ok=True)

    # Generate new Excel files
    if len(data_sheets) > 1:
        logging.info(f"Running split excel on <{Path(input_file).name}> into <{len(data_sheets)}>"
                     f" Excel files, parts are exported to <{output_dir}>")
        for i, data_sheet in enumerate(data_sheets):
            out_name = Path(input_file).stem+f'_part{i+1}.xlsx'
            output_file = output_dir / out_name

            # Read all sheets at once
            sheets_to_read = other_sheets + [data_sheet]
            temp_df = pd.read_excel(excel, sheet_name=sheets_to_read, engine='openpyxl')

            with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
                # Write other sheets
                for sheet in other_sheets:
                    temp_df[sheet].to_excel(writer, sheet_name=sheet, index=False)
                # Write the data sheet with a new name
                temp_df[data_sheet].to_excel(writer, sheet_name=sheet_prefix, index=False)
            splitted_file_names.append(str(output_file)) #apend to splitted file names

        # rename input file that it is splitted
        excel.close()
        modified_filename = input_file.with_name(input_file.stem + '_splittedfile_Ignore' + input_file.suffix)
        try:
            if not modified_filename.exists():
                input_file.rename(modified_filename)
                return (str(modified_filename), splitted_file_names, corrupted_flg)
        except Exception as e:
            logging.warning(f"Failed to rename splitted file: <{input_file.name}> to <{modified_filename.name}>")
            logging.debug(f"Debug info for renaming: {e}")

    return (str(input_file), splitted_file_names, corrupted_flg)

def check_csv_corruption(file_path:Path)->bool:
    try:
        df = pd.read_csv(file_path)
        corrupted_flg = False
    except Exception as e:
        corrupted_flg = True
        logging.warning(f"Failed to load .csv file: {file_path.name}")
        logging.debug(f"Debug message {e}")
    return corrupted_flg


def split_files_by_config(filtered_files: dict) -> dict:
    '''
    In some excels, the large data is split into multiple sheets with numeric suffix
    This function is to split sheets into new files & keep sheet name consistent
    Parameters:
    -----------
        filtered_files - list of paths to excel files (output of filter_files_byConfig()), which includes meta from config
    Returns:
        updated filtered_files - list of paths to excel files after splitting (adds the file splitted to "to_ignore")
    '''

    filtered_files01 = copy.deepcopy(filtered_files)
    filtered_files01['to_copy']['post_split_meta'] = {}
    filtered_files01['to_copy']['splitting_info'] = {}
    filtered_files01['corrupted']['names'] = []
    for filepath in filtered_files01['to_copy']['meta'].keys():
        file_meta = filtered_files01['to_copy']['meta'][filepath]
        corrupt_flg = False
        act_filepath = filepath
        split_filepaths = []
    # check if the file is excel
        if Path(filepath).suffix in [".xls",".xlsx", ".xlsm", ".xlsb", ".odf", ".ods", ".XLS"]:
            # check config if splitting excel data sheets is needed
            if file_meta['split_datasheets']:
                try:
                    act_filepath, split_filepaths, corrupt_flg = split_excel_by_data_sheets(input_file=filepath,
                                                           output_dir=str(Path(filepath).parent),
                                                           sheet_prefix = file_meta['datasheet_name'])
                except Exception as e:
                    logging.warning(f"Failed to split excel file: {Path(filepath).name}")
                    logging.debug(f"Debug message: {e}")
                # make a record of splitted files in dictionary format
                if corrupt_flg == True: # represents file corrupted
                    filtered_files01['corrupted']['names'].append(act_filepath)

                elif len(split_filepaths) > 1:
                    filtered_files01['to_copy']['splitting_info'][filepath] = [act_filepath, split_filepaths]
                    for temp in split_filepaths:
                        filtered_files01['to_copy']['post_split_meta'][temp] = file_meta
                    filtered_files01['to_ignore']['names'].append(act_filepath)
                else:
                    filtered_files01['to_copy']['post_split_meta'][filepath] = file_meta
            else:
                filtered_files01['to_copy']['post_split_meta'][filepath] = file_meta

        elif ".csv" in Path(filepath).name:
            if check_csv_corruption(file_path=Path(filepath)):
                logging.warning(f"Found corrupted .csv file: {Path(filepath).name}")
                filtered_files01['corrupted']['names'].append(filepath)
            else:
                filtered_files01['to_copy']['post_split_meta'][filepath] = file_meta
        else:
            logging.warning(f"New file type was configured in .yaml: {Path(filepath).suffix}, which is not checked for corruption "
                            f"please contact admin to avoid issues")
            filtered_files01['to_copy']['post_split_meta'][filepath] = file_meta
    return filtered_files01
    # end of function

def extract_cellid_from_name(filestem:str, prefix:str)->str:
    '''
    # sub function used in extract_unique_cellids()
    # Split at any special character (non-alphanumeric) and identify matching substring with given prefix
    # if filestem = "experiment_cell", prefix = "cell", then just "cell" is returned

    '''
    cellid = prefix
    if prefix in filestem:
        splits = filestem.split(prefix)
        if len(splits)>1:
            cellid = prefix + re.split(r'[^a-zA-Z0-9]+', splits[1])[0]
            substrings = re.split(r'[^a-zA-Z0-9]+', filestem)
        else:
            cellid = prefix
    else:
        logging.warning(f'Failed to extract cellid with prefix: {prefix} in name: {filestem}')
    return cellid

def copy_with_copy_rename(src_file_path:str|Path, dest_folder:str|Path, copy_action:str)-> tuple[Path,bool,str]:
    '''
    subfunction used in copy_files_matching_id()
    copies files to new folder and if file already exists in name, then it makes a numbered copy to avoid overwriting
    but if destination file is also of same size, it uses copy action to choose the action to do

    copy_action: options ['replace','create_copy','skip_copy']
    '''
    src = Path(src_file_path)
    dest_folder = Path(dest_folder)
    dest_file = dest_folder / src.name
    counter = 1
    duplicate_flag = False
    # Auto-rename if file exists
    if dest_file.exists():
        # copy action applied only when size and name are same for files, if size differs we create copy by default
        if compare_files_shallow(src_file=src, dest_file=dest_file):
            duplicate_flag = True
            if 'replace' in copy_action.lower():
                logging.warning(
                    f"Replacing file from {src.name} to {dest_folder} which has same size")
                pass
            elif 'skip_copy' in copy_action.lower():
                logging.warning(
                    f"Skipping file copy from <{src.parent.stem}/{src.name}> to {dest_folder}")
                return dest_file, duplicate_flag, copy_action
            else:
                while dest_file.exists():
                    dest_file = dest_folder / f"{src.stem}_copy{counter}{src.suffix}"
                    counter += 1
        else:
            while dest_file.exists():
                dest_file = dest_folder / f"{src.stem}_copy{counter}{src.suffix}"
                counter += 1
    if not src.exists():
        logging.critical(f"Failed to find src file {src.name} in {src.parent.stem} folder")
    if counter >1:
        logging.warning(f"Duplicate file found of name {src.name}, it is renamed to {dest_file.name} in {dest_folder}")
    #safe_move(src_path = str(src), dest_path = str(dest_file),retries = 3, delay = 1)
    #shutil.copy(src, dest_file)
    # to make sure file is released after copying following with command is used
    with open(src, 'rb') as fsrc, open(dest_file, 'wb') as fdst:
        shutil.copyfileobj(fsrc, fdst)

    return dest_file, duplicate_flag, copy_action

def copy_files_matching_id(filtered_files:dict, out_dir:Path, copy_action:str) -> dict:
    '''
    copy files in the filtered_files['to_copy']['post_split_meta'].keys() to their respective folders
    Parameters:
    ------------
    filtered_files - output from split_files_by_config() function, which includes meta after splitting
    '''
    logging.info(f"\n<<<<<<<<<<<< Copying Files to {out_dir.stem}, copy action: {copy_action} >>>>>>>>>>>>>>>")
    main_status_dict = copy.deepcopy(filtered_files)
    for archive in main_status_dict.keys():
        filtered_files03 = copy.deepcopy(main_status_dict[archive])
        filtered_files03['copied_files_meta'] = {}
        filtered_files03['failed_to_copy_meta'] = {}
         # copy files in respective folders with matching cellid

        for file in filtered_files03['to_copy']['post_split_meta'].keys():

            cellid = extract_cellid_from_name(Path(file).stem, prefix=filtered_files03['to_copy']['post_split_meta'][file]['cellid_prefix'])
            cell_folder = Path(out_dir) / cellid
            cell_folder.mkdir(parents=False, exist_ok=True)
            # copy file to folder if matching
            try:
                file_dest, duplicate_flag, duplicate_act = copy_with_copy_rename(src_file_path=file, dest_folder=cell_folder, copy_action=copy_action)
                filtered_files03['copied_files_meta'][file] = copy.deepcopy(filtered_files03['to_copy']['post_split_meta'][file])
                #filtered_files03['copied_files_meta'][file]['destination_folder'] = str(cell_folder)
                filtered_files03['copied_files_meta'][file]['destination_file'] = str(file_dest)
                filtered_files03['copied_files_meta'][file]['duplicate_flag'] = duplicate_flag
                filtered_files03['copied_files_meta'][file]['duplicate_action'] = duplicate_act
                filtered_files03['copied_files_meta'][file]['cellid'] = cellid
                #logging.debug(f"Copied file: from <{Path(file).name}> to <{Path(file_dest).name}> in <{cell_folder.name}>")
            except Exception as e:
                logging.warning(f"Failed to copy file: <{Path(file).stem}> to <{str(cell_folder)}>")
                logging.debug(f"Debug message: <{e}>")
                filtered_files03['failed_to_copy_meta'][file] = copy.deepcopy(filtered_files03['to_copy']['post_split_meta'][file])
                filtered_files03['failed_to_copy_meta'][file]['destination_file'] = None
                filtered_files03['failed_to_copy_meta'][file]['duplicate_flag'] = None
                filtered_files03['failed_to_copy_meta'][file]['duplicate_action'] = None
                filtered_files03['failed_to_copy_meta'][file]['cellid'] = cellid
        main_status_dict[archive] = filtered_files03
    return main_status_dict

def compare_files_shallow(src_file:Path, dest_file:Path) -> bool:
    '''
    Compare if 2 files are same in size, modified date and name to confirm successful copy
    '''

    if src_file.is_file() and dest_file.is_file():
        # size comparison is in bytes
        if abs(dest_file.stat().st_size - src_file.stat().st_size) <= 10000: #byte difference accepted
            # and ((src_file.stat().st_mtime == dest_file.stat().st_mtime) # check for same modified date
            # incase '_copy' suffix exists for destination file this would still work
            if (src_file.stem in dest_file.stem) and (src_file.suffix == dest_file.suffix):
                return True
    else:
        logging.warning(f"File comparison failed: <{src_file}> or <{dest_file}> is not file")
    return False

def compare_files_bytewise_if_same(src_file:Path, dest_file:Path, size:int = 4096)->bool:
    with open(src_file, 'rb') as f1, open(dest_file, 'rb') as f2:
        while True:
            b1 = f1.read(size)
            b2 = f2.read(size)
            if b1 != b2:
                return False
            if not b1:  # End of file
                return True

def get_file_hash(path:Path, algo='sha256'):
    h = hashlib.new(algo)
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            h.update(chunk)
    return h.hexdigest()

def compare_files_hash_if_same(src_file:Path, dest_file:Path)->bool:

    return get_file_hash(src_file) == get_file_hash(dest_file)

def move_archive(input_status_dict:dict, destination_dir:Path)-> dict:
    '''
    move archive to Archive folder form incoming folder if empty -> "not considered", "failed_to_copy_meta" and
    backlog_meta -> "mismatch_destination_file", "failed_to_remove_copied_file" in status_dict
    '''
    folder_name = time.strftime("%Y-%m_CW%V")
    destination_dir = destination_dir/folder_name
    destination_dir.mkdir(parents=False, exist_ok=True)

    logging.info("\n <<<<<<<<<<<<<< Moving compressed files >>>>>>>>>>>>>>")
    overall_status_dict = copy.deepcopy(input_status_dict)

    for archive in overall_status_dict:
        archive_file_path = Path(archive)
        overall_status_dict[archive]['compressed_file_meta'] = {}
        condition1 = len(overall_status_dict[archive]['unknown']['names'])==0
        condition2 = len(overall_status_dict[archive]['failed_to_copy_meta'].keys())==0
        condition3 = len(overall_status_dict[archive]['backlog_meta']['mismatch_destination_file'])==0
        condition4 = len(overall_status_dict[archive]['corrupted']['names'])==0

        overall_status_dict[archive]['compressed_file_meta']['copied_to_Archived'] = ''
        overall_status_dict[archive]['compressed_file_meta']['can_remove_manually'] = ''
        overall_status_dict[archive]['compressed_file_meta']['yet_to_copy'] = ''
        overall_status_dict[archive]['compressed_file_meta']['exceptions_found'] = ''

        if destination_dir.exists():
            if condition1 and condition2 and condition3 and condition4:
                try:
                    copy_with_copy_rename(src_file_path=archive_file_path, dest_folder=destination_dir, copy_action='create_copy')
                    overall_status_dict[archive]['compressed_file_meta']['copied_to_Archived'] = str(destination_dir / archive_file_path.name)
                    try:
                        gc.collect()
                        archive_file_path.unlink(missing_ok=False)
                    except Exception as e:
                        logging.warning(f"Failed to remove already copied Compressed file: <{archive_file_path.name}>")
                        overall_status_dict[archive]['compressed_file_meta']['can_remove_manually'] = str(archive_file_path)
                except Exception as e:
                    logging.warning(f"Failed to copy file: <{archive_file_path.name}> to <{destination_dir}>")
                    logging.debug(f"Debug message: <{e}>")
                    overall_status_dict[archive]['compressed_file_meta']['Failed_to_move'] = str(archive_file_path.name)
            else:
                overall_status_dict[archive]['compressed_file_meta']['exceptions_found'] = str(archive_file_path)
                logging.warning(f"Compressed file not moved to <{destination_dir.stem}>: <{archive_file_path.name}> "
                                f"contains: <{len(overall_status_dict[archive]['unknown']['names'])}> unknown (or) "
                                f"<{len(overall_status_dict[archive]['corrupted']['names'])}> corrupted (or) "
                                f"<{len(overall_status_dict[archive]['failed_to_copy_meta'].keys())}> failed to copy files (or)"
                                f"<{len(overall_status_dict[archive]['backlog_meta']['mismatch_destination_file'])}> mismatched with copied file")
        else:
            logging.critical(f"Destination directory missing for moving archive files: <{archive_file_path}>")
            overall_status_dict[archive]['compressed_file_meta']['Failed_to_move'] = str(archive_file_path.name)
    return overall_status_dict

def append_status_to_excel(status_dict: dict, logs_path: Path, backend_path:Path) -> None:
    '''
    Converts overall_status_dict into an excel and appends it to previous excel as a tracing summary of all files
    parameters:
     ----------
    status_dict: output from clear_backlog_after_copy()
    logs_path: path to logs where excel to be saved
    '''
    # convert status dict to dataframe to export
    outlist = []
    for zipfile in status_dict.keys():
        for idx in ['copied_files_meta', 'failed_to_copy_meta']:
            for file in status_dict[zipfile][idx].keys():
                try:
                    dest_file = Path(status_dict[zipfile][idx][file]['destination_file'])

                    cellid = status_dict[zipfile][idx][file]['cellid']
                    zipfile_name = Path(zipfile).name
                    file_name = Path(file).name
                    supplier_name = status_dict[zipfile][idx][file]['supplier']
                    processed_on = f"{datetime.datetime.fromtimestamp(dest_file.stat().st_ctime)}"
                    file_size = dest_file.stat().st_size / 1e6
                    file_hash = get_file_hash(dest_file)
                    duplicate_flag = status_dict[zipfile][idx][file]['duplicate_flag']
                    status = idx.split('_')[0]
                    if duplicate_flag:
                        duplicate_act = status_dict[zipfile][idx][file]['duplicate_action']
                    else:
                        duplicate_act = None
                    destination_file_name = dest_file.name
                    dest_folder = str(dest_file.parent)

                    outlist.append(
                        [cellid, zipfile_name, file_name, supplier_name, processed_on, file_size, duplicate_flag,status,
                         duplicate_act, destination_file_name, dest_folder, file_hash])
                except Exception as e:
                    logging.warning(f"Error in append_status_to_excel() regarding: <{zipfile}>, debug message: {e}")

    extract_trace = pd.DataFrame(outlist, columns=['cellid', 'archive_name', 'file_name', 'supplier_name',
                                                   'processed_on', 'file_size(MB)', 'duplicate_file', 'status','duplicate_action', 'destination_file_name',
                                                   'destination_path','file_hash'])
    # hdf export is done to make sure every run has a trace exported which cannot be tampered easily,
    # since excel read/write might fail if it is opened by someone
    try:
        extract_trace.to_parquet(Path(backend_path/f"{time.strftime("%Y%m%d_%H%M%S")}_trace.parquet"), index=False)
    except Exception as e:
        logging.warning(f"Failed to export parquet trace to {logs_path}: \n Debug message {e}")

    # export to excel and append if file exists - might fail, but reconstruction possible from .h5 files in backend
    if Path(logs_path / 'extract_trace.xlsx').exists():
        old_sheet = pd.read_excel(logs_path / 'extract_trace.xlsx', sheet_name='extract_trace')
        new_sheet = pd.concat([old_sheet, extract_trace], ignore_index=True).drop_duplicates()
        try:
            with pd.ExcelWriter(logs_path / 'extract_trace.xlsx', mode="a", engine="openpyxl",
                                if_sheet_exists="replace") as writer:
                new_sheet.to_excel(writer, sheet_name="extract_trace", index=False)
        except Exception as e:
            logging.warning(
                f"Failed to write Excel file <extract_trace.xlsx>, instead wrote to <temp_extract_trace.xlsx>")
            logging.debug(f"Debug message: <{e}>")
            try:
                with pd.ExcelWriter(logs_path / 'temp_extract_trace.xlsx', mode="w", engine="openpyxl",
                                if_sheet_exists="replace") as writer:
                    new_sheet.to_excel(writer, sheet_name="extract_trace", index=False)
            except:
                logging.debug(f"Failed to write temp file as well <temp_extract_trace.xlsx>")
    else:
        new_sheet = extract_trace
        try:
            with pd.ExcelWriter(logs_path / 'extract_trace.xlsx', mode="w", engine="openpyxl") as writer:
                new_sheet.to_excel(writer, sheet_name="extract_trace", index=False)
        except Exception as e:
            logging.warning(
                f"Failed to create Excel log file <extract_trace.xlsx>, Debug message: <{e}>")
    return None


def find_latest_file_in_folder(folder_path:str|Path, suffix:str='*.json') -> str|None:
    """
    Finds the latest modified .json file in the given folder.
    Parameters:
        folder_path (str): The path to the folder to search in.
    Returns:
        str: The path to the latest .json file, or None if no .json files are found.
    """
    _files = glob.glob(os.path.join(folder_path, suffix))
    if len(_files) < 0:
        return None

    latest_file = max(_files, key=os.path.getmtime)
    return latest_file


def flatten_list(lst: list)->list:
    flat = []
    for item in lst:
        if isinstance(item, list):
            flat.extend(flatten_list(item))
        else:
            flat.append(item)
    return flat
