from pandas.core.ops.missing import mask_zero_div_zero

from TB_CPA_TestDataAutomation.src.dependencies import *

def convert_mcm_xls_to_df(input_path:Path) -> [dict, bool]:
    # converts the iso8859 .xls files from MCM to dataframe
    try:
        # Read the file with ISO-8859-1 encoding and CRLF line endings
        with open(input_path, 'r', encoding='ISO-8859-1', newline='\r\n') as file:
            lines = file.readlines()

        # Split lines into columns assuming comma-separated values
        data = [line.strip().split('\t') for line in lines]
        # Create a DataFrame
        convert_df = pd.DataFrame(data)
        return {'Data':convert_df}, True

    except Exception as e:
        logging.warning('Error while converting .XLS file to dataframe in convert_iso8859_to_xlsx()')
        logging.debug(f'Debug message: {e}')
        return {'Data':pd.DataFrame()}, False

def parse_d_hms_ms(series: pd.Series) -> pd.Series:
    """
    Convert a Series of strings in 'd.hh:mm:ss.ms' into pandas Timedelta.
    Examples: '0.00:00:30.000', '2.12:05:07', '10.00:00:00.123'
    Non-matching rows become NaT. NaN is preserved.
    """
    # Regex pattern with named groups for clarity
    pat = r'^(?P<days>\d+)\.(?P<hours>\d{2}):(?P<minutes>\d{2}):(?P<seconds>\d{2})(?:\.(?P<msecs>\d+))?$'

    # Extract components
    parts = series.astype('string').str.extract(pat)

    # If nothing matches, return all-NaT Series of same index
    if parts.isna().all(axis=None):
        return pd.Series(pd.NaT, index=series.index, dtype='timedelta64[ns]')

    # Convert each component to numeric; missing msecs -> 0
    days    = pd.to_numeric(parts['days'], errors='coerce').fillna(0)
    hours   = pd.to_numeric(parts['hours'], errors='coerce').fillna(0)
    minutes = pd.to_numeric(parts['minutes'], errors='coerce').fillna(0)
    seconds = pd.to_numeric(parts['seconds'], errors='coerce').fillna(0)
    msecs   = pd.to_numeric(parts['msecs'], errors='coerce').fillna(0)

    # Build timedelta vectorized
    td = (
        pd.to_timedelta(days,    unit='D') +
        pd.to_timedelta(hours,   unit='h') +
        pd.to_timedelta(minutes, unit='m') +
        pd.to_timedelta(seconds, unit='s') +
        pd.to_timedelta(msecs,   unit='ms')
    )

    # Merge back: rows that didn't match the pattern become NaT
    matched = series.astype('string').str.match(pat, na=False)
    out = pd.Series(pd.NaT, index=series.index, dtype='timedelta64[ns]')
    out.loc[matched] = td.loc[matched].values
    return out

def mcm_transform_reltime_from_steptime(file_df:pd.DataFrame, input_column:list[str]) -> pd.Series|None:
    try:
        if "d.h" in input_column[0]:
            step_time_series = pd.to_timedelta(parse_d_hms_ms(file_df[input_column[0]])).dt.total_seconds()
            mask = step_time_series.diff() < 0
            delta_step_time = step_time_series.diff().clip(lower=0)
            delta_step_time[mask] = step_time_series[mask]
            total_time = delta_step_time.cumsum().fillna(0)
            return total_time
    except:
        return None

def mcm_transform_reltime_from_totaltime(file_df:pd.DataFrame, input_column:list[str]) -> pd.Series|None:
    try:
        if "d.h" in input_column[0]:
            step_time_series = pd.to_timedelta(parse_d_hms_ms(file_df[input_column[0]])).dt.total_seconds()
            return step_time_series
    except:
        return None

def mcm_transform_reltime(file_df:pd.DataFrame, input_column:list[str]) -> pd.Series|None:
    # input_columns = ["Test Time","Step Time"]
    # input format 0d 08:47:57.31, uses both columns to create a step time, assuming step time has better time resolution

    try:
        if (len(input_column)>1) and (input_column[0] in file_df.columns) and (input_column[1] in file_df.columns):
            test_time = pd.to_timedelta(file_df[input_column[0]]).dt.total_seconds().copy()
            step_time = pd.to_timedelta(file_df[input_column[1]]).dt.total_seconds().copy()

            delta_test_time = test_time.diff()
            delta_step_time = step_time.diff()
            delta_step_time[delta_step_time < 0] = 0

            mask = delta_test_time == 0
            for i in test_time.loc[mask].index:
                test_time.at[i] = test_time.at[i-1] + delta_step_time.at[i]

            return test_time.round(3)

        elif (input_column[0] in file_df.columns):
            test_time = pd.to_timedelta(file_df[input_column[0]]).dt.total_seconds().copy()
            return test_time.round(3)
    except:
        return None

def mcm_transform_unixtime(file_df:pd.DataFrame, input_columns:list[str])-> pd.Series|None:
    # input 0 is datetime and input 1 is Test time, input 2 is Step time
    # All inputs are in datetime format
    # Tries to pick the first time stamp and add the total seconds to the timestamp, after gap correction
    try:
        DPT_Time = pd.to_datetime(file_df[input_columns[0]], errors='coerce')
        if (len(input_columns)>1):
            # try to add timedelta and total seconds caluclated from mcm_transform_reltime() - which considers steptime
            if (input_columns[0] in input_columns) and (input_columns[1] in input_columns):
                # total test time in seconds
                if "d.h" in input_columns[1]:
                    test_time = mcm_transform_reltime_from_steptime(file_df, input_columns[1:])
                else:
                    test_time = mcm_transform_reltime(file_df, input_columns[1:])

                # add initial time step and the test time
                timeser = DPT_Time.iloc[0] + pd.to_timedelta(test_time, 's')

                # do a final check if the calculated timeseries and intial timeseries are aligned within 60s for last value
                if (pd.to_datetime(file_df[input_columns[0]]).iloc[-1] - timeser.iloc[-1]).total_seconds() < 60:
                    return timeser
                else:
                    rel_time_delta = test_time.diff()  # relative time delta
                    abs_time_delta = (DPT_Time - DPT_Time.iloc[0]).dt.total_seconds().diff()  # absolute time delta

                    # Add unknown gaps in absolute time to relative time
                    for indx in rel_time_delta.loc[(abs_time_delta - rel_time_delta) > 60].index:
                        test_time.loc[indx:] = test_time.loc[indx:] + abs_time_delta.loc[indx]
                    # add initial time step and the test time
                    timeser = DPT_Time.iloc[0] + pd.to_timedelta(test_time, 's')

                if (pd.to_datetime(file_df[input_columns[0]]).iloc[-1] - timeser.iloc[-1]).total_seconds() < 60:
                    return timeser
                else:
                    #logging.info(f"Note @mcm_transform_unixtime() - mismatch in last datetime value, rather using only {input_columns[0]}")
                    logging.debug(
                        f"Note @mcm_transform_unixtime() - mismatch in last datetime value: {(pd.to_datetime(file_df[input_columns[0]]).iloc[-1] - timeser.iloc[-1]).total_seconds()}")

        #timeser = pd.to_datetime(file_df[input_columns[0]],errors='coerce')
        return timeser
    except:
        return None

def mcm_transform_Tcold(file_df:pd.DataFrame, input_column:list[str]) -> pd.Series|None:
    "if Temp 5 and Temp 6 exist then take Temp 5 as T Cold, if Temp 6 is absent then just leave it"

    try:
        if (input_column[1] in file_df.columns) and (input_column[0] in file_df.columns):
            return file_df[input_column[0]]
        elif (input_column[1] not in file_df.columns) and (input_column[0] in file_df.columns):
            return None
    except:
        return None

def mcm_transform_direction(file_df:pd.DataFrame, input_columns:list[str])-> pd.Series|None:
    # Any column passed at [0] would be multiplied with -1 when discharge
    tempdf = file_df.copy()
    curr_col = input_columns[0]
    state_col = input_columns[1]

    tempdf.loc[tempdf[state_col] == 'D', curr_col] = tempdf.loc[tempdf[state_col] == 'D', curr_col]*(-1)

    return tempdf[curr_col]

def mcm_rename_step(file_df:pd.DataFrame, input_columns:list[str])-> pd.Series|None:
    rename_map = {
        "R":"Rest",
        "C":"Charge",
        "D":"Discharge",
        "O":"Control"
    }
    if input_columns:
        return file_df[input_columns[0]].map(rename_map)
    else:
        return None

# def mcm_transform_unixtime(file_df:pd.DataFrame, input_columns:list[str])-> pd.Series|None:
#     # transforms date time into unix format
#     if (len(input_columns) > 0) and (input_columns[0] in file_df.columns):
#         return pd.to_datetime(file_df[input_columns[0]],format='%Y-%m-%d %H:%M:%S.%f',errors='coerce')
#     return None

# def mcm_transform_unixtime_xls_temp(file_df:pd.DataFrame, input_columns:list[str])-> pd.Series|None:
#     # input 0 is datetime and input 1 is total_time_s in seconds
#     DPT_time_series = pd.to_datetime(file_df[input_columns[0]],errors='coerce')
#     return DPT_time_series.iloc[0] + pd.to_timedelta(file_df[input_columns[1]])
#
# def mcm_transform_unixtime_xls(file_df:pd.DataFrame, input_columns:list[str])-> pd.Series|None:
#     # input 0 is datetime and input 1 is totaltime in datetime format
#     DPT_time_series = pd.to_datetime(file_df[input_columns[0]],errors='coerce')
#     timeser = DPT_time_series[~DPT_time_series.isna()]
#     is_sec_rounded_flag = (timeser == timeser.dt.round('s'))
#     is_min_rounded_flag = (timeser == timeser.dt.round('min'))
#     if all(is_sec_rounded_flag) and (len(input_columns)>1):
#         if (input_columns[1] in file_df.columns):
#             # Convert to timedelta
#             total_time_s = pd.to_timedelta(file_df[input_columns[1]]).dt.total_seconds()
#             delta_time_s = total_time_s.diff().fillna(value=0)
#             temp_time_ms = round((delta_time_s % 1) * 1000)
#             temp_time_ms = temp_time_ms.astype(int)
#             return DPT_time_series + pd.to_timedelta(temp_time_ms, unit='ms')
#
#     return pd.to_datetime(file_df[input_columns[0]],errors='coerce')

