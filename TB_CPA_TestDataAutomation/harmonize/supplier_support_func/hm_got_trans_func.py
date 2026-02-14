from TB_CPA_TestDataAutomation.src.dependencies import *

def got_rename_step(file_df: pd.DataFrame, input_columns: list[str]) -> pd.Series | None:
    rename_map = {
        "Rest": "Rest",
        "CCCharge": "Charge",
        "CCCVCharge": "Charge",
        "CCCVDisCharge": "Discharge",
        "CCDisCharge": "Discharge",
        "ControlStep": "Control"
    }
    if input_columns:
        return file_df[input_columns[0]].str.strip().map(rename_map)
    else:
        return None


def got_transform_reltime(file_df:pd.DataFrame, input_column:list[str]) -> pd.Series|None:
    # transforms the time data of format 0d 08:47:57.31 to seconds
    try:
        if (len(input_column)>0) and (input_column[0] in file_df.columns):
            return file_df[input_column[0]] - file_df[input_column[0]].iloc[0]
    except:
        return None

def got_transform_unixtime(file_df:pd.DataFrame, input_columns:list[str])-> pd.Series|None:
    # input 0 is Absolute time, input 1 is TotalTime(s)
    # Tries to pick the first time stamp and add the total seconds to the timestamp, after gap correction

    DPT_Time = pd.to_datetime(file_df[input_columns[0]], errors='coerce')
    if (len(input_columns)>1):
        # try to add timedelta and total seconds caluclated from mcm_transform_reltime() - which considers steptime
        if (input_columns[0] in input_columns) and (input_columns[1] in input_columns):
            test_time = got_transform_reltime(file_df, input_columns[1:])    # total test time in seconds
            rel_time_delta = test_time.diff()  # relative time delta
            abs_time_delta = (DPT_Time - DPT_Time.iloc[0]).dt.total_seconds().diff() #absolute time delta

            for indx in rel_time_delta.loc[(abs_time_delta - rel_time_delta) > 60].index:
                test_time.loc[indx:] = test_time.loc[indx:] + abs_time_delta.loc[indx]

            timeser = DPT_Time.iloc[0] + pd.to_timedelta(test_time, 's')

            if (pd.to_datetime(file_df[input_columns[0]]).iloc[-1] - timeser.iloc[-1]).total_seconds() < 60:
                return timeser
            else:
                logging.info(f"Note @mcm_transform_unixtime() - mismatch in last datetime value, rather using only {input_columns[0]}")

    timeser = pd.to_datetime(file_df[input_columns[0]],errors='coerce')
    return timeser


def got_transform_reltime_abs(file_df:pd.DataFrame, input_columns:list[str])-> pd.Series|None:
    timeser = pd.to_datetime(file_df[input_columns[0]],errors='coerce')
    relative_time_seconds = (timeser - timeser.iloc[0]).dt.total_seconds()
    return relative_time_seconds

def got_transform_unixtime_abs(file_df:pd.DataFrame, input_columns:list[str])-> pd.Series|None:
    timeser = pd.to_datetime(file_df[input_columns[0]],errors='coerce')
    return timeser

def got_rename_step_chinese(file_df: pd.DataFrame, input_columns: list[str]) -> pd.Series | None:
    rename_map = {
        "静置": "Rest",
        "充电CC-CV": "Charge",
        "放电DC": "Discharge",
    }
    if input_columns:
        return file_df[input_columns[0]].str.strip().map(rename_map)
    else:
        return None

def got_transform_Tcold(file_df:pd.DataFrame, input_column:list[str]) -> pd.Series|None:
    "if T4(℃) and TemperBoxTempPV(℃) exist then take T4(℃) as T Cold, if TemperBoxTempPV(℃) is absent then just leave it"

    try:
        if (input_column[1] in file_df.columns) and (input_column[0] in file_df.columns):
            return file_df[input_column[0]]
        elif (input_column[1] not in file_df.columns) and (input_column[0] in file_df.columns):
            return None
    except:
        return None