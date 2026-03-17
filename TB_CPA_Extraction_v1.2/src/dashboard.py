"""
dashboard.py  —  TB_CPA_Extraction v1.2
Generates a self-contained HTML dashboard from the extraction status dict.

Multi-PC: merges all extraction_trace_log_*.xlsx from 06_Logs/pc_logs/
so the dashboard reflects every PC that has processed files.

Usage (called automatically from extraction_run.py):
    gen = DashboardGenerator(status_dict, logs_path)
    gen.generate(logs_path / "extraction_dashboard.html")
"""

import json
import socket
from datetime import datetime
from pathlib import Path

import pandas as pd


class DashboardGenerator:
    """
    Builds the extraction dashboard HTML.

    Data sources (in priority order):
      1. The live status_dict from the current run (always fresh).
      2. Merged per-PC trace logs from pc_logs/ (historical runs on other PCs).

    The live run's data always takes precedence over stored log data for the
    same ZIP archive (identified by ZIP_path).
    """

    def __init__(self, status_dict: dict, logs_path: Path):
        self._zip_rows = _build_zip_rows(status_dict)
        self._run_ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._hostname = socket.gethostname()

        # Merge historical data for ZIPs not in current run
        self._zip_rows = _merge_historical(self._zip_rows, logs_path)

    def generate(self, output_path: Path):
        html = _build_html(self._zip_rows, self._run_ts, self._hostname)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        print(f"[Dashboard] Generated → {output_path.name}")


# ── Data extraction ──────────────────────────────────────────────────────────

def _build_zip_rows(status_dict: dict) -> list[dict]:
    """Convert the pipeline status_dict into a flat list of per-ZIP dicts."""
    rows = []
    for zip_path_str, entry in status_dict.items():
        zip_name = Path(zip_path_str).name

        to_copy  = len(entry.get("to_copy", {}).get("meta", {}))
        copied   = len(entry.get("copied_files_meta", {}))
        corrupt  = len(entry.get("corrupted", {}).get("names", []))
        ignored  = len(entry.get("to_ignore", {}).get("names", []))
        unknown  = len(entry.get("unknown", {}).get("names", []))

        # Cell IDs from copied files
        cell_ids = sorted({
            meta.get("cellid", "?")
            for meta in entry.get("copied_files_meta", {}).values()
            if meta.get("cellid")
        })

        # Corrupt files grouped by cell ID
        corrupt_by_cell = _group_corrupt(
            entry.get("corrupted", {}).get("names", []),
            entry.get("to_copy", {}).get("meta", {}),
        )

        archive_moved = bool(entry.get("compressed_file_meta", {}).get("copied_to_Archived"))

        if corrupt == 0 and unknown == 0:
            overall = "Success"
        elif copied > 0:
            overall = "Partial"
        else:
            overall = "Failed"

        rows.append({
            "zip_name":       zip_name,
            "zip_path":       zip_path_str,
            "to_copy":        to_copy,
            "copied":         copied,
            "corrupt":        corrupt,
            "ignored":        ignored,
            "unknown":        unknown,
            "cell_ids":       cell_ids,
            "corrupt_by_cell": corrupt_by_cell,
            "archive_moved":  archive_moved,
            "overall":        overall,
        })
    return rows


def _group_corrupt(corrupt_names: list, to_copy_meta: dict) -> dict:
    """Group corrupt file names by inferred cell ID."""
    import re
    result: dict[str, list] = {}
    for name in corrupt_names:
        stem = Path(name).stem
        cellid = "unknown"
        for path_key, meta in to_copy_meta.items():
            if Path(path_key).name == Path(name).name:
                prefix = meta.get("cellid_prefix", "")
                if prefix and prefix in stem:
                    splits = stem.split(prefix)
                    if len(splits) > 1:
                        cellid = prefix + re.split(r"[^a-zA-Z0-9]+", splits[1])[0]
                    else:
                        cellid = prefix
                break
        result.setdefault(cellid, []).append(Path(name).name)
    return result


def _merge_historical(live_rows: list[dict], logs_path: Path) -> list[dict]:
    """
    Append rows from pc_logs/ for ZIP archives not present in the live run.
    This shows a complete picture including ZIPs processed on other PCs.
    """
    live_paths = {r["zip_path"] for r in live_rows}
    pc_logs_dir = logs_path / "pc_logs"
    if not pc_logs_dir.exists():
        return live_rows

    frames = []
    for p in sorted(pc_logs_dir.glob("extraction_trace_log_*.xlsx")):
        try:
            frames.append(pd.read_excel(p, dtype=str))
        except Exception as e:
            print(f"[Dashboard] Warning: could not read {p.name}: {e}")

    if not frames:
        return live_rows

    hist_df = pd.concat(frames, ignore_index=True)

    for _, row in hist_df.iterrows():
        zp = str(row.get("ZIP_path", ""))
        if zp in live_paths:
            continue  # live run data takes precedence
        try:
            corrupt_by_cell = json.loads(str(row.get("Corrupt_files_json", "{}")))
        except Exception:
            corrupt_by_cell = {}
        cell_ids_raw = str(row.get("Cell_IDs", ""))
        cell_ids = [c.strip() for c in cell_ids_raw.split(",") if c.strip() and c.strip() != "—"]

        live_rows.append({
            "zip_name":        str(row.get("ZIP_name", "?")),
            "zip_path":        zp,
            "to_copy":         _int(row.get("To_copy")),
            "copied":          _int(row.get("Copied")),
            "corrupt":         _int(row.get("Corrupt")),
            "ignored":         _int(row.get("Ignored")),
            "unknown":         _int(row.get("Unknown")),
            "cell_ids":        cell_ids,
            "corrupt_by_cell": corrupt_by_cell,
            "archive_moved":   str(row.get("Archive_moved", "")).lower() == "true",
            "overall":         str(row.get("Status", "—")),
        })

    return live_rows


def _int(val) -> int:
    try:
        return int(val)
    except Exception:
        return 0


# ── HTML builder ─────────────────────────────────────────────────────────────

def _build_html(zip_rows: list[dict], run_ts: str, hostname: str) -> str:
    # Totals
    total_zips    = len(zip_rows)
    total_to_copy = sum(r["to_copy"]  for r in zip_rows)
    total_copied  = sum(r["copied"]   for r in zip_rows)
    total_corrupt = sum(r["corrupt"]  for r in zip_rows)
    total_ignored = sum(r["ignored"]  for r in zip_rows)
    total_unknown = sum(r["unknown"]  for r in zip_rows)

    totals = {
        "zips":    total_zips,
        "to_copy": total_to_copy,
        "copied":  total_copied,
        "corrupt": total_corrupt,
        "ignored": total_ignored,
        "unknown": total_unknown,
    }

    data_json = json.dumps({"rows": zip_rows, "totals": totals}, indent=2, default=str)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Extraction Dashboard — TB_CPA v1.2</title>
<style>
  :root {{
    --blue-dark:  #1F4E79;
    --blue-mid:   #2E75B6;
    --blue-light: #D6E4F0;
    --green:      #70AD47;
    --orange:     #ED7D31;
    --red:        #FF4C4C;
    --yellow:     #FFD966;
    --grey-bg:    #F4F7FB;
    --grey-line:  #DEE2E6;
    --text:       #212529;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: var(--grey-bg); color: var(--text); }}

  /* ── Header ── */
  .header {{
    background: linear-gradient(135deg, var(--blue-dark) 0%, var(--blue-mid) 100%);
    color: white; padding: 20px 32px;
  }}
  .header h1 {{ font-size: 1.5rem; font-weight: 700; letter-spacing: .5px; }}
  .header .subtitle {{ font-size: 0.85rem; opacity: .8; margin-top: 4px; }}

  /* ── Summary cards ── */
  .cards {{ display: flex; gap: 16px; padding: 20px 32px; flex-wrap: wrap; }}
  .card {{
    background: white; border-radius: 10px; padding: 16px 24px;
    box-shadow: 0 2px 8px rgba(0,0,0,.07); min-width: 120px; flex: 1;
    border-top: 4px solid var(--blue-mid);
  }}
  .card.green  {{ border-top-color: var(--green); }}
  .card.orange {{ border-top-color: var(--orange); }}
  .card.red    {{ border-top-color: var(--red); }}
  .card.yellow {{ border-top-color: var(--yellow); }}
  .card .val {{ font-size: 2rem; font-weight: 700; }}
  .card .lbl {{ font-size: 0.78rem; color: #6c757d; margin-top: 4px; text-transform: uppercase; letter-spacing: .5px; }}

  /* ── Chart ── */
  .chart-wrap {{
    background: white; border-radius: 10px; margin: 0 32px 24px;
    padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,.07);
  }}
  .chart-wrap h2 {{ font-size: 1rem; color: var(--blue-dark); margin-bottom: 14px; }}
  #barChart {{ max-height: 260px; }}

  /* ── Main table ── */
  .section {{ margin: 0 32px 32px; }}
  .section h2 {{ font-size: 1rem; color: var(--blue-dark); margin-bottom: 10px; }}
  table {{ width: 100%; border-collapse: collapse; background: white;
           border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,.07); }}
  th {{
    background: var(--blue-dark); color: white; text-align: left;
    padding: 10px 14px; font-size: .82rem; text-transform: uppercase; letter-spacing: .4px;
    cursor: pointer; user-select: none;
  }}
  th:hover {{ background: var(--blue-mid); }}
  td {{ padding: 10px 14px; font-size: .88rem; border-bottom: 1px solid var(--grey-line); vertical-align: top; }}
  tr.zip-row {{ cursor: pointer; transition: background .15s; }}
  tr.zip-row:hover {{ background: var(--blue-light); }}
  tr.zip-row td.expand-cell::before {{ content: '▶  '; font-size: .7rem; color: var(--blue-mid); }}
  tr.zip-row.open td.expand-cell::before {{ content: '▼  '; }}

  /* ── Detail panel ── */
  tr.detail-row td {{ padding: 0; background: #f0f4fa; border-bottom: 2px solid var(--blue-light); }}
  .detail-inner {{ padding: 16px 24px 20px 40px; }}

  .detail-section {{ margin-bottom: 16px; }}
  .detail-section h3 {{ font-size: .85rem; color: var(--blue-dark); margin-bottom: 8px; font-weight: 600; }}

  /* Cell ID chips */
  .chip-list {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .chip {{
    background: var(--blue-light); color: var(--blue-dark);
    border-radius: 20px; padding: 3px 12px; font-size: .80rem; font-weight: 600;
  }}

  /* Corrupt sub-table */
  .corrupt-table {{ border-collapse: collapse; border-radius: 6px; overflow: hidden; width: auto; box-shadow: none; }}
  .corrupt-table th {{ background: #c0392b; font-size: .76rem; padding: 6px 12px; }}
  .corrupt-table td {{ font-size: .78rem; padding: 5px 12px; background: #fff5f5; border-bottom: 1px solid #fdd; }}
  .corrupt-table tr:last-child td {{ border-bottom: none; }}

  /* ── Badges ── */
  .badge {{
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: .76rem; font-weight: 600; white-space: nowrap;
  }}
  .badge-Success {{ background: #C6EFCE; color: #276221; }}
  .badge-Partial  {{ background: #FFEB9C; color: #7D5A00; }}
  .badge-Failed   {{ background: #FFC7CE; color: #9C0006; }}
  .badge-moved    {{ background: #C6EFCE; color: #276221; }}
  .badge-pending  {{ background: #F2F2F2; color: #666; }}

  .num-red    {{ color: #c0392b; font-weight: 700; }}
  .num-green  {{ color: #276221; font-weight: 700; }}
  .num-orange {{ color: #7D5A00; font-weight: 700; }}

  /* ── Filter bar ── */
  .filter-bar {{ margin: 0 32px 16px; display: flex; gap: 10px; align-items: center; }}
  .filter-bar input {{
    border: 1px solid var(--grey-line); border-radius: 6px; padding: 6px 12px;
    font-size: .88rem; width: 300px; background: white;
  }}
  .filter-bar label {{ font-size: .85rem; color: #6c757d; }}
  .filter-bar select {{
    border: 1px solid var(--grey-line); border-radius: 6px; padding: 6px 10px;
    font-size: .88rem; background: white;
  }}
</style>
</head>
<body>

<div class="header">
  <h1>TB_CPA Extraction Dashboard</h1>
  <div class="subtitle">Generated: {run_ts} &nbsp;|&nbsp; PC: {hostname} &nbsp;|&nbsp; TB_CPA_Extraction v1.2</div>
</div>

<div class="cards" id="cards"></div>

<div class="chart-wrap">
  <h2>Files per ZIP — Copied / Corrupt / Ignored</h2>
  <canvas id="barChart"></canvas>
</div>

<div class="filter-bar">
  <label>Filter:</label>
  <input type="text" id="searchInput" placeholder="Search ZIP name or cell ID …" oninput="applyFilter()">
  <label>Status:</label>
  <select id="statusFilter" onchange="applyFilter()">
    <option value="">All</option>
    <option value="Success">Success</option>
    <option value="Partial">Partial</option>
    <option value="Failed">Failed</option>
  </select>
</div>

<div class="section">
  <h2>ZIP Archive Summary &nbsp;<small style="font-weight:normal;color:#6c757d">(click a row to expand details)</small></h2>
  <table id="zipTable">
    <thead>
      <tr>
        <th onclick="sortTable(0)">ZIP Archive ⇅</th>
        <th onclick="sortTable(1)">To Copy ⇅</th>
        <th onclick="sortTable(2)">Copied ⇅</th>
        <th onclick="sortTable(3)">Corrupt ⇅</th>
        <th onclick="sortTable(4)">Ignored ⇅</th>
        <th onclick="sortTable(5)">Unknown ⇅</th>
        <th onclick="sortTable(6)">Cells ⇅</th>
        <th onclick="sortTable(7)">Archived ⇅</th>
        <th onclick="sortTable(8)">Status ⇅</th>
      </tr>
    </thead>
    <tbody id="zipTbody"></tbody>
  </table>
</div>

<script>
// ── Inline Chart.js (CDN) ─────────────────────────────────────────────────
// Note: requires internet for first load; for offline use, bundle Chart.js separately.
</script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
<script>
const DATA = {data_json};

// ── Summary cards ────────────────────────────────────────────────────────────
(function() {{
  const t = DATA.totals;
  const defs = [
    {{ val: t.zips,    lbl: 'ZIP Archives', cls: '' }},
    {{ val: t.to_copy, lbl: 'To Copy',      cls: '' }},
    {{ val: t.copied,  lbl: 'Copied',       cls: 'green' }},
    {{ val: t.corrupt, lbl: 'Corrupt',      cls: 'red' }},
    {{ val: t.ignored, lbl: 'Ignored',      cls: 'orange' }},
    {{ val: t.unknown, lbl: 'Unknown',      cls: 'yellow' }},
  ];
  const wrap = document.getElementById('cards');
  defs.forEach(d => {{
    wrap.innerHTML += `<div class="card ${{d.cls}}"><div class="val">${{d.val}}</div><div class="lbl">${{d.lbl}}</div></div>`;
  }});
}})();

// ── Bar chart ────────────────────────────────────────────────────────────────
(function() {{
  const rows = DATA.rows;
  const labels = rows.map(r => r.zip_name.length > 35 ? r.zip_name.slice(0,33)+'…' : r.zip_name);
  new Chart(document.getElementById('barChart'), {{
    type: 'bar',
    data: {{
      labels,
      datasets: [
        {{ label: 'Copied',  data: rows.map(r => r.copied),  backgroundColor: '#70AD47' }},
        {{ label: 'Corrupt', data: rows.map(r => r.corrupt), backgroundColor: '#FF4C4C' }},
        {{ label: 'Ignored', data: rows.map(r => r.ignored), backgroundColor: '#ED7D31' }},
        {{ label: 'Unknown', data: rows.map(r => r.unknown), backgroundColor: '#FFD966' }},
      ]
    }},
    options: {{
      responsive: true,
      plugins: {{ legend: {{ position: 'top' }} }},
      scales: {{ x: {{ stacked: true }}, y: {{ stacked: true, beginAtZero: true }} }}
    }}
  }});
}})();

// ── Table rendering ──────────────────────────────────────────────────────────
const tbody = document.getElementById('zipTbody');

function badge(val) {{
  const cls = val === true ? 'moved' : val === false ? 'pending' : val;
  const label = val === true ? '✔ Archived' : val === false ? '— Pending' : val;
  return `<span class="badge badge-${{cls}}">${{label}}</span>`;
}}

function numCell(n, cls) {{
  if (n === 0) return `<td>0</td>`;
  return `<td class="${{cls}}">${{n}}</td>`;
}}

function buildDetail(row) {{
  // Cell ID chips
  let chips = '<div class="detail-section"><h3>Cell IDs (' + row.cell_ids.length + ')</h3>';
  if (row.cell_ids.length === 0) {{
    chips += '<p style="color:#999;font-size:.82rem">No cell IDs found (no files copied)</p>';
  }} else {{
    chips += '<div class="chip-list">';
    row.cell_ids.forEach(c => {{ chips += `<span class="chip">${{c}}</span>`; }});
    chips += '</div>';
  }}
  chips += '</div>';

  // Corrupt files per cell
  let corruptHtml = '';
  const cbc = row.corrupt_by_cell || {{}};
  const corruptCells = Object.keys(cbc);
  if (corruptCells.length > 0) {{
    corruptHtml = '<div class="detail-section"><h3 style="color:#c0392b">Corrupt Files by Cell ID</h3>';
    corruptHtml += '<table class="corrupt-table"><thead><tr><th>Cell ID</th><th>Files</th></tr></thead><tbody>';
    corruptCells.forEach(cid => {{
      const files = cbc[cid];
      corruptHtml += `<tr><td><strong>${{cid}}</strong></td><td>`;
      corruptHtml += files.map(f => `<div>${{f}}</div>`).join('');
      corruptHtml += '</td></tr>';
    }});
    corruptHtml += '</tbody></table></div>';
  }}

  // ZIP path
  const pathHtml = `<div class="detail-section"><h3>Archive Path</h3>
    <code style="font-size:.78rem;color:#555;word-break:break-all">${{row.zip_path}}</code></div>`;

  return `<div class="detail-inner">${{chips}}${{corruptHtml}}${{pathHtml}}</div>`;
}}

let _allRows = DATA.rows.slice();  // working copy for sort/filter
let _sortDir = {{}};

function renderRows(rows) {{
  tbody.innerHTML = '';
  rows.forEach(row => {{
    const tr = document.createElement('tr');
    tr.className = 'zip-row';
    tr.dataset.zippath = row.zip_path;
    tr.dataset.searchtext = (row.zip_name + ' ' + row.cell_ids.join(' ')).toLowerCase();
    tr.dataset.status = row.overall;

    tr.innerHTML =
      `<td class="expand-cell">${{row.zip_name}}</td>` +
      `<td>${{row.to_copy}}</td>` +
      (row.copied  > 0 ? `<td class="num-green">${{row.copied}}</td>`  : `<td>0</td>`) +
      (row.corrupt > 0 ? `<td class="num-red">${{row.corrupt}}</td>`   : `<td>0</td>`) +
      (row.ignored > 0 ? `<td class="num-orange">${{row.ignored}}</td>` : `<td>0</td>`) +
      (row.unknown > 0 ? `<td class="num-orange">${{row.unknown}}</td>` : `<td>0</td>`) +
      `<td>${{row.cell_ids.length}}</td>` +
      `<td>${{badge(row.archive_moved)}}</td>` +
      `<td>${{badge(row.overall)}}</td>`;
    tbody.appendChild(tr);

    // Detail row (hidden)
    const detailTr = document.createElement('tr');
    detailTr.className = 'detail-row';
    detailTr.style.display = 'none';
    const td = document.createElement('td');
    td.colSpan = 9;
    td.innerHTML = buildDetail(row);
    detailTr.appendChild(td);
    tbody.appendChild(detailTr);

    tr.addEventListener('click', () => {{
      const open = detailTr.style.display !== 'none';
      detailTr.style.display = open ? 'none' : 'table-row';
      tr.classList.toggle('open', !open);
    }});
  }});
}}

renderRows(_allRows);

// ── Filter ────────────────────────────────────────────────────────────────────
function applyFilter() {{
  const q      = document.getElementById('searchInput').value.toLowerCase();
  const status = document.getElementById('statusFilter').value;
  const filtered = DATA.rows.filter(r => {{
    const txt = (r.zip_name + ' ' + r.cell_ids.join(' ')).toLowerCase();
    return (!q || txt.includes(q)) && (!status || r.overall === status);
  }});
  _allRows = filtered;
  renderRows(_allRows);
}}

// ── Sort ──────────────────────────────────────────────────────────────────────
function sortTable(colIdx) {{
  const dir = (_sortDir[colIdx] = !_sortDir[colIdx]);
  _allRows.sort((a, b) => {{
    const cols = ['zip_name','to_copy','copied','corrupt','ignored','unknown','cell_ids','archive_moved','overall'];
    let va = a[cols[colIdx]], vb = b[cols[colIdx]];
    if (cols[colIdx] === 'cell_ids') {{ va = va.length; vb = vb.length; }}
    if (typeof va === 'boolean') {{ va = va ? 1 : 0; vb = vb ? 1 : 0; }}
    const na = parseFloat(va), nb = parseFloat(vb);
    const cmp = isNaN(na) ? String(va).localeCompare(String(vb)) : na - nb;
    return dir ? cmp : -cmp;
  }});
  renderRows(_allRows);
}}
</script>
</body>
</html>"""
