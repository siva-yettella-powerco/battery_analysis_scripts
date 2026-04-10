# TB_CPA_Evaluate — Design Decisions

> Last updated: 2026-04-10 (performance optimisations applied to src/)
> Add an entry whenever a non-obvious design choice is made or changed.
> Format: **Decision** → **Rationale** → **Trade-offs**

---

## Source Functions Copied from `basic_evaluation_cop` — Now Intentionally Diverged for Performance

**Decision:** Functions in `src/` were originally copied verbatim from
`basic_evaluation_cop/01_Support_functions/` (import paths adjusted only).
As of 2026-04-10, several functions have been **intentionally rewritten** in this repo
for performance while keeping identical public signatures and return values:

| Function | File | Change |
|----------|------|--------|
| `fix_capacity_counting` | cleaning.py | `groupby` iteration instead of repeated `.loc[]` per step |
| `_calculate_SOC_draft_reset_dch_zero` | soc_calculations.py | `groupby.agg()` + `.map()` instead of per-step `.loc[]` |
| `calculate_SOC_reset_zero_full_dch` (SOC correction) | soc_calculations.py | offset map + `ffill` + vectorised subtract |
| `read_harm_cell_data` | data_io.py | collect-then-concat instead of incremental `pd.concat` loop |
| `_preclean` (internal) | data_io.py | single `.map()` pass instead of two chained `.apply/.map` |

**Rationale:** Battery test DataFrames can have millions of rows and hundreds of Step IDs.
The original pattern — `for id in df['Step_id'].unique(): df.loc[df['Step_id']==id, ...]` —
is O(M×N) per function call. On large datasets this caused multi-minute runtimes per cell.
Replacing with `groupby` aggregates (computed once) and vectorised column assignments (`.map()`)
reduces the dominant operations to O(N).

**Trade-offs:**
- These functions now diverge from `basic_evaluation_cop`. Any bug fixes or logic changes
  in the originals must be ported manually and adapted to the vectorised form.
- The rewritten functions produce numerically identical output — the assert statements inside
  `_calculate_SOC_draft_reset_dch_zero` remain in place to guard against regressions.

---

## `run_evaluate.py` Wraps the Script as a Callable Function

**Decision:** The flat-script logic of `Run_Base_evaluation.py` is wrapped inside a
`run_evaluate()` function, called from `run_config.py`.

**Rationale:** A flat script cannot be imported, tested, or called from another module.
Wrapping in a function allows `run_config.py` to pass typed parameters, makes the pipeline
testable, and keeps user-editable configuration (`run_config.py`) separate from logic
(`run_evaluate.py`). The loop body and all pipeline steps are otherwise identical to the
original script.

**Trade-offs:** Users familiar with the original flat script may need to adjust. The mapping
is direct: top-level variables → `run_evaluate()` parameters; `print()` → `logging`.

---

## `print()` Replaced with `logging`

**Decision:** All `print()` calls from `Run_Base_evaluation.py` are replaced with
`logger.info()` / `logger.warning()` / `logger.error()` in `run_evaluate.py`.

**Rationale:** `logging` supports optional file output (controlled by `LOG_PATH`),
per-module filtering, and timestamps — none of which are available with `print()`.
This is important for long overnight batch runs where console output is not monitored.

**Trade-offs:** None significant. `run_config.py` prints the final summary line to console
so the user sees output even without reading the log file.

---

## `PATHS_OBJ` Centralises the Folder Convention

**Decision:** `src/paths.py` defines `PATHS_OBJ` which maps `BASE_PATH` to the fixed
subfolder names `03_Harmonized_Data/` and `04_Evaluated_Data/`. `run_config.py` only
exposes `BASE_PATH`.

**Rationale:** The `03_/04_` numbering convention is shared across the whole CDS toolchain.
Centralising it avoids each script independently constructing the same paths and drifting
out of sync.

**Trade-offs:** Moving to a different folder layout requires changing `paths.py`, not
`run_config.py`. The convention is intentionally not user-configurable.

---

## Long-Path Support via `\\?\` Prefix

**Decision:** All file paths pass through `long_path()` before any I/O, prepending `\\?\`
on Windows.

**Rationale:** Deep project trees with long cell IDs can push paths beyond the 260-character
Windows MAX_PATH limit, causing silent I/O failures.

**Trade-offs:** `\\?\` paths require absolute normalised paths — `long_path()` uses
`Path.absolute()` to ensure this before prepending.

---

## Meta JSON Enables Smart Skip-Rerun

**Decision:** Each successful cell run writes `{CELLID}_meta.json` (via `src/meta.py`)
alongside the other outputs. The skip-rerun check reads this file and compares the
current source files (name, size, mtime) and pipeline parameters against what was
recorded at the last run. If anything has changed the cell is re-evaluated automatically,
even when `SKIP_RERUN=True`.

**Meta contents:**
- `last_run`, `run_host`
- `pipeline_params` — nominal capacity, max/min voltage
- `source_files` — list of `{name, last_modified, size_bytes}` for every harmonized CSV
- `time_gaps` — start/resume datetime + unix timestamp, duration in s and h for every
  gap detected by `check_time_gap` (threshold 1 h)
- `output_files` — filenames written in that run
- `processing_stats` — `n_input_rows`, `n_steps`, `n_resampled_rows`

**Backward compatibility:** Cells evaluated before `meta.json` existed have no meta file.
The skip logic detects `meta is None` and falls back to the old file-existence check,
so existing evaluated data is not invalidated.

**Change detection uses size + mtime, not file hashing.**
Hashing large CSVs is expensive. Size + mtime together are reliable for this workflow:
the harmonized files grow when data is appended (size change) and the cycler software
updates the mtime on every write. If a file is replaced silently without either changing,
set `SKIP_RERUN = False` or add the cell to `SKIP_RERUN_EXCEPT_IDs` to force a rerun.

**Trade-offs:**
- Meta is only written on a fully successful run (all outputs completed). A partial
  failure leaves the old meta in place, so the next run with `SKIP_RERUN=True` will
  re-evaluate correctly based on the previous meta's source snapshot.
- `step_features_name` carries today's date in the filename. If rerun on a different
  day the old step-features file is not deleted — both dates will be present in the
  output folder. Only the newest is recorded in meta.

---

## Skip-Rerun Requires Both Output Files

**Decision:** A cell is skipped only if both `_processed_data.csv` **and** the HTML overview
already exist. Override per-cell with `SKIP_RERUN_EXCEPT_IDs` or globally with `SKIP_RERUN = False`.

**Rationale:** A partial run (CSV written, plot not yet written) should be re-run in full.
Checking only one file would leave the other permanently missing.

**Trade-offs:** If source harmonized CSVs are updated silently (no filename change), the stale
output persists. Manual deletion or `SKIP_RERUN = False` is required.

---

## SOC Calculation: C/3 RPT Reference Steps

**Decision:** SOC is scaled by the most recent measured C/3 discharge capacity (`Q_std`)
rather than nominal capacity.

**Rationale:** Cell capacity degrades over life. Using the last measured Q_std keeps SOC
physically meaningful across ageing.

**C/3 step identification (in `_calculate_SOC_draft_reset_dch_zero`):**
- `all_c3_dch_steps`: mean current × 3 within ±10% of `NOMINAL_CAPACITY` (negative)
- `full_dch_steps`: reach `MIN_CELL_VOLT + 0.05 V` and mean current > 25% nominal
- `c3_cha_steps`: final capacity ±10% nominal AND median current × 3 in [0.8, 1.1] × nominal
- `c3_dch_steps` (RPT-only): followed within 2–3 steps by a C/3 charge; proximity-filtered (threshold=8)

All four step lists are now derived from a single `groupby('Step_id').agg(...)` call
(aggregating `current_mean`, `current_median`, `voltage_min`, `cap_last`), rather than
four separate per-step `.loc[]` scans. `Q_std` and `SOC` are then assigned via
`Step_id.map(step_to_Qstd)` — two vectorised column writes instead of per-step `.loc[]` loops.

**Trade-offs:** If no C/3 RPT steps are found the assert will raise; `SOC_corrected` and
`Q_std` are set to NaN and a warning is logged.

---

## SOC Reset to Zero at Full Discharge

**Decision:** `SOC_corrected` is shifted so that it equals 0 at the first step after each
full-discharge event.

**Rationale:** Coulomb-counting drift accumulates over long tests. A known full-discharge
event is an unambiguous SOC=0 anchor, removing accumulated error.

**Implementation:** The correction is applied via a step-offset map: for each full-discharge
event, the SOC value at its reset step is recorded, the map is forward-filled across all
subsequent step IDs (`ffill`), and subtracted in a single vectorised column operation.
This replaces the original loop that re-sliced `df['Step_id'] >= reset_step` on every iteration.

**Pre-first-discharge behaviour:** Steps before the first full-discharge event are assigned
`SOC_corrected = SOC` (no correction applied, offset = 0). `SOC` for those steps already
uses the first RPT Q_std as reference (via the `c3_dch_steps[0]` fallback in step detection),
so `SOC_corrected` is physically meaningful throughout the test.
Tests with no full-discharge step produce an uncorrected `SOC_corrected` equal to `SOC` for all rows.

---

## Dynamic Resampling is Plot-Only

**Decision:** `dynamic_resampling()` is applied only to the data fed into the HTML plot.
The full `_processed_data.csv` is always written from the unsampled DataFrame.

**Rationale:** Resampling is lossy — it discards rows. The CSV must be complete for any
downstream analysis. The plot only needs to be visually faithful.

**Resampling thresholds:**

| Column    | Threshold | include_previous |
|-----------|-----------|-----------------|
| Voltage_V | 0.002 V   | False |
| Current_A | 1 A       | False |
| Step_id   | 1 (any)   | True |

Forced interval: at least 1 row per 60 s.

---

## Extra `src/` Functions Included but Not Called in the Main Pipeline

**Decision:** `src/` contains functions beyond what `run_evaluate.py` directly uses:
`export_to_excel`, `extract_2D_table_from_excel`, `split_on_time_gaps`, all helper
utilities, Arrhenius fitting functions, extra plotting functions, and `table_interpolation.py`.

**Rationale:** These functions are imported in `Run_Base_evaluation.py` (or available in
`basic_evaluation_cop`) and are frequently used in analysis notebooks that consume the
processed data. Keeping them in `src/` makes them available via `from src.X import Y`
without needing a separate dependency on the `basic_evaluation_cop` repo.

**Trade-offs:** `src/` is slightly larger than the minimum needed to run the pipeline.
Functions should still be updated in sync with `basic_evaluation_cop` when changed upstream.
