# TB_CPA_Extraction v1.2

Automated archive extraction and file distribution pipeline for battery cell test data (C48 Test Project).
Detects, extracts, and copies supplier data files from compressed archives into per-cell folder structure.

---

## GUI (Recommended for interactive use)

```bash
python battery_analysis_scripts/TB_CPA_Extraction_v1.2/extraction_gui.py
```

**Features:**

| Feature | Detail |
|---------|--------|
| Config list | Add, remove, or duplicate configs in the left panel |
| Editor | Set Name, Base Path, ZIP Filter, Copy Action, Dashboard toggle |
| Run This | Runs the selected config in a background subprocess with live console output |
| Run All | Runs all configs sequentially (skips any with no Base Path set) |
| Stop | Terminates the running process cleanly; cancels the remaining queue |
| Console | Live-streamed output with timestamps; Clear and Copy All buttons |
| Persistence | Configs auto-saved to `gui_configs.json` on close and reloaded on next launch |
| Save / Load | Export or import configs as a JSON file via toolbar buttons |

**Requirements:** `PySide6` — install with `pip install PySide6`

---

## Quick Start

**Single project:**
```bash
# 1. Set BASE_PATH in run_config.py
# 2. Run:
python battery_analysis_scripts/TB_CPA_Extraction_v1.2/run_config.py
```

**Multiple projects / daily scheduler:**
```bash
# 1. Add projects to PROJECTS list in run_all_config.py
# 2. Run manually, or register run_all.bat in Windows Task Scheduler
python battery_analysis_scripts/TB_CPA_Extraction_v1.2/run_all_config.py
```

---

## Entry Point Files

| File | Purpose |
|------|---------|
| `extraction_gui.py` | **GUI entry point** — interactive multi-config runner (PySide6) |
| `run_config.py` | Single-project script entry point — edit `BASE_PATH` and run parameters here |
| `run_all_config.py` | Multi-project script entry point — list of `PROJECTS` dicts, one per data root |
| `run_all.bat` | Windows batch launcher for Task Scheduler (see Scheduling section) |
| `src/_gui_runner.py` | Internal subprocess shim used by the GUI — do not run directly |

---

## Run Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `BASE_PATH` | — | Root data folder (must contain all numbered subfolders) |
| `ZIP_FILES` | `None` | Substrings to filter which archives to process; `None` = all |
| `COPY_ACTION` | `'skip_copy'` | `'skip_copy'` / `'replace'` / `'create_copy'` for duplicate files |
| `GENERATE_DASHBOARD` | `True` | Write `extraction_dashboard.html` to `06_Logs/` after each run |

---

## Pipeline Stages

```
01_Incoming_Compressed_Files/
    │
    ├── Stage 1: Detect & test archives (patool integrity check)
    │
    ├── Stage 2: Extract to 08_Backlog/temp_extract_{name}/
    │           Filter by format_config.yaml (include/exclude patterns)
    │           Split multi-sheet Excel files if configured
    │
    ├── Stage 3: Copy files → 02_Extracted_Raw_Files/{cellid}/
    │           Extract cell ID from filename using configured prefix
    │           Handle duplicates per copy_action setting
    │
    ├── Stage 4: Clear backlog — verify copies (size + hash), then delete originals
    │
    └── Move archives → 07_Archived/{YYYY-MM_CWxx}/
        (only if no corrupt/unknown/failed files)
```

---

## Outputs

```
<BASE_PATH>/
├── 02_Extracted_Raw_Files/
│   └── {Cell_ID}/
│       └── {filename}.xlsx          ← extracted raw data files
└── 06_Logs/
    ├── pc_logs/
    │   └── extraction_trace_log_{HOSTNAME}.xlsx   ← per-PC audit log
    ├── extraction_dashboard.html    ← merged dashboard (all PCs)
    ├── extract_trace.xlsx           ← legacy run log (appended each run)
    ├── debug_logs/debug_logfile.log
    └── backend_base/{timestamp}_status.json
```

---

## Trace Log (`extraction_trace_log_{HOSTNAME}.xlsx`)

One row per ZIP archive, updated in place on rerun (upsert).

| Column | Description |
|--------|-------------|
| `Run_timestamp` | When the run was executed |
| `PC_hostname` | Machine that processed the archive |
| `ZIP_name` | Archive filename |
| `ZIP_path` | Full path to the archive |
| `To_copy` | Files identified for copying |
| `Copied` | Files successfully copied to cell folders |
| `Corrupt` | Files that failed archive integrity check |
| `Ignored` | Files excluded by format_config.yaml |
| `Unknown` | Files not matching any config pattern (requires manual review) |
| `Cell_IDs` | Comma-separated list of cell IDs found in this archive |
| `Corrupt_files_json` | JSON: `{cell_id: [filenames]}` for corrupt files |
| `Archive_moved` | Whether the ZIP was moved to `07_Archived/` |
| `Status` | `Success` / `Partial` / `Failed` |

---

## Dashboard (`extraction_dashboard.html`)

Self-contained HTML — open in any browser, no server needed.

- **Summary cards** — total ZIPs, to-copy, copied, corrupt, ignored, unknown
- **Stacked bar chart** (Chart.js) — per-ZIP copied / corrupt / ignored breakdown
- **ZIP archive table** (sortable, filterable) — one row per archive
  - **Expand drill-down** — click any row to see:
    - **Cell ID breakdown table** — per-cell counts of To Copy / Copied / Corrupt, plus detected Supplier (from `format_config.yaml` pattern matching)
    - **Corrupt files by cell ID** — individual filenames listed under each cell
    - Full archive path
- **Multi-PC** — merges all `pc_logs/extraction_trace_log_*.xlsx` files so the dashboard reflects every machine that ran the pipeline

---

## Scheduling with Windows Task Scheduler

1. Open **Task Scheduler** → *Create Basic Task*
2. **Name:** `TB_CPA_Extraction_daily`
3. **Trigger:** Daily → set desired time (e.g. `06:00`)
4. **Action:** Start a program
   - Program: `C:\...\TB_CPA_Extraction_v1.2\run_all.bat`
   - Start in: `C:\...\TB_CPA_Extraction_v1.2\`
5. **Properties → Security Options:**
   - ☑ Run whether user is logged on or not
   - ☑ Run with highest privileges *(if accessing network/OneDrive paths)*
6. Click OK, enter Windows password

**Lock file:** `run_all_{HOSTNAME}.lock` is created at start and deleted on completion.
If a run is still active when the next scheduled trigger fires, the new instance exits immediately — no overlap, no conflict.

---

## Multi-PC Safety

Multiple PCs can run against the same OneDrive base path simultaneously with no file conflicts:

- Each PC writes only to **its own** `pc_logs/extraction_trace_log_{HOSTNAME}.xlsx`
- The lock file is also per-PC (`run_all_{HOSTNAME}.lock`)
- The dashboard reads **all** PC log files and merges them at generation time

---

## Format Config (`template/05_Configuration/format_config.yaml`)

Controls which files are extracted and how cell IDs are identified:

```yaml
RawDataHandling:
  format_to_import:
    "*DQ*.xlsx":                    # fnmatch pattern
      supplier: Gotion
      split_datasheets: RecordInfo  # split multi-sheet Excel on this sheet name
      cellid_prefix: DQ             # prefix used to extract cell ID from filename
    "*_FC*.xlsx":
      supplier: MCM
      split_datasheets: null
      cellid_prefix: FC
  format_to_ignore:
    "*_Info.xlsx": {}               # patterns to exclude
```

To add a new supplier: add an entry under `format_to_import` with the correct `fnmatch` pattern, `supplier`, `split_datasheets`, and `cellid_prefix`.

---

## Dependencies

```bash
pip install -r requirements.txt
```

Key packages: `patool`, `pandas`, `openpyxl`, `pyyaml`, `python-magic`, `tqdm`, `tabulate`, `PySide6`

---

## Version History

### v1.2 *(current)*

**New features:**
- `extraction_gui.py` + `src/_gui_runner.py` — PySide6 GUI for interactive multi-config runs with live console output, Stop button, and JSON persistence
- `run_config.py` — single-file user entry point; `BASE_PATH` and all run parameters in one place, no need to edit `src/paths.py`
- `run_all_config.py` — multi-project entry point with per-PC lock file guard
- `run_all.bat` — Windows batch launcher with Task Scheduler setup instructions inline
- `src/trace_log.py` — persistent per-archive audit log (`extraction_trace_log_{HOSTNAME}.xlsx`); upsert behaviour; one row per ZIP
- `src/dashboard.py` — self-contained HTML dashboard with Chart.js stacked bar chart, sortable/filterable ZIP table, and expandable drill-down rows showing a per-cell breakdown table (To Copy / Copied / Corrupt / Supplier) and corrupt file names per cell
- Per-PC log files in `06_Logs/pc_logs/` — no OneDrive/network write conflicts when multiple PCs use the same data root
- `src/paths.py` — `PATHS_OBJ` now accepts `base_path` as constructor argument (no hardcoding)

**Unchanged:**
- All pipeline logic in `src/extract_archive.py`, `src/file_handling.py`, `src/clear_backlog.py`, `src/consistency_check.py`
- `template/05_Configuration/format_config.yaml` schema
- Original `TB_CPA_Extraction/` folder — untouched

---

### v1.1 *(TB_CPA_Extraction — original)*
- Pipeline logic in `src/` modules
- Run parameters hard-coded in `main.py` and `src/paths.py`
- Status output as timestamped JSON in `06_Logs/backend_base/`
- No persistent audit log; no dashboard; no GUI
