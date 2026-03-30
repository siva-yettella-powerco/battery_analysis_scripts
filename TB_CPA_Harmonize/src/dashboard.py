"""
dashboard.py  —  TB_CPA_Harmonize v1.2
Generates a self-contained HTML dashboard by scanning the extract and
harmonize folders directly.

For each cell ID (subfolder in extract_path) it lists every source file and
checks whether a matching .csv exists in harmonized_path/{cell_id}/.
The last-modified time of the .csv is shown if present.
"""

import json
from pathlib import Path
from datetime import datetime


class DashboardGenerator:
    """
    Scans extract_path and harmonized_path to build a folder-state dashboard
    and writes harmonize_dashboard.html to logs_path.

    Usage:
        gen = DashboardGenerator(trace_log, logs_path,
                                 extract_path=extract_path,
                                 harmonized_path=harmonized_path)
        gen.generate(logs_path / "harmonize_dashboard.html")
    """

    def __init__(self, trace_log, logs_path: Path = None,
                 extract_path: Path = None, harmonized_path: Path = None):
        self._extract_path    = extract_path
        self._harmonized_path = harmonized_path

    # ── Public ────────────────────────────────────────────────────────────────

    def generate(self, output_path: Path):
        if self._extract_path and self._harmonized_path:
            cell_summary, total_stats = self._scan_folders()
        else:
            cell_summary, total_stats = [], {
                "total_cells": 0, "total_extract": 0,
                "total_harmonized": 0, "total_not_harmonized": 0,
            }

        run_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        html   = _build_html(cell_summary, total_stats, run_ts)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        print(f"[Dashboard] Generated → {output_path.name}")

    # ── Private ───────────────────────────────────────────────────────────────

    def _scan_folders(self):
        extract_path    = self._extract_path
        harmonized_path = self._harmonized_path

        cell_summary = []

        if not extract_path.exists():
            return cell_summary, {
                "total_cells": 0, "total_extract": 0,
                "total_harmonized": 0, "total_not_harmonized": 0,
            }

        for cell_dir in sorted(extract_path.iterdir()):
            if not cell_dir.is_dir():
                continue
            cell_id = cell_dir.name

            # Collect all files in the extract cell folder (non-recursive)
            src_files = sorted(
                [f for f in cell_dir.iterdir() if f.is_file()],
                key=lambda f: f.name.lower(),
            )

            file_rows = []
            harmonized_count = 0

            for src in src_files:
                csv_path    = harmonized_path / cell_id / (src.stem + ".csv")
                is_harm     = csv_path.exists()
                last_edited = "—"

                if is_harm:
                    harmonized_count += 1
                    try:
                        mtime = csv_path.stat().st_mtime
                        last_edited = datetime.fromtimestamp(mtime).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                    except Exception:
                        last_edited = "—"

                file_rows.append({
                    "file_name":    src.name,
                    "is_harmonized": is_harm,
                    "last_edited":  last_edited,
                })

            not_harm = len(src_files) - harmonized_count
            cell_summary.append({
                "cell_id":           cell_id,
                "extract_count":     len(src_files),
                "harmonized_count":  harmonized_count,
                "not_harmonized_count": not_harm,
                "files":             file_rows,
            })

        total_extract    = sum(c["extract_count"]     for c in cell_summary)
        total_harmonized = sum(c["harmonized_count"]  for c in cell_summary)
        total_stats = {
            "total_cells":        len(cell_summary),
            "total_extract":      total_extract,
            "total_harmonized":   total_harmonized,
            "total_not_harmonized": total_extract - total_harmonized,
        }
        return cell_summary, total_stats


# ── HTML builder ───────────────────────────────────────────────────────────────

def _build_html(cell_summary: list, total_stats: dict, run_ts: str) -> str:
    data_json = json.dumps({"cells": cell_summary, "totals": total_stats}, indent=2)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Harmonize Dashboard</title>
<style>
  :root {{
    --blue-dark:  #1F4E79;
    --blue-mid:   #2E75B6;
    --blue-light: #D6E4F0;
    --green:      #70AD47;
    --green-bg:   #C6EFCE;
    --green-fg:   #276221;
    --red:        #FF4C4C;
    --red-bg:     #FFC7CE;
    --red-fg:     #9C0006;
    --grey-bg:    #F4F7FB;
    --grey-line:  #DEE2E6;
    --text:       #212529;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: var(--grey-bg); color: var(--text); }}

  /* ── Header ── */
  .header {{
    background: linear-gradient(135deg, var(--blue-dark) 0%, var(--blue-mid) 100%);
    color: white; padding: 20px 32px; display: flex; align-items: center; gap: 24px;
  }}
  .header h1 {{ font-size: 1.5rem; font-weight: 700; letter-spacing: .5px; }}
  .header .subtitle {{ font-size: 0.85rem; opacity: .8; margin-top: 4px; }}

  /* ── Summary cards ── */
  .cards {{ display: flex; gap: 16px; padding: 20px 32px; flex-wrap: wrap; }}
  .card {{
    background: white; border-radius: 10px; padding: 16px 24px;
    box-shadow: 0 2px 8px rgba(0,0,0,.07); min-width: 140px; flex: 1;
    border-top: 4px solid var(--blue-mid);
  }}
  .card.green {{ border-top-color: var(--green); }}
  .card.red   {{ border-top-color: var(--red); }}
  .card .val  {{ font-size: 2rem; font-weight: 700; }}
  .card .lbl  {{ font-size: 0.78rem; color: #6c757d; margin-top: 4px; text-transform: uppercase; letter-spacing: .5px; }}

  /* ── Cell table ── */
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
  td {{ padding: 10px 14px; font-size: .88rem; border-bottom: 1px solid var(--grey-line); vertical-align: middle; }}
  tr.cell-row {{ cursor: pointer; transition: background .15s; }}
  tr.cell-row:hover {{ background: var(--blue-light); }}
  tr.cell-row td:first-child::before {{ content: '▶  '; font-size: .7rem; color: var(--blue-mid); }}
  tr.cell-row.open td:first-child::before {{ content: '▼  '; }}

  /* ── Progress bar ── */
  .prog-wrap {{
    display: flex; align-items: center; gap: 8px; min-width: 140px;
  }}
  .prog-bar {{
    flex: 1; height: 10px; background: #e9ecef; border-radius: 5px; overflow: hidden;
  }}
  .prog-fill {{
    height: 100%; background: var(--green); border-radius: 5px; transition: width .3s;
  }}
  .prog-pct {{ font-size: .82rem; color: #6c757d; white-space: nowrap; }}

  /* ── Detail rows ── */
  tr.detail-row td {{ padding: 0; background: #f9fbfd; }}
  .detail-inner {{ padding: 12px 24px 16px 40px; overflow-x: auto; }}
  .detail-inner table {{ box-shadow: none; border-radius: 6px; }}
  .detail-inner th {{ background: #4472C4; font-size: .76rem; cursor: default; }}
  .detail-inner th:hover {{ background: #4472C4; }}
  .detail-inner td {{ font-size: .82rem; }}

  /* ── Badges ── */
  .badge {{
    display: inline-block; padding: 2px 10px; border-radius: 4px;
    font-size: .76rem; font-weight: 600;
  }}
  .badge-yes {{ background: var(--green-bg); color: var(--green-fg); }}
  .badge-no  {{ background: var(--red-bg);   color: var(--red-fg); }}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>TB_CPA Harmonization Dashboard</h1>
    <div class="subtitle">Generated: {run_ts} &nbsp;|&nbsp; TB_CPA_Harmonize v1.2 &nbsp;|&nbsp; Folder scan view</div>
  </div>
</div>

<div class="cards" id="cards"></div>

<div class="section">
  <h2>Cell Summary &nbsp;<small style="font-weight:normal;color:#6c757d">(click a row to expand file details)</small></h2>
  <table id="cellTable">
    <thead>
      <tr>
        <th onclick="sortTable(0)">Cell ID ⇅</th>
        <th onclick="sortTable(1)">Extract Files ⇅</th>
        <th onclick="sortTable(2)">Harmonized ⇅</th>
        <th onclick="sortTable(3)">Not Harmonized ⇅</th>
        <th>Progress</th>
      </tr>
    </thead>
    <tbody id="cellTbody"></tbody>
  </table>
</div>

<script>
const DATA = {data_json};

// ── Cards ─────────────────────────────────────────────────────────────────────
(function renderCards() {{
  const t = DATA.totals;
  const defs = [
    {{ val: t.total_cells,          lbl: 'Cell IDs',        cls: '' }},
    {{ val: t.total_extract,        lbl: 'Extract Files',   cls: '' }},
    {{ val: t.total_harmonized,     lbl: 'Harmonized',      cls: 'green' }},
    {{ val: t.total_not_harmonized, lbl: 'Not Harmonized',  cls: 'red' }},
  ];
  const wrap = document.getElementById('cards');
  defs.forEach(d => {{
    wrap.innerHTML += `<div class="card ${{d.cls}}"><div class="val">${{d.val}}</div><div class="lbl">${{d.lbl}}</div></div>`;
  }});
}})();

// ── Cell table ────────────────────────────────────────────────────────────────
const tbody = document.getElementById('cellTbody');

function progressBar(harmonized, total) {{
  const pct = total > 0 ? Math.round(harmonized / total * 100) : 0;
  return `<div class="prog-wrap">
    <div class="prog-bar"><div class="prog-fill" style="width:${{pct}}%"></div></div>
    <span class="prog-pct">${{pct}}%</span>
  </div>`;
}}

function renderFileDetail(files) {{
  let html = `<div class="detail-inner"><table>
    <thead><tr>
      <th>File Name</th>
      <th>Harmonized?</th>
      <th>Last Edited in Harmonize Folder</th>
    </tr></thead><tbody>`;
  files.forEach(f => {{
    const badge = f.is_harmonized
      ? '<span class="badge badge-yes">Yes</span>'
      : '<span class="badge badge-no">No</span>';
    html += `<tr>
      <td>${{f.file_name}}</td>
      <td>${{badge}}</td>
      <td>${{f.last_edited}}</td>
    </tr>`;
  }});
  html += '</tbody></table></div>';
  return html;
}}

DATA.cells.forEach((cell) => {{
  const tr = document.createElement('tr');
  tr.className = 'cell-row';
  tr.innerHTML = `
    <td>${{cell.cell_id}}</td>
    <td>${{cell.extract_count}}</td>
    <td>${{cell.harmonized_count}}</td>
    <td>${{cell.not_harmonized_count}}</td>
    <td>${{progressBar(cell.harmonized_count, cell.extract_count)}}</td>
  `;
  tbody.appendChild(tr);

  const detailTr = document.createElement('tr');
  detailTr.className = 'detail-row';
  detailTr.style.display = 'none';
  const detailTd = document.createElement('td');
  detailTd.colSpan = 5;
  detailTd.innerHTML = renderFileDetail(cell.files);
  detailTr.appendChild(detailTd);
  tbody.appendChild(detailTr);

  tr.addEventListener('click', () => {{
    const open = detailTr.style.display !== 'none';
    detailTr.style.display = open ? 'none' : 'table-row';
    tr.classList.toggle('open', !open);
  }});
}});

// ── Sort ──────────────────────────────────────────────────────────────────────
let _sortDir = {{}};
function sortTable(colIdx) {{
  const rows = Array.from(tbody.querySelectorAll('tr.cell-row'));
  const dir  = (_sortDir[colIdx] = !_sortDir[colIdx]);
  rows.sort((a, b) => {{
    const va = a.cells[colIdx].textContent.trim();
    const vb = b.cells[colIdx].textContent.trim();
    const na = parseFloat(va), nb = parseFloat(vb);
    const cmp = isNaN(na) ? va.localeCompare(vb) : na - nb;
    return dir ? cmp : -cmp;
  }});
  rows.forEach(r => {{
    const next = r.nextElementSibling;
    tbody.appendChild(r);
    if (next && next.classList.contains('detail-row')) tbody.appendChild(next);
  }});
}}
</script>
</body>
</html>"""
