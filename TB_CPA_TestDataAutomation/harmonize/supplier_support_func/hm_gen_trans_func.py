import pandas as pd

from TB_CPA_TestDataAutomation.src.dependencies import *
from TB_CPA_TestDataAutomation.harmonize.supplier_support_func.hm_general_support import *
from TB_CPA_TestDataAutomation.harmonize.supplier_support_func.hm_mcm_trans_func import *
from TB_CPA_TestDataAutomation.harmonize.supplier_support_func.hm_tru_trans_func import *
from TB_CPA_TestDataAutomation.harmonize.supplier_support_func.hm_got_trans_func import *
from TB_CPA_TestDataAutomation.harmonize.supplier_support_func.hm_sz_trans_func import *
from TB_CPA_TestDataAutomation.harmonize.supplier_support_func.hm_srf_trans_func import *

def gen_calc_power(file_df: pd.DataFrame) -> pd.Series | None:
    # returns power in W
    if ('Voltage_V' in file_df.columns) and ('Current_A' in file_df.columns):
        return file_df['Voltage_V']*file_df['Current_A']
    else:
        return None

def convert_timestamp(x):
    # convert datetime to unix time format
    try:
        return x.timestamp()
    except:
        return None

def gen_calc_unix(file_df: pd.DataFrame)->pd.Series|None:
    if 'Date_time' in file_df.columns:
        return file_df['Date_time'].apply(convert_timestamp)
    else:
        return None

def gen_apply_transform_raw_data(file_data:pd.DataFrame, cfg_mapping:pd.Series, focus_columns:list[str]):
    '''
    apply the transformation of the files as per the config excel file
    '''
    df_unify = pd.DataFrame(columns=focus_columns)
    df_file = file_data.copy()

    header_map_df = check_header_to_cfg_cols(sheet_df=df_file, cfg_selected=cfg_mapping,
                                             select_cols=focus_columns)
    direct_map_df = header_map_df[(header_map_df['File_header'] != 'function()') & (header_map_df['Map_flg'] == True)]
    trans_map_df = header_map_df[(header_map_df['File_header'] == 'function()') & (header_map_df['Map_flg'] == True)]
    trans_map_df = gen_extract_transform_fn(trans_map_df=trans_map_df, file_columns=df_file.columns)

    for k in range(direct_map_df.shape[0]):
        unify_col = direct_map_df['Main_header'].iloc[k]
        file_col = direct_map_df['File_header'].iloc[k]
        if (file_col in df_file.columns) and (unify_col in df_unify.columns):
            df_unify[unify_col] = df_file[file_col]

    # TODO incase of OR || based condition last one takes priority as it overwrites
    # functions executed for transformation
    if trans_map_df.shape[0]>0:
        for k in trans_map_df[trans_map_df['function_level']==1].index:
            unify_col = trans_map_df.loc[k, 'Main_header']
            file_col = trans_map_df.loc[k, 'File_header']
            func_name = trans_map_df.loc[k, 'function_name']
            if (trans_map_df.loc[k, 'function_name'] in globals()):
                input_cols = trans_map_df.loc[k, 'function_inputs']
                df_unify[unify_col] = globals()[func_name](df_file, input_cols)
            else:
                logging.warning(f'Transform Function: {func_name} at level{trans_map_df.loc[k, "function_level"]} not found')

        # functions executed on after transform file
        for k in trans_map_df[trans_map_df['function_level']==2].index:
            unify_col = trans_map_df.loc[k, 'Main_header']
            file_col = trans_map_df.loc[k, 'File_header']
            func_name = trans_map_df.loc[k, 'function_name']
            if (trans_map_df.loc[k, 'function_name'] in globals()):
                df_unify[unify_col] = globals()[func_name](df_unify)
            else:
                logging.warning(f'Transform Function: {func_name} at level{trans_map_df.loc[k, "function_level"]} not found')
    return df_unify