import numpy as np
import pandas as pd

from src.helpers import (
    is_within_range,
    closest_lower_number,
    closest_nth_higher_number,
    filter_by_proximity,
)


def calculate_SOC_reset_zero_full_dch(df_input, nominal_cap=215, max_cell_volt=3.8, min_cell_volt=2.5):
    df_in = df_input.copy()
    # calculate draft SOC based on Qstd updated for every C3 discharge - scaling adjustment
    df_in, c3_dch_steps, c3_cha_steps, all_c3_dch_steps, full_dch_steps = _calculate_SOC_draft_reset_dch_zero(df_in, nominal_cap, min_cell_volt)

    full_charge_steps = df_in.loc[(df_in['Voltage_V'] >= max_cell_volt) & (df_in['Current_A']<=nominal_cap/19),'Step_id'].unique()

    # Build a per-step offset map, then forward-fill by step order and subtract
    # in one vectorised pass instead of re-slicing the DataFrame per iteration.
    all_steps = df_in['Step_id'].unique()
    soc_last_by_step = df_in.groupby('Step_id')['SOC'].last()
    offset_map = {}
    for full_dch_step in full_dch_steps:
        reset_soc_step = closest_nth_higher_number(all_steps, full_dch_step, n=1)
        if reset_soc_step is not None:
            offset_map[reset_soc_step] = soc_last_by_step.loc[reset_soc_step]

    step_offsets = (
        pd.Series(offset_map, dtype=np.float64)
        .reindex(sorted(all_steps))
        .ffill()
        .fillna(0)
    )
    df_in['SOC_corrected'] = (df_in['SOC'] - df_in['Step_id'].map(step_offsets)).astype(np.float64)

    return df_in, full_charge_steps, c3_dch_steps, c3_cha_steps, all_c3_dch_steps, full_dch_steps


def _calculate_SOC_draft_reset_dch_zero(df_in, NOMINAL_CAPACITY, MIN_CELL_VOLT):
    temp_df = df_in.copy()

    # Compute all per-step aggregates in a single groupby pass instead of
    # repeated .loc[df['Step_id']==i, ...] calls inside list comprehensions.
    agg = temp_df.groupby('Step_id').agg(
        current_mean=('Current_A', 'mean'),
        current_median=('Current_A', 'median'),
        voltage_min=('Voltage_V', 'min'),
        cap_last=('Capacity_step_Ah', 'last'),
    )

    all_c3_dch_steps = agg.index[
        agg['current_mean'].apply(lambda m: is_within_range(m * 3, [-NOMINAL_CAPACITY * 0.9, -NOMINAL_CAPACITY * 1.1]))
    ].tolist()

    full_dch_steps = [
        i for i in all_c3_dch_steps
        if agg.loc[i, 'voltage_min'] <= (MIN_CELL_VOLT + 0.05)
        and agg.loc[i, 'current_mean'] < -NOMINAL_CAPACITY * 0.25
    ]

    c3_cha_steps = agg.index[
        agg.apply(lambda r: is_within_range(r['cap_last'], [NOMINAL_CAPACITY * 0.9, NOMINAL_CAPACITY * 1.1])
                            and is_within_range(r['current_median'] * 3, [NOMINAL_CAPACITY * 0.8, NOMINAL_CAPACITY * 1.1]),
                  axis=1)
    ].tolist()

    c3_cha_set = set(c3_cha_steps)
    # detecting RPT only C3 discharge steps
    c3_dch_steps = [
        i for i in all_c3_dch_steps
        if ((i + 2 in c3_cha_set) or (i + 3 in c3_cha_set))
        and is_within_range(agg.loc[i, 'cap_last'], [-NOMINAL_CAPACITY * 0.9, -NOMINAL_CAPACITY * 1.2])
    ]

    c3_dch_steps = filter_by_proximity(c3_dch_steps, threshold=8)

    # Build a step_id -> Q_std mapping, then assign with vectorised .map()
    # instead of looping with .loc[] writes per step.
    unique_steps = temp_df['Step_id'].unique()
    step_to_Qstd = {}
    for i in unique_steps:
        prev_std_dch_step = closest_lower_number(c3_dch_steps, i)
        ref = prev_std_dch_step if prev_std_dch_step is not None else c3_dch_steps[0]
        Q_std = -agg.loc[ref, 'cap_last']
        lo, hi = NOMINAL_CAPACITY * 0.8, NOMINAL_CAPACITY * 1.1
        if not is_within_range(Q_std, [lo, hi]):
            raise ValueError(
                f"Q_std out of expected range for step {i} (ref step {ref}): "
                f"Q_std={Q_std:.3f} Ah, expected [{lo:.1f}, {hi:.1f}] Ah "
                f"(nominal={NOMINAL_CAPACITY} Ah)"
            )
        step_to_Qstd[i] = Q_std

    temp_df['Q_std'] = temp_df['Step_id'].map(step_to_Qstd)
    temp_df['SOC'] = temp_df['Capacity_Ah'] * 100 / temp_df['Q_std']

    return temp_df, c3_dch_steps, c3_cha_steps, all_c3_dch_steps, full_dch_steps
