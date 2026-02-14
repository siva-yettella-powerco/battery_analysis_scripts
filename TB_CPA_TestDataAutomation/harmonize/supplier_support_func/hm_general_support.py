from TB_CPA_TestDataAutomation.src.dependencies import *
from TB_CPA_TestDataAutomation.harmonize.hm_supplier_config import detect_supplier, MANDATORY_COLS_ETL
import pandas as pd

def convert_str_numeric_columns(df):
    """
    Converts columns with numeric strings to numeric types using .str.isnumeric(),
    while retaining other columns as they are.
    """
    for col in df.columns:
        if df[col].dtype == 'object':
            # Check if all non-null values are numeric strings
            if df[col].dropna().str.isnumeric().all():
                df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def check_header_to_cfg_cols(sheet_df: pd.DataFrame, cfg_selected: pd.Series, select_cols: list) -> pd.DataFrame:
    """
    Return: A summary dataframe which gives config to file column mapping if possible or
    Nan if not available or function() for transformations $$
    Note: incase of Step || StepNum if both matches then it creates 2 rows in dataframe for same Main_header
    """
    cfg_select_series = cfg_selected[select_cols]
    header_values = set(sheet_df.columns)
    match_list = []

    for idx, item in enumerate(cfg_select_series):

        if item == None:
            item_mod = item
        elif pd.isna(item):
            match_list.append([cfg_select_series.index[idx], item, None, False])
        elif ('||' in item) and ('$$' not in item):
            item_mod = gen_str_or_split(item)
        else:
            item_mod = item

        if isinstance(item_mod, list):
            for sub_item in item_mod:
                if sub_item in header_values:
                    match_list.append([cfg_select_series.index[idx],item,sub_item, True])
        else:
            if item_mod in header_values:
                match_list.append([cfg_select_series.index[idx],item,item_mod, True])
            else:
                if '$$' in item_mod:
                    # saves the function $$ inputs as items_func list
                    items_func = [i.strip() for i in re.findall(r'"([^"]*)"', item_mod)]
                    val_flags = []
                    for i_fn in items_func:
                        if '||' in i_fn:
                            items_func_temp = gen_str_or_split(i_fn)
                            val_flags.append(any([sub_i in header_values for sub_i in items_func_temp]))
                        else:
                            val_flags.append(i_fn in header_values)
                    items_flg = all(val_flags)
                    match_list.append([cfg_select_series.index[idx],item,'function()',items_flg])
                else:
                    match_list.append([cfg_select_series.index[idx],item,None, False])

    out_df = pd.DataFrame(match_list, columns=['Main_header','Cfg_header','File_header','Map_flg'])

    return out_df

def find_row_with_substring(df, substring="time"):
    # Convert all values to string and check if any cell contains the substring
    mask = df.astype(str).apply(lambda row: row.str.contains(substring, case=False)).any(axis=1)

    # Find the first row index where the condition is True
    matching_indices = df.index[mask]
    return matching_indices[0] if not matching_indices.empty else None

def gen_clean_datasheet(sheet_df:pd.DataFrame,config_selected:pd.Series,focus_cols:list,
                      mandatory_cols:list) -> tuple[bool,pd.DataFrame,pd.DataFrame]:
    '''
    Correct the header for the sheet & drop unnecessary rows.
    Find the columns with matching columns as per configuration, if not found mark check_flg to False
    '''
    sheet_check_flg = True

    #---------- Set the header and drop other top rows --------
    # TODO auto pick header number
    header_num = config_selected['Header_row_num']
    if (sheet_df.shape[1] - sheet_df.iloc[header_num-2, :].isna().sum()) < len(focus_cols):
        head_idx = find_row_with_substring(sheet_df, substring="step")
        if head_idx:
            header_num = head_idx + 2

    # Determine the header row
    if header_num > 1:
        # headers are stripped to remove spaces before or after name
        sheet_df.columns = sheet_df.iloc[header_num-2, :].astype(str).str.strip()
        sheet_df = sheet_df.iloc[header_num-1:, :].reset_index(drop=True)
    else:
        sheet_df.columns = sheet_df.columns.astype(str).str.strip()

    for col in sheet_df.columns:
        if sheet_df[col].dtype == 'object':  # string columns
            try:
                sheet_df[col] = pd.to_numeric(sheet_df[col].str.strip().str.replace(r'(?<=\d),(?=\d)', '', regex=True),
                                              errors='raise')
            except:
                continue

    header_map_df = check_header_to_cfg_cols(sheet_df=sheet_df, cfg_selected=config_selected, select_cols=focus_cols)
    sheet_check_flg = bool(header_map_df[header_map_df['Main_header'].isin(mandatory_cols)]['Map_flg'].all())
    if not sheet_check_flg:
        logging.info(header_map_df)
        logging.info(sheet_df.columns)
        logging.info(config_selected['Config_id'])


    # TODO drop the rows where the mandatory columns are NaN
    # TODO convert the rows to numeric where possible

    return sheet_check_flg, sheet_df, header_map_df

def map_to_unified_cols(raw_df, cfg_selected, focus_cols):

    header_map_df = check_header_to_cfg_cols(sheet_df=raw_df, cfg_selected=cfg_selected,
                                             select_cols=focus_cols)
    direct_map_df = header_map_df[(header_map_df['File_header'] != 'function()') & (header_map_df['Map_flg'] == True)]

    df_unify = pd.DataFrame(columns=focus_cols)
    df_file = raw_df

    for k in range(direct_map_df.shape[0]):
        unify_col = direct_map_df['Main_header'].iloc[k]
        file_col = direct_map_df['File_header'].iloc[k]
        print(unify_col, ' :: ', file_col)
        if (file_col in df_file.columns) and (unify_col in df_unify.columns):
            df_unify[unify_col] = df_file[file_col]

    return df_unify


def gen_str_or_split(string_in:str) -> list:
    '''
    splits the string for '||' pattern and returns a list of splitted strings.
    spaces before and after the '||' character are ignored
    '''
    split_list = string_in.split('||')
    return [i.strip() for i in split_list]


def gen_extract_transform_fn(trans_map_df: pd.DataFrame, file_columns:list) -> pd.DataFrame:
    '''
    Returns the dataframe with 2 additional columns: function name and function inputs which are extracted from the config string
    '''

    # Tranformation
    trans_map_df.loc[:,'function_name'] = ''
    trans_map_df.loc[:,'function_inputs'] = None
    trans_map_df.loc[:,'function_level'] = 99

    for k in trans_map_df.index:
        unify_col = trans_map_df.loc[k, 'Main_header']
        cfg_fn_arg = trans_map_df.loc[k, 'Cfg_header']

        transform_fn = None
        inputs_fn = []
        level = 1

        # extract function name and inputs needed for transformation $$ first level
        if fnmatch.fnmatch(cfg_fn_arg, '$$[!$]*'):
            match_fn = re.match(r"\$\$(\w+)\((.*)\)", cfg_fn_arg)
            if match_fn:
                # transform_fn contains the function name
                transform_fn = match_fn.group(1)
                level = 1

                # loop the list of inputs of function in " " as items_fn
                for i_temp in [i.strip() for i in re.findall(r'"([^"]*)"', cfg_fn_arg)]:
                    if '||' in i_temp:
                        k_temp_list = [j_temp for j_temp in gen_str_or_split(i_temp) if j_temp in file_columns]
                        inputs_fn.append(k_temp_list[0])
                    else:
                        inputs_fn.append(i_temp)

        # extract function name and inputs needed for transformation $$$ second level
        elif fnmatch.fnmatch(cfg_fn_arg, '$$$[!$]*'):
            match_fn = re.match(r"\$\$\$(\w+)\((.*)\)", cfg_fn_arg)
            if match_fn:
                # transform_fn contains the function name
                transform_fn = match_fn.group(1)
                level = 2
                # loop the list of inputs of function in " " as items_fn
                for i_temp in [i.strip() for i in re.findall(r'"([^"]*)"', cfg_fn_arg)]:
                    if '||' in i_temp:
                        k_temp_list = [j_temp for j_temp in gen_str_or_split(i_temp) if j_temp in file_columns]
                        inputs_fn.append(k_temp_list[0])
                    else:
                        inputs_fn.append(i_temp)

        trans_map_df.loc[k, 'function_name'] = transform_fn
        trans_map_df.at[k, 'function_inputs'] = inputs_fn
        trans_map_df.loc[k, 'function_level'] = level

    return trans_map_df


def export_to_harmonized_folder(file_path: Path, harmonized_data: pd.DataFrame, harmonized_folder:Path,
                                copy_action: str):
    # Create output folder
    folder_out = harmonized_folder / file_path.parent.stem
    folder_out.mkdir(parents=False, exist_ok=True)

    # Initial target file
    csv_file_temp = folder_out / (file_path.stem + '.csv')

    # Handle copy logic
    if csv_file_temp.exists():
        if copy_action.lower() == 'skip_copy':
            return csv_file_temp # Skip exporting
        elif copy_action.lower() == 'create_copy':
            counter = 1
            while csv_file_temp.exists():
                csv_file_temp = folder_out / f"{file_path.stem}_copy{counter}{file_path.suffix}"
                counter += 1

    # Export to CSV
    harmonized_data.to_csv(csv_file_temp, index=False)
    return csv_file_temp
