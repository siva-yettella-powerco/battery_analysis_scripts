import numpy as np
import pandas as pd


def find_matching_column_number(columns, number_to_match):
    match_cols = [i for i in columns if float(i)==number_to_match]
    if len(match_cols)==1:
        return match_cols[0]
    elif len(match_cols)>1:
        print(f"Warning, More than one column match in CDS {match_cols}")
        return match_cols[0]
    else:
        print("No Column match found in CDS")
        return None


def is_within_range(value, in_range=[]):
    return min(in_range) <= value <= max(in_range)


def closest_lower_number(numbers, target):
    lower_numbers = [num for num in numbers if num <= target]
    return max(lower_numbers) if lower_numbers else None


def closest_nth_higher_number(numbers, target, n=1):
    higher_numbers = sorted([num for num in numbers if num >= target])
    return higher_numbers[n - 1] if len(higher_numbers) >= n else None


def find_closest_indx_series(series, value):
    series = pd.Series(series)
    return (series - value).abs().idxmin()


def find_closest_argindx_series(series, value):
    series = pd.Series(series)
    return (series - value).abs().argmin()


def find_range(series):
    return series.max() - series.min()


def filter_by_proximity(values, threshold):
    """Filter values that have at least one neighbor within threshold."""
    result = []
    for i, val in enumerate(values):
        has_neighbor = any(
            i != j and abs(val - other) <= threshold
            for j, other in enumerate(values)
        )
        if has_neighbor:
            result.append(val)
    return result


def non_averaging_median(series):
    """Returns the lower median value (actual data point, not average of two middle values)."""
    sorted_series = series.sort_values().reset_index(drop=True)
    n = len(sorted_series)
    if n == 0:
        return None
    elif n % 2 == 1:
        return sorted_series.iloc[n // 2]
    else:
        return sorted_series.iloc[(n // 2) - 1]


def get_non_outlier_indices(data, threshold=4):
    """Returns indices of non-outliers using Modified Z-Score (MAD method)."""
    data = np.array(data)
    median = np.median(data)
    deviation = np.abs(data - median)
    mad = np.median(deviation)

    if mad == 0:
        return []

    modified_z_scores = 0.6745 * deviation / mad
    non_outlier_indices = np.where(modified_z_scores <= threshold)[0]

    return non_outlier_indices.tolist()
