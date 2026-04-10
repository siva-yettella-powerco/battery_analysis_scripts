"""
table_interpolation.py

Interpolate NaN values in a 2D lookup table where:
  - rows    = SOC points  (index)
  - columns = temperature points

Two interpolation axes are supported:
  1. Temperature axis  – Arrhenius or linear fitting per SOC row
  2. SOC axis          – linear interpolation / extrapolation after temperature axis is done

Usage example
-------------
    from src.table_interpolation import interpolate_table

    filled_df = interpolate_table(
        df,
        method="arrhenius",          # "arrhenius" | "linear"
        exclude_temps=[],            # temperature columns to exclude from fitting
        n_neighbors=None,            # int or None (all points) for Arrhenius
        extrapolate=False,           # True = extrapolate outside temp range, False = clamp
        soc_extrapolate=False,       # True = extrapolate outside SOC range, False = clamp
        plot=True,                   # show per-SOC fitting plots
    )
"""

from __future__ import annotations

import warnings
from typing import Sequence

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from scipy.stats import pearsonr

# ─────────────────────────────────────────────────────────────────────────────
# Arrhenius model helpers
# ─────────────────────────────────────────────────────────────────────────────

_R = 8.314  # J mol⁻¹ K⁻¹


def _to_kelvin(t):
    """Assume temperatures ≤ 200 are in °C; convert to K."""
    arr = np.asarray(t, dtype=float)
    mask = arr < 200.0
    arr = np.where(mask, arr + 273.15, arr)
    return arr


def _arrhenius_model(T_K, A, Ea):
    """y = A * exp(-Ea / (R * T))"""
    return A * np.exp(-Ea / (_R * T_K))


def _fit_arrhenius(temps, values, n_neighbors, query_temps, extrapolate):
    """
    Fit an Arrhenius curve to (temps, values) and evaluate at query_temps.

    Parameters
    ----------
    temps        : 1-D array of known temperature points (°C or K)
    values       : 1-D array of known values (same length as temps)
    n_neighbors  : use only the n nearest known points around each query point
                   (None → use all points for a single global fit)
    query_temps  : temperatures at which to evaluate the fitted model
    extrapolate  : if False, clamp outside [min(temps), max(temps)]

    Returns
    -------
    result : 1-D array of interpolated values at query_temps
    """
    T_K = _to_kelvin(temps)
    q_K = _to_kelvin(query_temps)

    result = np.full(len(query_temps), np.nan)

    # ── global fit (n_neighbors is None) ────────────────────────────────────
    if n_neighbors is None:
        try:
            popt, _ = curve_fit(
                _arrhenius_model,
                T_K,
                values,
                p0=[values.mean() * np.exp(5000 / T_K.mean()), 5000.0],
                maxfev=10_000,
            )
            fitted = _arrhenius_model(q_K, *popt)
        except RuntimeError:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                coeffs = np.polyfit(1.0 / T_K, np.log(np.abs(values) + 1e-30), 1)
            fitted = np.exp(np.polyval(coeffs, 1.0 / q_K))

        if not extrapolate:
            lo, hi = temps.min(), temps.max()
            fitted = np.where(
                (query_temps < lo) | (query_temps > hi),
                np.interp(query_temps, temps, values),
                fitted,
            )
        result[:] = fitted
        return result

    # ── local fit using n nearest neighbours ────────────────────────────────
    for i, (qt, qK) in enumerate(zip(query_temps, q_K)):
        distances = np.abs(temps - qt)
        idx = np.argsort(distances)[:n_neighbors]
        t_local = T_K[idx]
        v_local = values[idx]

        if len(t_local) < 2:
            result[i] = v_local[0] if len(v_local) == 1 else np.nan
            continue

        in_range = temps.min() <= qt <= temps.max()

        if not extrapolate and not in_range:
            result[i] = values[np.argmin(np.abs(temps - qt))]
            continue

        try:
            popt, _ = curve_fit(
                _arrhenius_model,
                t_local,
                v_local,
                p0=[v_local.mean() * np.exp(5000 / t_local.mean()), 5000.0],
                maxfev=10_000,
            )
            result[i] = _arrhenius_model(qK, *popt)
        except RuntimeError:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                coeffs = np.polyfit(1.0 / t_local, np.log(np.abs(v_local) + 1e-30), 1)
            result[i] = np.exp(np.polyval(coeffs, 1.0 / qK))

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Linear temperature interpolation helper
# ─────────────────────────────────────────────────────────────────────────────

def _interp_linear_temp(temps, values, query_temps, extrapolate):
    """Linear interpolation along temperature axis."""
    if extrapolate:
        result = np.interp(query_temps, temps, values, left=np.nan, right=np.nan)
        lo_mask = query_temps < temps[0]
        if lo_mask.any() and len(temps) >= 2:
            slope = (values[1] - values[0]) / (temps[1] - temps[0])
            result[lo_mask] = values[0] + slope * (query_temps[lo_mask] - temps[0])
        hi_mask = query_temps > temps[-1]
        if hi_mask.any() and len(temps) >= 2:
            slope = (values[-1] - values[-2]) / (temps[-1] - temps[-2])
            result[hi_mask] = values[-1] + slope * (query_temps[hi_mask] - temps[-1])
    else:
        result = np.interp(query_temps, temps, values)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# SOC axis interpolation
# ─────────────────────────────────────────────────────────────────────────────

def _interp_along_soc(soc_values, column_data, soc_extrapolate):
    """
    Fill NaNs along a single temperature column using linear SOC interpolation.

    Parameters
    ----------
    soc_values      : full SOC axis
    column_data     : 1-D array of values (may contain NaN) at each SOC
    soc_extrapolate : whether to extrapolate beyond known SOC range

    Returns
    -------
    filled column_data
    """
    known_mask = ~np.isnan(column_data)
    if known_mask.sum() < 2:
        return column_data

    known_soc = soc_values[known_mask]
    known_val = column_data[known_mask]

    result = column_data.copy()
    nan_mask = np.isnan(column_data)

    if not nan_mask.any():
        return result

    q_soc = soc_values[nan_mask]

    if soc_extrapolate:
        interped = np.interp(q_soc, known_soc, known_val, left=np.nan, right=np.nan)
        lo = q_soc < known_soc[0]
        if lo.any() and len(known_soc) >= 2:
            slope = (known_val[1] - known_val[0]) / (known_soc[1] - known_soc[0])
            interped[lo] = known_val[0] + slope * (q_soc[lo] - known_soc[0])
        hi = q_soc > known_soc[-1]
        if hi.any() and len(known_soc) >= 2:
            slope = (known_val[-1] - known_val[-2]) / (known_soc[-1] - known_soc[-2])
            interped[hi] = known_val[-1] + slope * (q_soc[hi] - known_soc[-1])
    else:
        interped = np.interp(q_soc, known_soc, known_val)

    result[nan_mask] = interped
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Plotting helpers
# ─────────────────────────────────────────────────────────────────────────────

def _plot_soc_row(soc, all_temps, original_row, filled_row, method, exclude_temps, n_neighbors, extrapolate):
    """Plot fitting curve, original, and interpolated points for one SOC row."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        warnings.warn("matplotlib is not installed – skipping plots.")
        return

    known_mask = (
        ~np.isnan(original_row)
        & ~np.isin(all_temps, exclude_temps)
    )
    interp_mask = np.isnan(original_row) & ~np.isnan(filled_row)

    if known_mask.sum() >= 2:
        t_smooth = np.linspace(all_temps.min(), all_temps.max(), 300)
        known_t = all_temps[known_mask]
        known_v = original_row[known_mask]

        if method == "arrhenius":
            smooth_v = _fit_arrhenius(known_t, known_v, n_neighbors, t_smooth, extrapolate=True)
        else:
            smooth_v = _interp_linear_temp(known_t, known_v, t_smooth, extrapolate=True)
    else:
        t_smooth = np.array([])
        smooth_v = np.array([])

    fig, ax = plt.subplots(figsize=(8, 4))

    if len(t_smooth):
        ax.plot(t_smooth, smooth_v, "b-", lw=1.5, label="fit / interpolant")

    ax.scatter(all_temps[known_mask], original_row[known_mask], color="green", zorder=5, s=60, label="original known")

    if interp_mask.any():
        ax.scatter(all_temps[interp_mask], filled_row[interp_mask], color="red", marker="x", zorder=6, s=80, lw=2, label="interpolated / extrapolated")

        excluded_known_mask = (~np.isnan(original_row) & np.isin(all_temps, exclude_temps))
        ax.scatter(all_temps[excluded_known_mask], original_row[excluded_known_mask], color="orange", marker="s", s=50, label="excluded from fit")

    if exclude_temps:
        excl_arr = np.array(exclude_temps, dtype=float)
        excl_in_range = excl_arr[(excl_arr >= all_temps.min()) & (excl_arr <= all_temps.max())]
        for et in excl_in_range:
            ax.axvline(et, color="gray", ls="--", lw=0.8, alpha=0.6)

    ax.set_xlabel("Temperature (°C or K)")
    ax.set_ylabel("Value")
    ax.set_title(
        f"SOC = {soc:.4g}  |  method = {method}"
        + (f"  |  n_neighbors = {n_neighbors}" if n_neighbors else "")
    )
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


# ─────────────────────────────────────────────────────────────────────────────
# Main public functions
# ─────────────────────────────────────────────────────────────────────────────

def interpolate_table(
    df: pd.DataFrame,
    method: str = "arrhenius",
    exclude_temps=None,
    n_neighbors=None,
    extrapolate: bool = False,
    soc_extrapolate: bool = False,
    plot: bool = False,
) -> pd.DataFrame:
    """
    Fill NaN values in a SOC × Temperature lookup table.

    The function works in two passes:
      1. Temperature axis – for each SOC row, use available temperature
         columns to fit and fill missing temperature columns.
      2. SOC axis – for each temperature column still containing NaNs,
         interpolate linearly across SOC.

    Parameters
    ----------
    df              : DataFrame with SOC as index, temperature values as columns.
    method          : "arrhenius" or "linear"
    exclude_temps   : Temperature columns to exclude from fitting (treated as targets).
    n_neighbors     : Arrhenius only. None = global fit; int = local n-nearest fit.
    extrapolate     : Temperature axis extrapolation beyond known range.
    soc_extrapolate : SOC axis extrapolation beyond known range.
    plot            : Show per-SOC matplotlib fitting plots.

    Returns
    -------
    pd.DataFrame with NaN values filled where possible.
    """
    if method not in ("arrhenius", "linear"):
        raise ValueError(f"method must be 'arrhenius' or 'linear', got '{method}'")

    exclude_temps = list(exclude_temps) if exclude_temps else []

    result = df.copy().astype(float)
    all_temps = np.array(result.columns, dtype=float)
    soc_index = np.array(result.index, dtype=float)

    # ── Pass 1: interpolate along temperature axis row by row ────────────────
    for soc, row in result.iterrows():
        original_row = row.values.copy()

        fit_mask = ~np.isnan(original_row) & ~np.isin(all_temps, exclude_temps)

        if fit_mask.sum() < 2:
            continue

        fill_mask = np.isnan(original_row)

        if not fill_mask.any():
            continue

        fit_temps = all_temps[fit_mask]
        fit_vals = original_row[fit_mask]
        query_temps = all_temps[fill_mask]

        if method == "arrhenius":
            interped = _fit_arrhenius(fit_temps, fit_vals, n_neighbors, query_temps, extrapolate)
        else:
            interped = _interp_linear_temp(fit_temps, fit_vals, query_temps, extrapolate)

        filled_row = original_row.copy()
        filled_row[fill_mask] = interped
        result.loc[soc] = filled_row

        if plot:
            _plot_soc_row(
                soc=soc,
                all_temps=all_temps,
                original_row=original_row,
                filled_row=filled_row,
                method=method,
                exclude_temps=exclude_temps,
                n_neighbors=n_neighbors,
                extrapolate=extrapolate,
            )

    # ── Pass 2: interpolate along SOC axis column by column ──────────────────
    for col_temp in result.columns:
        col = result[col_temp].values.copy()
        if not np.isnan(col).any():
            continue
        filled_col = _interp_along_soc(soc_index, col, soc_extrapolate)
        result[col_temp] = filled_col

    result.columns = result.columns.astype(float)

    return result


def query_table(
    df: pd.DataFrame,
    new_socs,
    new_temps,
    method: str = "arrhenius",
    exclude_temps=None,
    n_neighbors=None,
    extrapolate: bool = False,
    soc_extrapolate: bool = False,
    plot: bool = False,
) -> pd.DataFrame:
    """
    Evaluate a SOC × Temperature lookup table at arbitrary new SOC
    and temperature points by expanding the grid and reusing interpolate_table.
    """
    new_soc_arr = np.asarray(new_socs, dtype=float)
    new_temps_arr = np.asarray(new_temps, dtype=float)

    all_soc = np.unique(np.concatenate([df.index.astype(float), new_soc_arr]))
    all_temps = np.unique(np.concatenate([df.columns.astype(float), new_temps_arr]))

    all_soc.sort()
    all_temps.sort()

    if max(new_soc_arr) > max(df.index) * 10:
        print(f"Warning: Check input: new_socs values scaling: \nTable's SOC range <{min(df.index)} to {max(df.index)}>, while new SOCs are {new_socs}")
    elif max(new_soc_arr) * 10 < max(df.index):
        print(f"Warning: Check input: new_socs values scaling: \nTable's SOC range <{min(df.index)} to {max(df.index)}>, while new SOCs are {new_socs}")

    expanded = df.astype(float).reindex(index=all_soc, columns=all_temps)

    filled = interpolate_table(
        expanded,
        method=method,
        exclude_temps=exclude_temps,
        n_neighbors=n_neighbors,
        extrapolate=extrapolate,
        soc_extrapolate=soc_extrapolate,
        plot=plot,
    )

    out = filled.loc[new_soc_arr, new_temps_arr]
    out.index.name = df.index.name or "SOC"
    out.columns.name = df.columns.name
    out = out.sort_index(axis=0, ascending=False).sort_index(axis=1)

    return out
