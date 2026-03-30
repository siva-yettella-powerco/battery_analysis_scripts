# TB_CPA_Harmonize v1.2

Automated harmonization pipeline for battery cell test data (C48 Test Project).
Transforms supplier-specific raw files into a unified 16-column CSV schema.

---

## GUI (Recommended for interactive use)

A point-and-click interface for running multiple configs without editing any Python files.

```bash
python battery_analysis_scripts/TB_CPA_Harmonize_v1.2/harmonize_gui.py
```

**Features:**

| Feature | Detail |
|---------|--------|
| Config list | Add, remove, or duplicate configs in the left panel |
| Editor | Set Name, Base Path, Skip Rerun, Force-rerun IDs, Copy Action, Cell ID filter, Dashboard toggle |
| Run This | Runs the selected config in a background subprocess with live console output |
| Run All | Runs all configs sequentially (skips any with no Base Path set) |
| Stop | Terminates the running process cleanly; cancels the remaining queue |
| Console | Live-streamed output with timestamps; Clear and Copy All buttons |
| Persistence | Configs auto-saved to `gui_configs.json` on close and reloaded on next launch |
| Save / Load | Export or import configs as a JSON file via toolbar buttons |

**Requirements:** `PySide6` (install with `pip install PySide6`)

---

## Quick Start

**Single project:**
```bash
# 1. Set BASE_PATH in run_config.py
# 2. Run:
python battery_analysis_scripts/TB_CPA_Harmonize_v1.2/run_config.py
```

**Multiple projects / daily scheduler:**
```bash
# 1. Add projects to PROJECTS list in run_all_config.py
# 2. Run manually, or register run_all.bat in Windows Task Scheduler
python battery_analysis_scripts/TB_CPA_Harmonize_v1.2/run_all_config.py
```

---

## Entry Point Files

| File | Purpose |
|------|---------|
| `harmonize_gui.py` | **GUI entry point** — interactive multi-config runner (PySide6) |
| `run_config.py` | Single-project script entry point — edit `BASE_PATH` and run parameters here |
| `run_all_config.py` | Multi-project script entry point — list of `PROJECTS` dicts, one per data root |
| `run_all.bat` | Windows batch launcher for Task Scheduler (see Scheduling section) |
| `_gui_runner.py` | Internal subprocess shim used by the GUI — do not run directly |

---

## Run Parameters (both entry points)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `BASE_PATH` | — | Root data folder containing `02_Extracted_Raw_Files`, `06_Logs`, etc. |
| `SKIP_RERUN` | `True` | Skip files whose harmonized CSV already exists |
| `SKIP_RERUN_EXCEPT_IDs` | `[]` | Cell IDs to force-rerun even when `SKIP_RERUN=True` |
| `COPY_ACTION` | `'skip_copy'` | `'skip_copy'` / `'replace'` / `'create_copy'` for existing output files |
| `RUN_CELL_IDs` | `[]` | Process only listed cell folders; `[]` = all cells |
| `GENERATE_DASHBOARD` | `True` | Write `harmonize_dashboard.html` to `06_Logs/` after each run |

---

## Outputs

```
<BASE_PATH>/
├── 03_Harmonized_Data/
│   └── {Cell_ID}/
│       └── {filename}.csv          ← 16-column unified schema
└── 06_Logs/
    ├── pc_logs/
    │   └── harmonize_trace_log_{HOSTNAME}.xlsx   ← per-PC audit log
    ├── harmonize_dashboard.html    ← merged dashboard (all PCs)
    ├── debug_logs/debug_logfile.log
    └── backend_base/hm_{timestamp}_status.json
```

---

## Trace Log (`harmonize_trace_log_{HOSTNAME}.xlsx`)

One row per source file, updated in place on rerun (upsert).

| Column | Description |
|--------|-------------|
| `Run_timestamp` | When the run was executed |
| `PC_hostname` | Machine that processed the file |
| `Cell_ID` | Cell folder name (e.g. `LFP44X_001`) |
| `File_name` | Source filename |
| `File_path` | Full path to source file |
| `File_size_KB` | Source file size in KB |
| `Supplier` | Detected supplier (MCM / GOTION / SZ / SRF / TRURON) |
| `Config_used` | Matching config class (e.g. `cfg_mcm_std_01`) |
| `Status` | `Harmonized` / `Skipped` / `Failed` / `No_config` |
| `Skip_reason` | `already_harmonized` / `no_config_match` / `empty_output` / `error` |
| `Error_message` | Exception text (up to 500 chars) if failed |
| `Harmonized_file_path` | Full path to output CSV |
| `Output_size_KB` | Size of output CSV at time of export |
| `Row_count` | Data rows in harmonized CSV |
| `Date_harmonized` | Timestamp of successful export |
| `Current_status` | `OK` / `Modified` / `Deleted` / `Not_applicable` — checked on every run |

**Rerun behaviour:**
- `Status=Skipped` + row already exists → **row unchanged** (previous `Harmonized` record preserved)
- Any other status → row updated in place
- `Current_status` is refreshed on every run by checking if the output CSV still exists and matches the stored size (±10 KB threshold)

---

## Dashboard (`harmonize_dashboard.html`)

Self-contained HTML file — open in any browser, no server needed. No CDN or internet required.

- **Summary cards** — total cell IDs, extract files, harmonized, not harmonized
- **Cell summary table** (sortable) — per-cell counts of Extract Files / Harmonized / Not Harmonized with a progress bar (%)
  - **Expand drill-down** — click any row to see:
    - Each source file in `02_Extracted_Raw_Files/{cell_id}/` with a **Yes / No** harmonized badge
    - Last-edited timestamp of the matching CSV in `03_Harmonized_Data/{cell_id}/`
- **Live folder scan** — reflects the actual file-system state at run time (not trace-log based); a file is shown as harmonized if and only if a matching `.csv` exists in the harmonize folder

---

## Scheduling with Windows Task Scheduler

1. Open **Task Scheduler** → *Create Basic Task*
2. **Name:** `TB_CPA_Harmonize_daily`
3. **Trigger:** Daily → set desired time (e.g. `06:00`)
4. **Action:** Start a program
   - Program: `C:\...\TB_CPA_Harmonize_v1.2\run_all.bat`
   - Start in: `C:\...\TB_CPA_Harmonize_v1.2\`
5. **Properties → Security Options:**
   - ☑ Run whether user is logged on or not
   - ☑ Run with highest privileges *(if accessing network/OneDrive paths)*
6. Click OK, enter Windows password

**Lock file:** `run_all_{HOSTNAME}.lock` is created at start and deleted when done.
If a run is still in progress when the next scheduled trigger fires, the new instance exits immediately with a warning — no overlap, no conflict.

---

## Multi-PC Safety

Multiple PCs can run against the same OneDrive base path simultaneously with no file conflicts:

- Each PC writes only to **its own** `pc_logs/harmonize_trace_log_{HOSTNAME}.xlsx`
- The lock file is also per-PC (`run_all_{HOSTNAME}.lock`)
- The dashboard reads **all** PC log files and merges them at generation time

---

## Supported Suppliers

| Supplier | Detection pattern |
|----------|-------------------|
| MCM | `LFP44X` in cell folder / `QCA0`, `MCM`, `GOT` in filename |
| GOTION | `DQ` prefix / `_DQ` / `LAB-VW` prefix |
| SZ | `096_` + `_P_` in cell folder |
| SRF | `CNSRF` in filename |
| TRURON | `CNTRURON` / `_Channel_` / `Ch` + `Wb` in filename |

---

## Output Schema (16 columns)

```
Total_time_s, Date_time, Unix_time, Step, Step_name, Cycle,
Voltage_V, Current_A, Power_W, Capacity_step_Ah, Energy_step_Wh,
T_Cell_degC, T_Anode_degC, T_Cathode_degC, T_Chamber_degC, T_cold_degC
```

**Mandatory columns** (run fails if absent): `Total_time_s`, `Date_time`, `Voltage_V`, `Current_A`, `Capacity_step_Ah`

---

## Dependencies

```
pip install -r requirements.txt
```

Key packages: `pandas`, `openpyxl`, `pyarrow`, `python-magic`, `pyyaml`, `tqdm`

---

## Version History

### v1.2 *(current)*
**New features:**
- `harmonize_gui.py` + `_gui_runner.py` — PySide6 GUI for interactive multi-config runs with live console output, Stop button, and JSON persistence (no changes to core pipeline)
- `run_config.py` — single-file user entry point; `BASE_PATH` and all run parameters in one place, no need to edit `paths.py` or `harmonize_run.py`
- `run_all_config.py` — multi-project entry point; add multiple `BASE_PATH` entries as a list of project dicts
- `run_all.bat` — Windows batch launcher with Task Scheduler setup instructions inline; appends output to `run_all.log`
- `src/trace_log.py` — persistent per-file audit log (`harmonize_trace_log_{HOSTNAME}.xlsx`); upsert behaviour (one row per file, updates in place on rerun); `Current_status` refreshed on every run
- `src/dashboard.py` — self-contained HTML dashboard built from a live folder scan of `02_Extracted_Raw_Files/` and `03_Harmonized_Data/`; sortable cell table with progress bars and expandable per-file rows showing harmonization status and last-edited timestamp; no CDN dependency
- Per-PC log files in `06_Logs/pc_logs/` subfolder — eliminates OneDrive/network write conflicts when multiple PCs process the same data root simultaneously
- `src/paths.py` — `PATHS_OBJ` now accepts `base_path` in `__init__()` (injectable) instead of hard-coded class attribute
- Lock file guard (`run_all_{HOSTNAME}.lock`) — prevents overlapping scheduled runs on the same PC

**Bug fixes:**
- Original `harmonize_run.py` filtered out all files when `RUN_CELLIDs = []` (empty list always evaluates to no match). Fixed: empty `run_cell_ids` now correctly processes all cells.

**Unchanged:**
- All `harmonize/` supplier transform modules (`hm_mcm_trans_func.py`, `hm_got_trans_func.py`, etc.)
- ETL config Excel schema (`supplier_data_ETL_config.xlsx`)
- Original `TB_CPA_Harmonize/` folder — untouched

---

### v1.1 *(TB_CPA_Harmonize — original)*
- Supplier-agnostic flat-script pipeline
- Config classes per supplier in `harmonize/hm_import_data.py`
- Run parameters hard-coded in `harmonize_run.py` and `src/paths.py`
- Status output as timestamped JSON in `06_Logs/backend_base/`
- No persistent audit log; no dashboard
