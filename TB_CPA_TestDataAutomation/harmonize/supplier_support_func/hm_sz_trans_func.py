from TB_CPA_TestDataAutomation.src.dependencies import *


def SZ_transform_capacity(file_df:pd.DataFrame, input_columns:list[str]) -> pd.Series|None:
    # transforms the time data of format 0d 08:47:57.31 to seconds
    try:
        if (len(input_columns)>0) and (input_columns[0] in file_df.columns) and (input_columns[1] in file_df.columns):
            return file_df[input_columns[0]] - file_df[input_columns[1]]
    except:
        return None


def SZ_transform_energy(file_df:pd.DataFrame, input_columns:list[str]) -> pd.Series|None:
    # transforms the time data of format 0d 08:47:57.31 to seconds
    try:
        if (len(input_columns)>0) and (input_columns[0] in file_df.columns) and (input_columns[1] in file_df.columns):
            return file_df[input_columns[0]] - file_df[input_columns[1]]
    except:
        return None


def SZ_name_step(file_df:pd.DataFrame, input_column:list[str]) -> pd.Series|None:
    # transforms the time data of format 0d 08:47:57.31 to seconds
    try:
        if (len(input_column)>0) and (input_column[0] in file_df.columns):
            return file_df[input_column[0]].apply(lambda x: "Discharge" if x < 0 else "Charge" if x > 0 else "Rest")

    except:
        return None
