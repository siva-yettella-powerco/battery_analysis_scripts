# Architecture — TB_CPA_Harmonize_v2

---

## The Big Picture

The old pipeline asked **"which supplier is this?"** and branched on the answer.
This pipeline asks **"what is in this file?"** and figures it out from the data.

```
Raw file (any supplier, any format)
        │
        ▼
┌─────────────────┐
│  FileInspector  │  ── "What kind of file is this, and where is the data?"
└────────┬────────┘
         │  raw DataFrame (all strings, no header applied yet)
         ▼
┌─────────────────┐     ┌──────────────────┐
│  OverrideLoader │ ──▶ │  (YAML patches)  │  ── optional, per filename
└────────┬────────┘     └──────────────────┘
         │  overrides dict  (may be empty)
         ▼
┌─────────────────┐
│  ColumnMapper   │  ── "Which source column plays which role?"
└────────┬────────┘
         │  MappingResult  {target → source, confidence}
         ▼
┌─────────────────────────────────────────────┐
│                TransformEngine              │  ── "How do I convert each role?"
│  ┌──────────────────┐ ┌───────────────────┐ │
│  │ TimeFormatDet.   │ │ CurrentDirectionH.│ │
│  │ TimeTransformer  │ │ StepNameNorm.     │ │
│  │                  │ │ CapacityTransform.│ │
│  └──────────────────┘ └───────────────────┘ │
│  ┌──────────────────┐                        │
│  │ DerivedColumns   │  Power = V×I           │
│  │ Calculator       │  Unix_time = timestamp │
│  └──────────────────┘                        │
└────────┬────────────────────────────────────┘
         │  unified DataFrame (up to 16 columns)
         ▼
┌─────────────────┐
│   Harmonizer    │  ── orchestrates all of the above; returns HarmonizeResult
└────────┬────────┘
         │
         ▼
  harmonize_run.py  ── loops over files, exports CSV, writes status JSON
```

---

## Module Map

```
TB_CPA_Harmonize_v2/
│
├── harmonize_run.py          ENTRY POINT
│                             Discovers files, calls Harmonizer.run(), exports CSV.
│
├── src/
│   ├── paths.py              Folder paths. SET base_path HERE.
│   └── dependencies.py       Shared imports (pandas, pathlib, logging, …)
│
└── harmonize/
    │
    ├── column_registry.py    THE KNOWLEDGE BASE
    │                         Defines the 16 target columns.
    │                         Each column has three tiers of keywords:
    │                           exact / high / med
    │                         Only file you edit to support a new column name.
    │
    ├── file_inspector.py     STAGE 1 — File Loading
    │                         FileInspector class.
    │                         Detects format → loads sheets → picks best sheet
    │                         → finds header row → returns clean DataFrame.
    │
    ├── column_mapper.py      STAGE 2 — Column Role Assignment
    │                         ColumnMapper class + MappingResult dataclass.
    │                         Scores every source column against column_registry.
    │                         Greedy 1:1 assignment. Returns MappingResult.
    │
    ├── transform_engine.py   STAGE 3 — Data Conversion
    │                         Five classes, each responsible for one data type:
    │                           TimeFormatDetector
    │                           TimeTransformer
    │                           CurrentDirectionHandler
    │                           StepNameNormalizer
    │                           CapacityTransformer
    │                           DerivedColumnsCalculator
    │
    ├── harmonizer.py         ORCHESTRATOR
    │                         Harmonizer class + HarmonizeResult dataclass.
    │                         Calls the four stages in order.
    │                         Builds the unified DataFrame.
    │                         Returns HarmonizeResult.
    │
    └── overrides/
        ├── override_loader.py    YAML Loading + Merging
        │                         Loads all *.yaml from the overrides folder.
        │                         Matches by filename pattern.
        │                         Patches MappingResult additively.
        │
        └── examples/
            └── mcm_example.yaml  Reference override for MCM-format files.
```

---

## Stage 1 — FileInspector

**Input:** file path
**Output:** `(DataFrame with string values, inspection_report dict)`

```
filepath
    │
    ├── detect_file_format()      xlsx / xls_binary / xls_tab / csv
    │       suffix + first 8 bytes (OLE2 magic for .xls)
    │
    ├── _load_all_sheets()        returns dict {sheet_name: raw_df}
    │       Excel → pd.read_excel(header=None, dtype=str)
    │       xls_tab → pd.read_csv(sep='\t')      MCM .xls text format
    │       csv → pd.read_csv(comment='#')        skip metadata comment rows
    │
    ├── detect_data_sheet()       picks sheet with most rows
    │
    └── detect_header_row()       scores rows by string-label density
            score = n_string_labels × (n_string_labels / n_non_empty)
            row with highest score = header
            → returns 1-based row index
```

**Override hooks:**
- `sheet` → skip sheet detection, use named sheet directly
- `header_row` → skip header detection, use fixed row number

---

## Stage 2 — ColumnMapper

**Input:** DataFrame (or column list), optional overrides dict
**Output:** `MappingResult`

```
source columns  ──┐
                  ├──► normalise()  lowercase + collapse whitespace
                  │
column_registry ──┤
                  ├──► _score(source_norm, target_def)
                  │        exact match   → 1.0
                  │        starts-with high keyword → 0.85
                  │        contains high keyword    → 0.70
                  │        starts-with med keyword  → 0.60
                  │        contains med keyword     → 0.50
                  │
                  ├──► apply forced overrides (confidence = 1.0)
                  │
                  └──► greedy assignment
                           sort all (target, source, score) descending
                           assign if neither target nor source already taken
                           threshold: 0.3 mandatory / 0.4 optional
```

`MappingResult` fields:
```
column_map       {target: source}      the final assignments
confidence       {target: 0.0–1.0}     score of each assignment
unmatched_targets  mandatory cols that had no match above threshold
unmatched_sources  source cols that weren't assigned to any target
is_valid           True if all mandatory cols found
notes              log of override actions and warnings
```

---

## Stage 3 — TransformEngine

Five independent classes. Each knows one thing.

### TimeFormatDetector

Inspects a sample of 20 values and returns one of:

| Format string | Looks like | Examples |
|---------------|-----------|---------|
| `float_seconds` | numeric | `0.0`, `1.88`, `3600.5` |
| `d_hms_ms` | days.hh:mm:ss | `0.00:00:01.062`, `0d 08:47:57.31` |
| `timedelta_pandas` | pandas timedelta string | `0 days 00:01:30.000000000` |
| `datetime` | ISO datetime | `2025-01-15 10:00:00` |
| `unknown` | could not determine | — |

Detection order: float → d_hms_ms → timedelta → datetime

### TimeTransformer

Converts any detected format to **total seconds** (starting from 0) or **datetime**.

```
'float_seconds'    → as-is, subtract first value
'd_hms_ms'         → parse_d_hms_ms() → timedelta → .dt.total_seconds()
'timedelta_pandas' → pd.to_timedelta() → .dt.total_seconds()
'datetime'         → (dt - dt.iloc[0]).dt.total_seconds()
```

Two methods are **stubs** — implement them for MCM/SRF complex time logic:
- `build_total_time_from_step_plus_test()` — combined step+test time
- `build_datetime_with_gap_correction()` — gap-corrected absolute datetime

### CurrentDirectionHandler

```
detect(df, current_col)
    │
    ├── both + and − present?  ──YES──► 'bipolar'  (no state column needed)
    │
    └── all positive (or all negative)?
            │
            └── find_state_column()
                    low-cardinality string column where at least one value
                    matches known charge/discharge keywords
                    ──FOUND──► 'unipolar_with_state_col'
                    ──NOT FOUND──► 'unknown'

normalize(convention, state_col)
    'bipolar'                → return as-is
    'unipolar_with_state_col'→ multiply by -1 where state_col ∈ discharge_vals
```

### StepNameNormalizer

Maps raw step name values to four canonical labels using regex patterns:

```
Charge    ← charge, cccharge, cccvcharge, C, ch, 充电, laden, …
Discharge ← discharge, ccdischarge, D, dch, 放电, entladen, …
Rest      ← rest, R, ocp, 静置, pause, relaxation, …
Control   ← control, controlstep, formation, O, …
```

If no `Step_name` source column is found, `infer_from_current()` is used:
```
current > 0  → Charge
current < 0  → Discharge
current = 0  → Rest
```

### CapacityTransformer

```
detect_convention(df, cap_col, step_col)
    ├── both "charge cap" and "discharge cap" columns exist?  → 'split_ch_dch'
    ├── values monotonically increase across test?            → 'cumulative'
    ├── values can be negative?                               → 'direct_signed'
    └── default                                               → 'direct_unsigned'

compute_step_capacity(convention, ...)
    'direct_signed'    → return cap_col as-is, subtract step start
    'direct_unsigned'  → same, always positive
    'split_ch_dch'     → (charge_cap - ch_start) - (discharge_cap - dch_start)  per step
    'cumulative'       → diff within each step, cumsum
```

### DerivedColumnsCalculator

```
calc_power(df)     → df['Voltage_V'] × df['Current_A']
calc_unix_time(df) → df['Date_time'].apply(x.timestamp())
```

Both run after all source-column transforms are done.

---

## The Orchestrator — Harmonizer

```python
result = Harmonizer(override_dir=...).run(filepath)
```

Internal sequence:

```
1. FileInspector.load_data()
        → raw DataFrame + inspection report

2. OverrideLoader.match(filepath)
        → override dict (empty if no YAML matches)

3. Apply forced sheet / header_row from override
        → may reload file with specific sheet

4. ColumnMapper.map(df, overrides)
        → MappingResult
        → if not is_valid: return HarmonizeResult(is_valid=False)

5. _build_unified(data, mapping, override)
        a. Direct column copies (Step, Cycle, temperatures, Energy)
        b. Total_time_s  ── TimeFormatDetector + TimeTransformer
        c. Date_time     ── TimeFormatDetector + TimeTransformer
        d. Current_A     ── CurrentDirectionHandler
        e. Step_name     ── StepNameNormalizer (or infer from Current_A)
        f. Capacity_step_Ah ── CapacityTransformer
        g. Power_W       ── DerivedColumnsCalculator (if not in source)
        h. Unix_time     ── DerivedColumnsCalculator (always derived)
        i. Reorder to FOCUS_COLS order

6. Validate: all mandatory cols present and non-empty?

7. Return HarmonizeResult
```

`HarmonizeResult` fields:
```
data           unified DataFrame (or None on failure)
filepath       source file path
is_valid       True if all mandatory cols have data
inspection     FileInspector report
mapping        MappingResult from ColumnMapper
warnings       recoverable issues (non-fatal)
errors         fatal issues (file was skipped)
```

---

## Override System

Overrides are **additive patches** — they supplement auto-detection, never replace it.

```
harmonize/overrides/
    my_supplier.yaml     ← match_pattern: "*SUPPLIER*_FC*.xlsx"
    another.yaml         ← match_pattern: "DQ_*.xlsx"
    examples/
        mcm_example.yaml
```

At runtime, `OverrideLoader` scans all `*.yaml` files once on startup.
For each file, `match(filepath)` returns the first YAML whose `match_pattern` matches the filename using `fnmatch`.

The override dict flows into both `ColumnMapper` (forces source assignments) and `_build_unified` (forces time_format, direction_convention, capacity_convention).

**Decision flow with overrides:**

```
Auto-detect column → Override forces column?
                          YES → use override (confidence = 1.0)
                          NO  → use auto-detected assignment

Auto-detect time_format → Override specifies time_format?
                               YES → use override hint
                               NO  → use TimeFormatDetector result

Auto-detect direction → Override specifies direction_convention?
                             YES → use override, find state_col from override
                             NO  → use CurrentDirectionHandler.detect()
```

---

## Data Flow for a Single Column

Example: `Total_time_s` for an MCM file with `Test Time` column in `0d 08:47:57.31` format.

```
Raw file
   "Test Time" column → ['0.00:00:01.062', '0.00:00:02.988', …]
        │
        ▼ FileInspector (dtype=str, no conversion)
   Series of strings
        │
        ▼ ColumnMapper
   keywords_exact match: 'test time' == 'test time' → confidence 1.0
   MappingResult: Total_time_s ← 'Test Time'
        │
        ▼ TimeFormatDetector.detect()
   sample matches pattern ^\d+[d\.]\d{2}:\d{2} → 'd_hms_ms'
        │
        ▼ TimeTransformer.to_total_seconds(fmt='d_hms_ms')
   _parse_d_hms_ms(): '0.00:00:01.062' → Timedelta(seconds=1.062)
   .dt.total_seconds() → [1.062, 2.988, …]
   subtract first value → [0.0, 1.926, …]
        │
        ▼ df['Total_time_s'] = [0.0, 1.926, …]
```

---

## What Is Hardcoded vs. Data-Driven

| Concern | Where decided | How to change |
|---------|--------------|---------------|
| Column name → role | `column_registry.py` keywords | Add keyword, one line |
| Time format | `TimeFormatDetector` auto-detect | Override YAML `time_format` |
| Current sign | `CurrentDirectionHandler` auto-detect | Override YAML `direction_*` |
| Step names | `StepNameNormalizer` regex patterns | Edit patterns in `transform_engine.py` |
| Capacity layout | `CapacityTransformer` auto-detect | Override YAML `capacity_convention` |
| Sheet selection | Largest sheet by row count | Override YAML `sheet` |
| Header row | String-label density heuristic | Override YAML `header_row` |
| Which file to use | `fnmatch` pattern on filename | Override YAML `match_pattern` |

Nothing is hardcoded to a supplier name. Adding a new supplier means:
1. Run the pipeline → check status JSON for unmatched columns
2. Add missing column names to `column_registry.py` (if keywords don't cover them)
3. Create an override YAML if time/current/capacity logic can't be auto-detected

---

## Separation of Concerns

```
column_registry.py   KNOWS what columns exist and what they're called
file_inspector.py    KNOWS how to open files and find data
column_mapper.py     KNOWS how to assign roles to columns  (no data transformation)
transform_engine.py  KNOWS how to convert data              (no column assignment)
harmonizer.py        KNOWS the order of operations          (no data knowledge)
override_loader.py   KNOWS how to patch the above           (no business logic)
harmonize_run.py     KNOWS file paths and batch iteration   (no harmonization logic)
```

Each module has one job. You can test and modify them independently.
