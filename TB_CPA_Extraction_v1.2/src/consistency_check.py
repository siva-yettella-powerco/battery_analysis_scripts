import pandas as pd

from .dependencies import *
from .file_handling import get_file_hash

def file_consistency_check(backend_path: Path, extract_path: Path)->dict:
    logging.info("\n-------------------------- RUNNING CONSISTENCY CHECK -------------------------------------\n")
    # Load all parquet files
    parquet_files = [f for f in os.listdir(backend_path) if f.endswith('.parquet')]
    trace_combined = pd.DataFrame()

    for file in parquet_files:
        temp = pd.read_parquet(backend_path / file, engine='pyarrow')
        trace_combined = pd.concat([trace_combined, temp], ignore_index=True)

    # Construct full destination file paths
    trace_combined['dest_file_paths'] = trace_combined['destination_path'] + '\\' + trace_combined['destination_file_name']

    # Get unique traced paths and actual extracted files
    files_trace_paths = [Path(i) for i in trace_combined['dest_file_paths'].unique()]
    files_Extract_dir = [Path(i) for i in glob.glob(str(extract_path / "**/*.*"), recursive=True) if '.ini' not in Path(i).name]

    # Compare sets
    files_missing_in_extract = list(set(files_trace_paths) - set(files_Extract_dir))
    files_not_traced = list(set(files_Extract_dir) - set(files_trace_paths))
    files_tweaked_in_extract = []
    files_ok = []
    cannot_confirm_properties = []

    for file in set(files_Extract_dir).intersection(files_trace_paths):
        try:
            stored_hash = trace_combined[trace_combined['dest_file_paths'] == str(file)]['file_hash'].iloc[0]
            if get_file_hash(file) == stored_hash:
                files_ok.append(file)
            else:
                files_tweaked_in_extract.append(file)
        except Exception as e:
            logging.debug(f"Debug message: {e}")
            cannot_confirm_properties.append(file)

    # Logging
    if files_missing_in_extract:
        logging.warning(f"Files missing in extracted folder:\n{files_missing_in_extract}\n"
                        f"Note: Recover manually using source zip file name in trace.")
    if files_not_traced:
        logging.warning(f"Files not part of tracing:\n{files_not_traced}\n"
                        f"Note: Possibly due to deleted backend files or manual extraction.")
    if files_tweaked_in_extract:
        logging.warning(f"Files tweaked in extract:\n{files_tweaked_in_extract}\n"
                        f"Note: File size mismatch.")
    if cannot_confirm_properties:
        logging.warning(f"Files with unconfirmed properties:\n{cannot_confirm_properties}")

    if files_ok:
        logging.info(f"Number of files which are ok: <{len(files_ok)}> out of <{len(files_trace_paths)}> unique traces")

    return {
        "files_missing_in_extract": files_missing_in_extract,
        "files_not_traced": files_not_traced,
        "files_tweaked_in_extract": files_tweaked_in_extract,
        "cannot_confirm_properties": cannot_confirm_properties,
        "files_ok": files_ok,
        }
