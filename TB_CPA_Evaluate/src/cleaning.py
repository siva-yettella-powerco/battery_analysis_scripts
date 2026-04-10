import pandas as pd


def fix_step_series(in_series):
    """Alternative step fixing using cumulative sum of absolute diffs."""
    step_series = in_series.copy()
    return step_series.diff().abs().clip(upper=1).cumsum().fillna(0)


def fix_capacity_counting(df_in):
    # NOTE: fix step id before capacity counting
    df = df_in.copy()
    df['Capacity_Ah'] = 0.0
    last_step_cap = 0
    for step_id, grp in df.groupby('Step_id', sort=False):
        step_cap = grp['Capacity_step_Ah']
        df.loc[grp.index, 'Capacity_Ah'] = step_cap.values + last_step_cap
        last_val = step_cap.iloc[-1]
        if len(step_cap) > 1 and last_val == 0 and abs(step_cap.iloc[-2]) > 0.1:
            last_step_cap += step_cap.iloc[-2]
        else:
            last_step_cap += last_val

    df['Capacity_Ah'] = df['Capacity_Ah'] - df['Capacity_Ah'].min()
    return df


def check_time_gap(cell_df, threshold=3600):
    """Detect time gaps exceeding threshold (seconds) in Unix_datetime column.

    Returns: (has_gap, gap_indices, gap_values)
    """
    time_gaps = cell_df['Unix_datetime'].diff().dt.total_seconds()
    if any(time_gaps > threshold):
        return True, time_gaps[time_gaps > threshold].index, time_gaps[time_gaps > threshold].values
    else:
        return False, [], []


def split_on_time_gaps(df, time_col, threshold):
    """Split DataFrame into segments at time discontinuities.

    Returns: list of DataFrame segments
    """
    df = df.sort_values(by=time_col).reset_index(drop=True)
    time_diffs = df[time_col].diff()
    split_indices = time_diffs[time_diffs > threshold].index

    segments = []
    start_idx = 0
    for idx in split_indices:
        segments.append(df.iloc[start_idx:idx])
        start_idx = idx
    segments.append(df.iloc[start_idx:])

    return segments
