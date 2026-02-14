## TB_CPA_TestDataAutomation
To automatically handle data from various test institutes and organize, post process the data 

### Archive handling
Archive types are detected in incoming_folder and tested if they are corrupted. Upon successful testing they are processed for extraction

### File handling
Files are not moved, but rather first copied and upon verifying successful copy, backlog file is deleted

### File copying
When a duplicate name exists in destination folder, 
it would append _copy suffix to file being copied

### Reading .json file
json file is used to summarize status of files to extract for debugging

- _archive_path_ 
  - _to_copy_ : 
    - _meta_ : contains all files along with config values which match config definition eg. "DQ*.xlsx"
    - _post_split_meta_ : it is exact copy of "to_copy:meta" (above), except if any file is splitted, here only parts are considered and main file is ignored
    - _splitting_info_ : contains which files are splitted (sheets in excel split) and its parts names
  - _to_ignore_ : files which are ignored as per config file or parent file which is splitted (sheets in excel split)
  - _unknown_ : files which doesn't meet include nor ignore criteria as per config file
  - _corrupted_: files which couldn't be handled possibly due to corruption
  - _copied_files_meta_ : files which are copied successfully to their respective cell folder, contains its destination path
  - _failed_to_copy_meta_ : files which couldn't be copied (which supposed to be copied) due to system/permission issues
  - _backlog_meta_ :
    - _cleared_in_backlog_ : files which are copied successfully & cleared in backlog
    - _failed_to_remove_copied_file_ : files copied but failed to delete their duplicate in backlog, these can be manually deleted later
    - _mismatch_destination_file_ : these files which were supposed to be copied are somehow not copied in destination. It requires special attention
    - _ignored_files_in_backlog_ : files which are ignored in backlog and these are files either ignored as per config or splitted file parent
    - _failed_remove_ignored_files_ : files which are ignored in backload couldnt be removed due to system/permission issues
  - _compressed_file_meta_ :
    - _copied_to_Archived_ : files which are copied to 07_Archived folder from 01_Incoming_Compressed_Files
    - _can_remove_manually_ : files which are copied but not removed in 01_Incoming_Compressed_Files, which can be manually deleted
    -  _caution_move_manually_ : files which are not present in 07_Archive and yet to be moved there from 01_Incoming_Compressed_Files
    - _exceptions_found_ : files where archives are not moved intentionally, as corresponding backlog files have exceptions
