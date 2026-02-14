from .dependencies import *
from .clear_backlog import *
from .file_handling import *

def rename_duplicate_files(file_paths):
    """
    Renames duplicate files in the list based on their name (not path).
    Appends _copy1, _copy2, etc., to duplicates.
    Args:
        file_paths (list of Path): List of pathlib.Path objects.
    Returns:
        list of Path: Updated list with renamed duplicates.
    """
    name_count = defaultdict(int)
    renamed_paths = []

    for path in file_paths:
        path = Path(path)
        name = path.name
        if name_count[name] == 0:
            renamed_paths.append(path)
        else:
            stem = path.stem
            suffix = path.suffix
            new_name = f"{stem}_copy{name_count[name]}{suffix}"
            new_path = path.with_name(new_name)

            if path.exists():
                try:
                    path.rename(new_path)
                    renamed_paths.append(str(new_path))
                except Exception as e:
                    print('exception')
                    logging.warning(f'Found Duplicate files {path.name}, but failed to rename it')
                    logging.debug(f"Debug message {e}")
                    renamed_paths.append(str(path))
        name_count[name] += 1

    return renamed_paths


def detect_archive(path: Path, recursive:bool=True, include_substrings:list=None) -> dict:
    """
    Detects archive files in given path and tests them if they are corrupt

    Parameters:
    -----------
     path: folder path to the archive files
     recursive: whether to recursively detect archive files in subfolders

    returns: dictionary of archives list which are segregated as DetectedArchives(all), tested (Ok) or exception (not OK)
    """
    out_dict = {'DetectedArchives':[],
                'TestedArchives':[],
                'ExceptionArchives':[]
                }

    project_path = path

    logging.info("\n<<<<<<<<<<<<< Detect & Test Archives >>>>>>>>>>>>>>\n")
    logging.info(f"Running: Detection of archives in: <{project_path.stem}>")
    if recursive:
        compressed_files = list(project_path.rglob('*.*'))
    else:
        compressed_files = list(project_path.glob('*.*'))

    # --- MINIMAL CHANGE: optional substring filter -------------------------
    if include_substrings:
        compressed_files = [
            f for f in compressed_files
            if any(sub in f.name for sub in include_substrings)
        ]
    # -----------------------------------------------------------------------

    logging.info(f"Found: <{len(compressed_files)}> archives in: <{project_path.stem}>")

    out_dict['DetectedArchives'] = [str(k) for k in compressed_files]

    logging.info(f"Testing the archives for corrupt files in: <{project_path.stem}>")
    for i in range(len(compressed_files)):
        if patoolib.is_archive(str(compressed_files[i])):
            try:
                patoolib.test_archive(str(compressed_files[i]))
                out_dict['TestedArchives'].append(str(compressed_files[i]))
            except Exception as e:
                out_dict['ExceptionArchives'].append(str(compressed_files[i]))
    if len(out_dict['ExceptionArchives']) > 0:
        logging.critical(f"\t Found <{len(out_dict['ExceptionArchives'])}> Corrupt Archives in: <{project_path.stem}>")
        logging.debug(f"\t list of corrupt archives: <{out_dict['ExceptionArchives']}>")

    # renaming the duplicate archive files
    logging.info(r"Renaming duplicate named tested archive files in incoming_folder")
    out_dict['TestedArchives'] = rename_duplicate_files(out_dict['TestedArchives'])
    return out_dict


def extract_to_folder(archive_path:Path, folder_path:Path) -> bool:
    """
    Extract archive file to a folder
    Parameters:
    -----------
     archive_path: archive file path
     folder_dir: folder path to export/extract
    """
    # Create a temporary folder & extract archive into temp folder
    try:
        logging.info(f"Extracting archive file <{archive_path.name}> to <{folder_path.stem}> folder")
        if not folder_path.is_dir():
            folder_path.mkdir(parents=False, exist_ok=True)
        # Extract files into temporary folder
        patoolib.extract_archive(str(archive_path), outdir=str(folder_path), verbosity=-1)
        return True
    except Exception as e:
        logging.critical(f"Failed to extract <{archive_path.name}> to <{folder_path.stem}> folder:")
        logging.debug(f"Archive Extract fail: {e}")
        return False

def main_extract_archives(archive_file_paths: list, out_dir: Path, backlog_dir:Path, config_path: Path) -> dict:
    """
    Extracts the archive files and copies them to their out_dir/cellid folder
    configuration is used to identify which files to copy & where

    Behvaiour:
    Incase filename already exists, it would still copy them but with a suffix of copy_num
    Incase a data sheet is split across multiple sheets, it would split the excel into parts with part_num in suffix
    Splitted excel would be ignored to copy, only parts already splitted would be copied

    Issue:
    Due to issue with releasing working files shutil.copy() doesnt work reliably, hence copy() is used
    A following function needs to shutil.unlink() or delete these copied files after confirming if they are duplicates

    parameters:
     archive_file_paths: Pathlib paths list, output from detect_archive
     copy_action: options to choose ['replace','create_copy','skip_copy']
    """
    logging.info(f"\n<<<<<<<<<<<<<< Extract Data from Archives >>>>>>>>>>>>>>\n")
    # try reading configuration file
    config_dict = load_config(config_path)
    overall_status_dict = defaultdict()

    # extract archive files to temporary folder
    for archive_path in tqdm(archive_file_paths):
        sorted_file_paths_dict_split = defaultdict()
        sorted_file_paths_dict = defaultdict()
        sorted_file_paths_dict_copy = defaultdict()

        archive_path = Path(archive_path)
        logging.info(f"Working on <{archive_path}>")
        temp_extract_folder = backlog_dir / f"temp_extract_{archive_path.stem}"
        if temp_extract_folder.exists():
            temp_extract_folder = backlog_dir / f"copy_{temp_extract_folder.stem}"
        # extract files to temp folder
        extract_to_folder(archive_path=archive_path, folder_path=temp_extract_folder)
        # attach configuration & filter files based on configuration
        sorted_file_paths_dict = filter_files_byConfig(extracted_folder=temp_extract_folder, config_dict=config_dict)
        # check for multiple_data_sheets only if splits_datasheets is "Yes"
        sorted_file_paths_dict_split = split_files_by_config(sorted_file_paths_dict)
        overall_status_dict[str(archive_path)] = sorted_file_paths_dict_split

        logging.info(f" -- Finished extracting <{archive_path.name}>")

    files_in_backlog = []
    for root, dirs, files in os.walk(backlog_dir):
        files_in_backlog.extend(files)  # Use extend instead of append to avoid nested lists

    files_left = [f for f in files_in_backlog if '.ini' not in f]

    logging.info(f"\nNote: Total files post extraction in backlog: {len(files_left)}\n")

    return overall_status_dict