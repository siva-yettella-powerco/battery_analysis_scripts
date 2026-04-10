import pandas as pd
import numpy as np
from scipy.interpolate import interp1d
from scipy.optimize import curve_fit


def get_decimal_places(series):
    """Estimate the number of decimal places in a numeric pandas Series."""
    decimals = series.dropna().astype(str).str.split('.').str[1]
    decimals = decimals[decimals.notnull()]
    if not decimals.empty:
        return max(decimals.map(len).mode()[0], 2)
    return 2


def interpolate_dataframe_with_rounding(df, reference_col, new_values):
    """
    Interpolate all columns based on a reference column, preserving decimal precision.

    - If reference_col == "index", df.index is used as x-values
    - Output will also use new_values as index in that case
    """
    interpolated_data = {}

    for col in df.columns:
        if reference_col == 'index':
            f = interp1d(df.index, df[col], kind='linear', bounds_error=False, fill_value=np.nan)
        else:
            if col == reference_col:
                continue
            f = interp1d(df[reference_col], df[col], kind='linear', bounds_error=False, fill_value=np.nan)

        decimals = get_decimal_places(df[col])
        interpolated_data[col] = np.round(f(new_values), decimals)

    if reference_col == 'index':
        result = pd.DataFrame(interpolated_data, index=new_values)
        result.index.name = "index"
    else:
        interpolated_data[reference_col] = new_values
        result = pd.DataFrame(interpolated_data)

    return result


def arrhenius(T, A, Ea):
    """Arrhenius equation: k(T) = A * exp(-Ea / (R * T))

    Parameters:
    - T: temperature in Celsius (converted to Kelvin internally)
    - A: pre-exponential factor
    - Ea: activation energy (J/mol)
    """
    R = 8.314  # J/(mol*K)
    return A * np.exp(-Ea / (R * (T + 273.15)))


def fit_arrhenius(temperatures, values):
    """Fit Arrhenius model to all valid (non-NaN) data points.

    Returns: (fitted_values, popt) where popt = [A, Ea]
    """
    temperatures = np.array(temperatures, dtype=float)
    values = np.array(values, dtype=float)

    mask = ~np.isnan(values)
    T_fit = temperatures[mask]
    V_fit = values[mask]

    if len(T_fit) < 3:
        raise ValueError("Not enough data points to fit Arrhenius model.")

    popt, _ = curve_fit(arrhenius, T_fit, V_fit, maxfev=10000)
    fitted_values = arrhenius(temperatures, *popt)

    return fitted_values, popt


def fit_arrhenius_first_three(temperatures, values):
    """Fit Arrhenius on first 3 non-NaN points (low temperature extrapolation).

    Returns: (fitted_values, popt) where popt = [A, Ea]
    """
    temperatures = np.array(temperatures, dtype=float)
    values = np.array(values, dtype=float)

    mask = ~np.isnan(values)
    T_fit = temperatures[mask][:3]
    V_fit = values[mask][:3]

    if len(T_fit) < 3:
        raise ValueError("Not enough data points to fit Arrhenius model.")

    popt, _ = curve_fit(arrhenius, T_fit, V_fit, maxfev=10000)
    fitted_values = arrhenius(temperatures, *popt)

    return fitted_values, popt


def fit_arrhenius_last_three(temperatures, values):
    """Fit Arrhenius on last 3 non-NaN points (high temperature extrapolation).

    Returns: (fitted_values, popt) where popt = [A, Ea]
    """
    temperatures = np.array(temperatures, dtype=float)
    values = np.array(values, dtype=float)

    mask = ~np.isnan(values)
    T_fit = temperatures[mask][-3:]
    V_fit = values[mask][-3:]

    if len(T_fit) < 3:
        raise ValueError("Not enough data points to fit Arrhenius model.")

    popt, _ = curve_fit(arrhenius, T_fit, V_fit, maxfev=10000)
    fitted_values = arrhenius(temperatures, *popt)

    return fitted_values, popt


def dynamic_resampling(
    df,
    time_col,
    change_thresholds,
    min_interval_seconds=60
):
    """
    Dynamic resampling with:
    - Per-column change detection
    - Optional inclusion of the previous point on change
    - Forced keep every min_interval_seconds
    """
    df = df.copy()
    time = df[time_col].to_numpy()

    # --------- 1) SIGNIFICANT CHANGE MASKS ----------
    change_mask = np.zeros(len(df), dtype=bool)
    change_mask[0] = True  # always keep first

    prev_mask = np.zeros(len(df), dtype=bool)

    for col, cfg in change_thresholds.items():

        if col not in df.columns:
            continue

        threshold = cfg.get("threshold", None)
        include_prev = cfg.get("include_previous", False)

        if threshold is None:
            continue

        vals = df[col].to_numpy()
        delta = np.abs(vals[1:] - vals[:-1])

        # rows where change happens
        this_change = delta >= threshold

        # keep the change row
        change_mask[1:] |= this_change

        # optionally keep the previous row
        if include_prev:
            prev_mask[:-1] |= this_change

    significant_mask = change_mask | prev_mask

    # --------- 2) FORCED INTERVAL KEEP ----------
    dt = time - time[0]
    buckets = dt // min_interval_seconds

    forced_mask = np.zeros(len(df), dtype=bool)
    _, first_idx = np.unique(buckets, return_index=True)
    forced_mask[first_idx] = True

    # --------- 3) COMBINE ----------
    final_mask = significant_mask | forced_mask

    return df[final_mask].reset_index(drop=True)
