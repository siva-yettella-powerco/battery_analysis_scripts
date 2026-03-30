# TB_CPA_Harmonize_v2

Supplier-agnostic harmonization pipeline for battery cell test data.
Converts raw test files (Excel, CSV) from any supplier into a unified 16-column CSV schema — without any supplier detection logic.

---

## Quick Start

1. Set your data folder in [src/paths.py](src/paths.py):
   ```python
   base_path = Path(r"C:\your\data\folder")
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run:
   ```bash
   python harmonize_run.py
   ```

Output CSVs appear in `03_Harmonized_Data/`, mirroring the subfolder structure of `02_Extracted_Raw_Files/`.
A status JSON is written to `06_Logs/backend_base/`.

---

## How It Works

No supplier detection. The pipeline reads the file itself and figures out what it contains.

```
File
 │
 ├── FileInspector      → detects format, encoding, sheet, header row
 ├── ColumnMapper       → scores column names against keyword lists → assigns roles
 ├── OverrideLoader     → optional YAML patch for edge cases (runs before mapping)
 └── TransformEngine    → converts time, current sign, step names, capacity
      └── Harmonizer    → orchestrates everything → unified DataFrame
```

### Step 1 — FileInspector

Automatically detects:
- **Format**: `.xlsx`, `.xlsm`, `.xls` (binary), `.xls` (tab-separated text, MCM style), `.csv`
- **Encoding**: tries utf-8, iso-8859-1, cp1252 in order
- **Sheet**: picks the sheet with the most rows
- **Header row**: scores rows by string-label density; the densest row wins

### Step 2 — ColumnMapper

Scores every source column against keyword lists for each of the 16 target columns.
Three tiers:

| Tier | How matched | Score |
|------|-------------|-------|
| `keywords_exact` | lowercased name == keyword exactly | 1.0 |
| `keywords_high` | name starts-with keyword | 0.85 |
| `keywords_high` | name contains keyword | 0.70 |
| `keywords_med` | name starts-with keyword | 0.60 |
| `keywords_med` | name contains keyword | 0.50 |

Greedy one-to-one assignment (each source column used for at most one target).
Returns a `MappingResult` with `is_valid=True` only if all mandatory columns were found.

### Step 3 — TransformEngine

Handles format differences without branching on supplier:

| What | How |
|------|-----|
| **Time** | Detects format (`float_seconds`, `d_hms_ms`, `timedelta_pandas`, `datetime`) and converts to seconds |
| **Current sign** | Detects bipolar (±) or unipolar+state-column; normalises to discharge=negative |
| **Step names** | Maps raw values (`CCCVCharge`, `C`, `充电`, …) to `Charge / Discharge / Rest / Control` |
| **Capacity** | Detects `direct`, `split_ch_dch` (TRURON-style), or `cumulative`; resets per step |
| **Power** | Derived as `V × I` if not in source |
| **Unix_time** | Derived from `Date_time.timestamp()` |

---

## Output Schema (16 columns)

| Column | Unit | Mandatory | Notes |
|--------|------|-----------|-------|
| `Total_time_s` | s | ✓ | Elapsed seconds from start |
| `Date_time` | — | | Absolute datetime |
| `Unix_time` | s | | POSIX timestamp, always derived |
| `Voltage_V` | V | ✓ | |
| `Current_A` | A | ✓ | Discharge = negative |
| `Power_W` | W | | Derived if absent |
| `Capacity_step_Ah` | Ah | ✓ | Reset to 0 at each step start |
| `Energy_step_Wh` | Wh | | |
| `Step` | — | | Integer step index |
| `Step_name` | — | | `Charge / Discharge / Rest / Control` |
| `Cycle` | — | | Cycle index |
| `T_Cell_degC` | °C | | |
| `T_Anode_degC` | °C | | |
| `T_Cathode_degC` | °C | | |
| `T_Chamber_degC` | °C | | |
| `T_cold_degC` | °C | | |

Columns that are absent in the source file are omitted from the output (not filled with NaN columns).

---

## Run Options

Edit the top of [harmonize_run.py](harmonize_run.py):

```python
hm_skip_rerun = True          # skip files that already have an output CSV
hm_skip_rerun_except = []     # list of filename substrings to force-reprocess
OVERRIDE_DIR = Path('harmonize/overrides')  # set to None to disable overrides
```

---

## Adding Keywords for a New Column Format

If a supplier uses a column name not in the keyword lists, add it to [harmonize/column_registry.py](harmonize/column_registry.py). No other files need to change.

Example — a new supplier uses `"Zellspannung (V)"` for voltage:
```python
'Voltage_V': TargetColumnDef(
    ...
    keywords_exact=[..., 'zellspannung (v)'],   # add here
    ...
)
```

One line. No logic changes.

---

## Override YAMLs

For the 5–10% of files where auto-detection cannot resolve ambiguity, place a YAML file in `harmonize/overrides/`. The override is **additive** — it only patches the fields you specify; everything else is still auto-detected.

See [harmonize/overrides/examples/mcm_example.yaml](harmonize/overrides/examples/mcm_example.yaml) for a full reference.

**Minimal override** (force one column assignment):
```yaml
match_pattern: "*TRURON*.xlsx"
description: "Force capacity columns for TRURON split-charge format"

column_overrides:
  Capacity_step_Ah:
    source: "Charge Capacity (Ah)"
    capacity_convention: "split_ch_dch"
```

**Available override fields:**

| Field | What it does |
|-------|-------------|
| `match_pattern` | `fnmatch` pattern matched against the filename |
| `sheet` | Force a specific sheet name |
| `header_row` | Force header row number (1-based) |
| `column_overrides.<target>.source` | Force which source column maps to this target |
| `column_overrides.<target>.time_format` | Force time format: `float_seconds`, `d_hms_ms`, `timedelta_pandas`, `datetime` |
| `column_overrides.Current_A.direction_convention` | Force `bipolar` or `unipolar_with_state_col` |
| `column_overrides.Current_A.direction_state_col` | Column holding charge/discharge state |
| `column_overrides.Current_A.direction_discharge_vals` | List of values that mean "discharge" |
| `column_overrides.Capacity_step_Ah.capacity_convention` | Force `direct_signed`, `direct_unsigned`, `split_ch_dch`, `cumulative` |

---

## Stubs to Implement

Two complex time-reconstruction functions are left as stubs in [harmonize/transform_engine.py](harmonize/transform_engine.py). They raise `NotImplementedError` until you fill them in. You only need these if your files require combined step+test time logic or gap-corrected datetime.

**`TimeTransformer.build_total_time_from_step_plus_test()`**
```
MCM/SRF: use step_time as higher-resolution counter,
test_time for step boundary detection.
Cumsum of step_time deltas, corrected at each reset using test_time.
```

**`TimeTransformer.build_datetime_with_gap_correction()`**
```
MCM/SRF/GOTION/TRURON: base_datetime + rel_seconds.
Where (abs_time_delta - rel_time_delta) > 60s, a test pause occurred.
Add abs_time_delta at that index onward to rel_seconds before constructing datetime.
```

Both have docstrings with the full algorithm description.

---

## File Structure

```
TB_CPA_Harmonize_v2/
├── harmonize_run.py              ← entry point
├── requirements.txt
├── README.md                     ← this file
├── src/
│   ├── dependencies.py           ← shared imports
│   └── paths.py                  ← SET base_path HERE
└── harmonize/
    ├── column_registry.py        ← 16-column schema + keyword lists
    ├── file_inspector.py         ← format / encoding / sheet / header detection
    ├── column_mapper.py          ← scoring + greedy assignment → MappingResult
    ├── transform_engine.py       ← time / current / step / capacity transforms
    ├── harmonizer.py             ← orchestrator → HarmonizeResult
    └── overrides/
        ├── override_loader.py    ← YAML loading + merging
        └── examples/
            └── mcm_example.yaml  ← reference override
```

---

## Troubleshooting

**File skipped with "Mandatory columns not found"**
- Check the log for which columns were not mapped.
- Add the source column name to the relevant `keywords_exact` list in `column_registry.py`.
- Or create an override YAML with `column_overrides.<target>.source`.

**Time column wrong (all zeros, NaN, or nonsensical)**
- Check what format the raw column uses (float, `0d 08:47:57`, ISO datetime, …).
- Add a `time_format` hint in an override YAML.
- If the file uses combined step+test time: implement `build_total_time_from_step_plus_test()`.

**Current sign wrong (discharge appears positive)**
- Add an override with `direction_convention: unipolar_with_state_col` and specify `direction_state_col` and `direction_discharge_vals`.

**Capacity resets incorrectly between steps**
- Check the `capacity_convention` auto-detected value from the status JSON.
- Override with the correct convention if needed.

**Wrong sheet selected**
- Force with `sheet: "SheetName"` in an override YAML.

**Wrong header row**
- Force with `header_row: 3` in an override YAML.
