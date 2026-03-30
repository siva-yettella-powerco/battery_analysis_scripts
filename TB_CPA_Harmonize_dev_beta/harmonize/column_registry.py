"""
column_registry.py
------------------
Defines the 16 target columns for the unified harmonized schema.
Each column has keyword lists at three confidence tiers (exact / high / med).
ColumnMapper uses these to score source columns from raw data.

Tier semantics
--------------
keywords_exact  → full lowercased name must equal keyword        → score 1.0
keywords_high   → lowercased name starts-with OR contains kw    → score 0.8 / 0.7
keywords_med    → lowercased name contains kw (weaker signal)   → score 0.5
"""

from dataclasses import dataclass, field


@dataclass
class TargetColumnDef:
    name: str
    mandatory: bool = False
    derived: bool = False          # True → can be computed if source absent
    dtype_hint: str = 'float'      # 'float', 'int', 'datetime', 'time', 'string'
    keywords_exact: list = field(default_factory=list)
    keywords_high: list = field(default_factory=list)
    keywords_med: list = field(default_factory=list)


COLUMN_REGISTRY: dict[str, TargetColumnDef] = {

    # ── Mandatory columns ──────────────────────────────────────────────────────

    'Total_time_s': TargetColumnDef(
        name='Total_time_s',
        mandatory=True,
        dtype_hint='time',
        keywords_exact=['test time', 'totaltime(s)', 'total time(s)', 'time(s)',
                        'rel.time(s)', 'relative time(s)', 'elapsed time(s)',
                        'testtime', 'test_time', 'time_s', 'total_time_s',
                        'totaltime_s', 'relative_time_s', 'elapsed_time_s'],
        keywords_high=['test time', 'totaltime', 'total time', 'rel.time',
                       'relative time', 'elapsed time', 'step time', 'time_s',
                       'time'],
        keywords_med=['zeit', 'temps', 'tiempo', 'zeit(s)'],
    ),

    'Voltage_V': TargetColumnDef(
        name='Voltage_V',
        mandatory=True,
        dtype_hint='float',
        keywords_exact=['voltage(v)', 'voltage [v]', 'u(v)', 'v(v)',
                        'cell voltage(v)', 'cell voltage [v]', 'volt(v)', 'voltage_v'],
        keywords_high=['voltage', 'volt', 'u(v)', 'v(v)', 'cell volt',
                       'spannung', 'tension', 'u [v]', 'v [v]'],
        keywords_med=['spann', 'tens', 'vdc'],
    ),

    'Current_A': TargetColumnDef(
        name='Current_A',
        mandatory=True,
        dtype_hint='float',
        keywords_exact=['current(a)', 'current [a]', 'i(a)', 'i [a]',
                        'current_a', 'amps', 'ampere'],
        keywords_high=['current', 'i(a)', 'i [a]', 'strom', 'courant',
                       'current [a]', 'charge current', 'discharge current'],
        keywords_med=['amp', 'stro', 'cour'],
    ),

    'Capacity_step_Ah': TargetColumnDef(
        name='Capacity_step_Ah',
        mandatory=True,
        dtype_hint='float',
        keywords_exact=['capacity(ah)', 'capacity [ah]', 'cap(ah)', 'q(ah)',
                        'step capacity(ah)', 'charge capacity(ah)',
                        'discharge capacity(ah)', 'capacity_ah',
                        'step_capacity_ah', 'step capacity ah',
                        'stepcapacity(ah)', 'stepcap(ah)'],
        keywords_high=['step capacity', 'step_capacity', 'step cap',
                       'capacity', 'cap', 'q(ah)', 'ah',
                       'kapazität', 'capacite'],
        keywords_med=['kapa', 'capa', 'cap.'],
    ),

    'Step_name': TargetColumnDef(
        name='Step_name',
        mandatory=False,   # Not mandatory: Harmonizer infers from Current_A if absent
        dtype_hint='string',
        keywords_exact=['step name', 'stepname', 'step type', 'steptype',
                        'state', 'mode', 'status', 'charge state', 'md',
                        'step_name', 'step_type'],
        keywords_high=['step name', 'step type', 'state', 'mode', 'status',
                       'charge state', 'step mode', 'operation'],
        keywords_med=['typ', 'modus', 'schritt'],
    ),

    # ── Important optional columns ─────────────────────────────────────────────

    'Date_time': TargetColumnDef(
        name='Date_time',
        mandatory=False,
        dtype_hint='datetime',
        keywords_exact=['date', 'datetime', 'date_time', 'absolute time',
                        'absolutetime', 'dpt time', 'timestamp', 'date time',
                        'abs time', 'abs.time', 'date/time'],
        keywords_high=['date', 'absolute time', 'dpt time', 'timestamp',
                       'abs time', 'datum', 'date/time', 'datetime'],
        keywords_med=['zeit', 'time stamp', 'horodatage'],
    ),

    'Step': TargetColumnDef(
        name='Step',
        mandatory=False,
        dtype_hint='int',
        keywords_exact=['step', 'step index', 'step id', 'step number',
                        'stepindex', 'stepnum', 'step_index', 'step_id',
                        'step no', 'step no.'],
        keywords_high=['step index', 'step id', 'step number', 'step num',
                       'stepindex', 'step no'],
        keywords_med=['schritt', 'etape', 'paso'],
    ),

    'Cycle': TargetColumnDef(
        name='Cycle',
        mandatory=False,
        dtype_hint='int',
        keywords_exact=['cycle', 'cycle number', 'cycle index', 'cycle no',
                        'cycle_number', 'cycle_index', 'cycleindex', 'zyklen'],
        keywords_high=['cycle number', 'cycle index', 'cycle no', 'zyklen',
                       'cycle count', 'cycle'],
        keywords_med=['zyk', 'cycl', 'cycle'],
    ),

    # ── Temperature columns ────────────────────────────────────────────────────

    'T_Cell_degC': TargetColumnDef(
        name='T_Cell_degC',
        mandatory=False,
        dtype_hint='float',
        keywords_exact=['cell temp(°c)', 'cell temperature(°c)', 't cell(°c)',
                        'temperature(°c)', 'temp(°c)', 'aux4', 't(°c)',
                        't_cell', 'cell_temp'],
        keywords_high=['cell temp', 'cell temperature', 'temperature', 'temp',
                       'aux4', 't(°c)', 't cell', 'zelltemperatur'],
        keywords_med=['temp', 'therm', 'degc', '°c'],
    ),

    'T_Anode_degC': TargetColumnDef(
        name='T_Anode_degC',
        mandatory=False,
        dtype_hint='float',
        keywords_exact=['anode temp(°c)', 'anode temperature(°c)', 'aux2',
                        't2(°c)', 't_anode', 'anode_temp'],
        keywords_high=['anode temp', 'anode temperature', 'aux2', 't2',
                       't anode'],
        keywords_med=['anode', 't2'],
    ),

    'T_Cathode_degC': TargetColumnDef(
        name='T_Cathode_degC',
        mandatory=False,
        dtype_hint='float',
        keywords_exact=['cathode temp(°c)', 'cathode temperature(°c)', 'aux1',
                        't1(°c)', 't_cathode', 'cathode_temp'],
        keywords_high=['cathode temp', 'cathode temperature', 'aux1', 't1',
                       't cathode'],
        keywords_med=['cathode', 't1'],
    ),

    'T_Chamber_degC': TargetColumnDef(
        name='T_Chamber_degC',
        mandatory=False,
        dtype_hint='float',
        keywords_exact=['chamber temp(°c)', 'chamber temperature(°c)',
                        'temperboxtemppv(°c)', 'temper box(°c)', 'aux5',
                        't5(°c)', 't_chamber', 'chamber_temp'],
        keywords_high=['chamber temp', 'temperboxtemppv', 'temper box', 'aux5',
                       't5', 'klimakammer', 'climate chamber', 'environment temp'],
        keywords_med=['chamber', 'klimak', 'kammer'],
    ),

    'T_cold_degC': TargetColumnDef(
        name='T_cold_degC',
        mandatory=False,
        dtype_hint='float',
        keywords_exact=['cold spot(°c)', 'cold temp(°c)', 'aux6', 't6(°c)',
                        't4(°c)', 't_cold', 'cold_spot'],
        keywords_high=['cold spot', 'cold temp', 'aux6', 't6', 't4',
                       'cold plate', 'cold surface'],
        keywords_med=['cold', 'kalt', 'froid'],
    ),

    # ── Derived columns ────────────────────────────────────────────────────────

    'Energy_step_Wh': TargetColumnDef(
        name='Energy_step_Wh',
        mandatory=False,
        derived=False,             # source col preferred; fallback: integrate V*I
        dtype_hint='float',
        keywords_exact=['energy(wh)', 'energy [wh]', 'e(wh)', 'energie(wh)',
                        'step energy(wh)', 'energy_wh'],
        keywords_high=['energy', 'energie', 'wh', 'e(wh)', 'step energy'],
        keywords_med=['ener', 'joule', 'wh'],
    ),

    'Power_W': TargetColumnDef(
        name='Power_W',
        mandatory=False,
        derived=True,              # always computable as V * I
        dtype_hint='float',
        keywords_exact=['power(w)', 'power [w]', 'p(w)', 'watt', 'power_w'],
        keywords_high=['power', 'watt', 'p(w)', 'leistung', 'puissance'],
        keywords_med=['pwr', 'leist'],
    ),

    'Unix_time': TargetColumnDef(
        name='Unix_time',
        mandatory=False,
        derived=True,              # always derived from Date_time
        dtype_hint='float',
        keywords_exact=[],         # no source column; always computed
        keywords_high=[],
        keywords_med=[],
    ),
}


# Ordered list for output CSV (the 16-column standard schema)
FOCUS_COLS: list[str] = [
    'Total_time_s',
    'Date_time',
    'Unix_time',
    'Voltage_V',
    'Current_A',
    'Power_W',
    'Capacity_step_Ah',
    'Energy_step_Wh',
    'Step',
    'Step_name',
    'Cycle',
    'T_Cell_degC',
    'T_Anode_degC',
    'T_Cathode_degC',
    'T_Chamber_degC',
    'T_cold_degC',
]

MANDATORY_COLS: list[str] = [
    col for col, defn in COLUMN_REGISTRY.items() if defn.mandatory
]

# Columns that are always derived — never assigned from source
ALWAYS_DERIVED_COLS: list[str] = ['Unix_time']

# Columns that are derived but can also come from a source col
OPTIONALLY_DERIVED_COLS: list[str] = ['Power_W']
