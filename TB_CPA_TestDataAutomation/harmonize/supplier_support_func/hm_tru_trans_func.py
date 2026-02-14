from TB_CPA_TestDataAutomation.src.dependencies import *

def tru_rename_step(file_df: pd.DataFrame, input_columns: list[str]) -> pd.Series | None:
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

def tru_get_stepname(file_df: pd.DataFrame, input_columns: list[str]) -> pd.Series | None:
    # $$tru_get_stepname("Step Index","Current (A)"),
    try:
        step_series = pd.to_numeric(file_df[input_columns[0]], errors="coerce")
        current_series = pd.to_numeric(file_df[input_columns[1]], errors="coerce")

        out = pd.Series(index=file_df.index, dtype="float64", name="step_capacity")
        # ---- Process each step ----
        for step_value in pd.unique(step_series.dropna()):
            if current_series[step_series == step_value].median() > 0:
                out.loc[step_series == step_value] = "Charge"
            elif current_series[step_series == step_value].median() < 0:
                out.loc[step_series == step_value] = "Discharge"
            elif (current_series[step_series == step_value].count() == 1) & (current_series[step_series == step_value].median() == 0):
                out.loc[step_series == step_value] = "Control"
            else:
                out.loc[step_series == step_value] = "Rest"

        return out
    except:
        return None

def tru_transform_reltime(file_df:pd.DataFrame, input_column:list[str]) -> pd.Series|None:
    #just substracts the initial time
    try:
        if (len(input_column)>0) and (input_column[0] in file_df.columns):
            return file_df[input_column[0]] - file_df[input_column[0]].iloc[0]
    except:
        return None

def tru_transform_unixtime(file_df:pd.DataFrame, input_columns:list[str])-> pd.Series|None:
    # input 0 is Absolute time, input 1 is TotalTime(s)
    # Tries to pick the first time stamp and add the total seconds to the timestamp, after gap correction

    DPT_Time = pd.to_datetime(file_df[input_columns[0]], errors='coerce')
    if (len(input_columns)>1):
        # try to add timedelta and total seconds caluclated from mcm_transform_reltime() - which considers steptime
        if (input_columns[0] in input_columns) and (input_columns[1] in input_columns):
            test_time = tru_transform_reltime(file_df, input_columns[1:])    # total test time in seconds
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


def tru_transform_reltime_abs(file_df:pd.DataFrame, input_columns:list[str])-> pd.Series|None:
    timeser = pd.to_datetime(file_df[input_columns[0]],errors='coerce')
    relative_time_seconds = (timeser - timeser.iloc[0]).dt.total_seconds()
    return relative_time_seconds

def tru_transform_unixtime_abs(file_df:pd.DataFrame, input_columns:list[str])-> pd.Series|None:
    timeser = pd.to_datetime(file_df[input_columns[0]],errors='coerce')
    return timeser


def tru_get_step_capacity(file_df: pd.DataFrame, input_columns: list[str]) -> pd.Series|None:
    # $$tru_get_step_capacity("Step Index", "Charge Capacity (Ah)", "Discharge Capacity (Ah)")

    try:
        # ---- Coerce to numerics where applicable ----
        step_series = pd.to_numeric(file_df[input_columns[0]], errors="coerce")
        charge_cap_series = pd.to_numeric(file_df[input_columns[1]], errors="coerce")
        discharge_cap_series = pd.to_numeric(file_df[input_columns[2]], errors="coerce")

        out = pd.Series(index=file_df.index, dtype="float64", name="step_capacity")
        # ---- Process each step ----
        for step_value in pd.unique(step_series.dropna()):
            ch_ser = charge_cap_series.loc[step_series == step_value]
            dch_ser = discharge_cap_series.loc[step_series == step_value]

            out.loc[step_series == step_value] = (ch_ser-ch_ser.iloc[0])-(dch_ser-dch_ser.iloc[0])

        return out
    except:
        return None
