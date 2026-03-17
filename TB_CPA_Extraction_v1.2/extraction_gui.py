"""
extraction_gui.py  —  TB_CPA_Extraction v1.2
PySide6 GUI for running multiple extraction configs.
Launch with:  python extraction_gui.py
"""

import copy
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QPalette, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QListWidget, QListWidgetItem, QPushButton, QLabel,
    QLineEdit, QCheckBox, QComboBox, QFileDialog, QPlainTextEdit,
    QScrollArea, QFrame, QMessageBox,
)

import subprocess

# ── Paths ─────────────────────────────────────────────────────────────────────

_HERE    = Path(__file__).parent
_RUNNER  = _HERE / "src" / "_gui_runner.py"
_PERSIST = _HERE / "gui_configs.json"

# ── Stylesheet (Catppuccin Mocha dark theme) ──────────────────────────────────

QSS = """
* { font-family: "Segoe UI", sans-serif; font-size: 13px; }
QMainWindow, QWidget#root { background: #1e1e2e; color: #cdd6f4; }
QSplitter::handle { background: #313244; }

QWidget#left_panel { background: #181825; }
QListWidget {
    background: #181825; border: none; outline: none; padding: 4px;
}
QListWidget::item {
    padding: 10px 12px; border-radius: 6px; margin: 2px 4px; color: #cdd6f4;
}
QListWidget::item:selected { background: #313244; color: #cba6f7; }
QListWidget::item:hover:!selected { background: #2a2a3c; }

QWidget#editor_panel { background: #1e1e2e; }
QScrollArea { background: #1e1e2e; border: none; }
QScrollArea > QWidget > QWidget { background: #1e1e2e; }

QLineEdit {
    background: #181825; color: #cdd6f4;
    border: 1px solid #313244; border-radius: 5px; padding: 5px 8px;
    selection-background-color: #45475a;
}
QLineEdit:focus { border-color: #cba6f7; }

QComboBox {
    background: #181825; color: #cdd6f4;
    border: 1px solid #313244; border-radius: 5px; padding: 5px 8px;
}
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background: #181825; color: #cdd6f4;
    selection-background-color: #45475a; border: 1px solid #313244;
}

QCheckBox { spacing: 8px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #585b70; border-radius: 3px; background: #181825;
}
QCheckBox::indicator:checked { background: #cba6f7; border-color: #cba6f7; }

QPushButton {
    background: #313244; color: #cdd6f4; border: none; border-radius: 5px; padding: 6px 14px;
}
QPushButton:hover { background: #45475a; }
QPushButton:disabled { color: #585b70; background: #1e1e2e; }

QPushButton#run_btn { background: #a6e3a1; color: #1e1e2e; font-weight: bold; padding: 7px 18px; }
QPushButton#run_btn:hover { background: #94d49d; }
QPushButton#run_btn:disabled { background: #2d4a35; color: #4a7a52; }

QPushButton#stop_btn { background: #f38ba8; color: #1e1e2e; font-weight: bold; padding: 7px 18px; }
QPushButton#stop_btn:hover { background: #e07090; }

QPushButton#run_all_btn { background: #89b4fa; color: #1e1e2e; font-weight: bold; padding: 7px 18px; }
QPushButton#run_all_btn:hover { background: #74a0e8; }
QPushButton#run_all_btn:disabled { background: #1e3050; color: #3a5070; }

QPushButton#add_btn    { background: #313244; color: #a6e3a1; }
QPushButton#remove_btn { background: #313244; color: #f38ba8; }
QPushButton#dup_btn    { background: #313244; color: #89b4fa; }

QPlainTextEdit#console {
    background: #11111b; color: #a6e3a1; border: none;
    border-top: 1px solid #313244;
    font-family: Consolas, "Courier New", monospace; font-size: 11px; padding: 6px;
}

QLabel#section_label { color: #585b70; font-size: 10px; font-weight: bold; letter-spacing: 1px; }
QLabel#title_label   { color: #cba6f7; font-size: 16px; font-weight: bold; }
QLabel#status_label  { font-size: 12px; }

QFrame#divider { color: #313244; background: #313244; max-height: 1px; }
QWidget#toolbar { background: #181825; border-bottom: 1px solid #313244; }
"""

# ── Status indicators ─────────────────────────────────────────────────────────

STATUS_IDLE    = ("● Idle",    "#585b70")
STATUS_RUNNING = ("⏳ Running", "#f9e2af")
STATUS_DONE    = ("✔ Done",    "#a6e3a1")
STATUS_FAILED  = ("✗ Failed",  "#f38ba8")
STATUS_STOPPED = ("■ Stopped", "#fab387")


def _default_config() -> dict:
    return {
        "name":               "New Config",
        "base_path":          "",
        "zip_files":          [],        # [] = all; ["Peak"] = filter
        "copy_action":        "skip_copy",
        "generate_dashboard": True,
    }


# ── RunWorker ─────────────────────────────────────────────────────────────────

class RunWorker(QThread):
    line_received = Signal(str)
    finished      = Signal(bool, str)   # success, message

    def __init__(self, config: dict):
        super().__init__()
        self._config  = config
        self._process = None
        self._stopped = False

    def run(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tf:
            json.dump(self._config, tf)
            tmp_path = tf.name

        try:
            self._process = subprocess.Popen(
                [sys.executable, str(_RUNNER), tmp_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                cwd=str(_HERE),
            )
            for line in self._process.stdout:
                self.line_received.emit(line.rstrip())
            self._process.wait()

            if self._stopped:
                self.finished.emit(False, "Stopped by user.")
            elif self._process.returncode == 0:
                self.finished.emit(True, "Completed successfully.")
            else:
                self.finished.emit(False, f"Exited with code {self._process.returncode}.")
        except Exception as e:
            self.finished.emit(False, str(e))
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass

    def stop(self):
        self._stopped = True
        if self._process and self._process.poll() is None:
            self._process.terminate()


# ── ConfigEditorWidget ────────────────────────────────────────────────────────

class ConfigEditorWidget(QWidget):
    run_requested  = Signal(dict)
    stop_requested = Signal()
    config_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("editor_panel")
        self._loading = False
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        inner = QWidget()
        inner.setObjectName("editor_panel")
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Config name
        layout.addWidget(self._section("CONFIG NAME"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Project B2-2")
        self.name_edit.textChanged.connect(self._on_change)
        layout.addWidget(self.name_edit)

        # Base path
        layout.addWidget(self._section("BASE PATH"))
        path_row = QHBoxLayout()
        path_row.setSpacing(6)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Root folder containing 01_Incoming_Compressed_Files/")
        self.path_edit.textChanged.connect(self._on_change)
        browse_btn = QPushButton("📁")
        browse_btn.setFixedWidth(36)
        browse_btn.setToolTip("Browse for folder")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self.path_edit)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        # ZIP filter
        layout.addWidget(self._section("ZIP FILE FILTER  —  substrings to match (blank = all)"))
        self.zip_filter_edit = QLineEdit()
        self.zip_filter_edit.setPlaceholderText("e.g. Peak, Cycle_01  —  leave blank to process every archive")
        self.zip_filter_edit.textChanged.connect(self._on_change)
        layout.addWidget(self.zip_filter_edit)
        hint = QLabel("Comma-separated substrings.  Only archives whose filename contains one of these will be processed.")
        hint.setStyleSheet("color: #585b70; font-size: 11px; font-style: italic;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Copy action
        layout.addWidget(self._section("DUPLICATE FILE BEHAVIOUR"))
        self.copy_action_cb = QComboBox()
        self.copy_action_cb.addItems(["skip_copy", "replace", "create_copy"])
        self.copy_action_cb.setToolTip(
            "skip_copy   — leave the existing destination file untouched (recommended)\n"
            "replace     — overwrite the existing file\n"
            "create_copy — save alongside existing file with a _copy suffix"
        )
        self.copy_action_cb.currentIndexChanged.connect(self._on_change)
        layout.addWidget(self.copy_action_cb)

        # Dashboard
        layout.addWidget(self._section("DASHBOARD"))
        self.dashboard_cb = QCheckBox("Generate HTML dashboard after run")
        self.dashboard_cb.stateChanged.connect(self._on_change)
        layout.addWidget(self.dashboard_cb)

        # Divider
        layout.addSpacing(8)
        div = QFrame()
        div.setObjectName("divider")
        div.setFrameShape(QFrame.HLine)
        layout.addWidget(div)
        layout.addSpacing(4)

        # Status
        status_row = QHBoxLayout()
        self.status_label = QLabel("● Idle")
        self.status_label.setObjectName("status_label")
        self._set_status_color("#585b70")
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        layout.addLayout(status_row)

        # Run / Stop
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.run_btn = QPushButton("▶  Run This Config")
        self.run_btn.setObjectName("run_btn")
        self.run_btn.clicked.connect(self._emit_run)
        self.stop_btn = QPushButton("■  Stop")
        self.stop_btn.setObjectName("stop_btn")
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self.stop_requested)
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addStretch()

        scroll.setWidget(inner)
        outer.addWidget(scroll)

    def _section(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("section_label")
        return lbl

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Base Path")
        if folder:
            self.path_edit.setText(folder)

    def _on_change(self):
        if not self._loading:
            self.config_changed.emit()

    def _set_status_color(self, color: str):
        self.status_label.setStyleSheet(f"color: {color};")

    def set_status(self, text: str, color: str):
        self.status_label.setText(text)
        self._set_status_color(color)

    def set_running(self, running: bool):
        self.run_btn.setVisible(not running)
        self.stop_btn.setVisible(running)
        self.run_btn.setEnabled(not running)

    def load_config(self, cfg: dict):
        self._loading = True
        self.name_edit.setText(cfg.get("name", ""))
        self.path_edit.setText(cfg.get("base_path", ""))
        zip_f = cfg.get("zip_files") or []
        self.zip_filter_edit.setText(", ".join(zip_f))
        idx = self.copy_action_cb.findText(cfg.get("copy_action", "skip_copy"))
        self.copy_action_cb.setCurrentIndex(max(idx, 0))
        self.dashboard_cb.setChecked(cfg.get("generate_dashboard", True))
        self.set_status(*STATUS_IDLE)
        self.set_running(False)
        self._loading = False

    def read_config(self) -> dict:
        def _parse_list(text: str) -> list:
            return [s.strip() for s in text.split(",") if s.strip()]

        zip_f = _parse_list(self.zip_filter_edit.text())
        return {
            "name":               self.name_edit.text().strip() or "Unnamed",
            "base_path":          self.path_edit.text().strip(),
            "zip_files":          zip_f if zip_f else [],
            "copy_action":        self.copy_action_cb.currentText(),
            "generate_dashboard": self.dashboard_cb.isChecked(),
        }

    def _emit_run(self):
        self.run_requested.emit(self.read_config())


# ── ConsoleWidget ─────────────────────────────────────────────────────────────

class ConsoleWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("toolbar")
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(10, 4, 10, 4)
        lbl = QLabel("CONSOLE OUTPUT")
        lbl.setObjectName("section_label")
        hlay.addWidget(lbl)
        hlay.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedHeight(24)
        copy_btn = QPushButton("Copy All")
        copy_btn.setFixedHeight(24)
        clear_btn.clicked.connect(self.clear)
        copy_btn.clicked.connect(self.copy_all)
        hlay.addWidget(clear_btn)
        hlay.addWidget(copy_btn)
        layout.addWidget(header)

        self.text = QPlainTextEdit()
        self.text.setObjectName("console")
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(5000)
        layout.addWidget(self.text)

    def append(self, line: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.text.appendPlainText(f"[{ts}]  {line}")
        self.text.moveCursor(QTextCursor.End)

    def clear(self):
        self.text.clear()

    def copy_all(self):
        QApplication.clipboard().setText(self.text.toPlainText())


# ── MainWindow ────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Extraction Runner  —  TB_CPA_Extraction v1.2")
        self.resize(1100, 720)

        self._configs: list[dict] = []
        self._current_idx: int = -1
        self._worker: RunWorker | None = None
        self._run_all_queue: list[int] = []

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Toolbar ──
        toolbar = QWidget()
        toolbar.setObjectName("toolbar")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(16, 10, 16, 10)
        tb.setSpacing(10)
        title = QLabel("⚡ Extraction Runner")
        title.setObjectName("title_label")
        tb.addWidget(title)
        tb.addStretch()

        self.run_all_btn = QPushButton("▶▶  Run All")
        self.run_all_btn.setObjectName("run_all_btn")
        self.run_all_btn.clicked.connect(self._run_all)
        save_btn = QPushButton("💾  Save Configs")
        save_btn.clicked.connect(self._save_configs)
        load_btn = QPushButton("📂  Load Configs")
        load_btn.clicked.connect(self._load_configs)
        for btn in (self.run_all_btn, save_btn, load_btn):
            tb.addWidget(btn)
        root_layout.addWidget(toolbar)

        # ── Body splitter ──
        body_split = QSplitter(Qt.Horizontal)
        body_split.setHandleWidth(2)

        # Left panel — project list
        left = QWidget()
        left.setObjectName("left_panel")
        left.setMinimumWidth(200)
        left.setMaximumWidth(280)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(10, 12, 10, 12)
        ll.setSpacing(8)
        ll.addWidget(self._slabel("CONFIGS"))

        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self._on_select)
        ll.addWidget(self.list_widget)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        add_btn = QPushButton("+")
        add_btn.setObjectName("add_btn")
        add_btn.setFixedWidth(36)
        add_btn.setToolTip("Add config")
        add_btn.clicked.connect(self._add_config)
        rem_btn = QPushButton("✕")
        rem_btn.setObjectName("remove_btn")
        rem_btn.setFixedWidth(36)
        rem_btn.setToolTip("Remove selected")
        rem_btn.clicked.connect(self._remove_config)
        dup_btn = QPushButton("⧉")
        dup_btn.setObjectName("dup_btn")
        dup_btn.setFixedWidth(36)
        dup_btn.setToolTip("Duplicate selected")
        dup_btn.clicked.connect(self._duplicate_config)
        for b in (add_btn, rem_btn, dup_btn):
            btn_row.addWidget(b)
        btn_row.addStretch()
        ll.addLayout(btn_row)
        body_split.addWidget(left)

        # Right panel — editor
        self.editor = ConfigEditorWidget()
        self.editor.run_requested.connect(self._run_config)
        self.editor.stop_requested.connect(self._stop)
        self.editor.config_changed.connect(self._on_editor_change)
        body_split.addWidget(self.editor)
        body_split.setStretchFactor(0, 0)
        body_split.setStretchFactor(1, 1)

        # Vertical splitter — body + console
        v_split = QSplitter(Qt.Vertical)
        v_split.setHandleWidth(2)
        v_split.addWidget(body_split)
        self.console = ConsoleWidget()
        v_split.addWidget(self.console)
        v_split.setStretchFactor(0, 3)
        v_split.setStretchFactor(1, 1)
        root_layout.addWidget(v_split)

        self._auto_load()

    def _slabel(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("section_label")
        return lbl

    # ── Config list ───────────────────────────────────────────────────────────

    def _refresh_list(self):
        self.list_widget.clear()
        for cfg in self._configs:
            self.list_widget.addItem(QListWidgetItem(cfg.get("name", "Unnamed")))

    def _add_config(self):
        self._configs.append(_default_config())
        self._refresh_list()
        self.list_widget.setCurrentRow(len(self._configs) - 1)

    def _remove_config(self):
        idx = self.list_widget.currentRow()
        if idx < 0:
            return
        self._configs.pop(idx)
        self._refresh_list()
        new_idx = min(idx, len(self._configs) - 1)
        if new_idx >= 0:
            self.list_widget.setCurrentRow(new_idx)
        else:
            self._current_idx = -1

    def _duplicate_config(self):
        idx = self.list_widget.currentRow()
        if idx < 0:
            return
        dup = copy.deepcopy(self._configs[idx])
        dup["name"] += " (copy)"
        self._configs.insert(idx + 1, dup)
        self._refresh_list()
        self.list_widget.setCurrentRow(idx + 1)

    def _on_select(self, row: int):
        if row < 0 or row >= len(self._configs):
            self._current_idx = -1
            return
        self._current_idx = row
        self.editor.load_config(self._configs[row])

    def _on_editor_change(self):
        if self._current_idx < 0:
            return
        updated = self.editor.read_config()
        self._configs[self._current_idx] = updated
        self.list_widget.item(self._current_idx).setText(updated["name"])

    # ── Run logic ─────────────────────────────────────────────────────────────

    def _run_config(self, cfg: dict):
        if self._worker and self._worker.isRunning():
            return
        if not cfg.get("base_path"):
            QMessageBox.warning(self, "Missing Path", "Please set a Base Path before running.")
            return
        self._start_worker(cfg, self._current_idx)

    def _start_worker(self, cfg: dict, cfg_idx: int):
        self.console.append(f"━━━  Starting: {cfg['name']}  ━━━")
        self.editor.set_status(*STATUS_RUNNING)
        self.editor.set_running(True)
        self.run_all_btn.setEnabled(False)

        self._worker = RunWorker(cfg)
        self._worker.line_received.connect(self.console.append)
        self._worker.finished.connect(lambda ok, msg: self._on_finished(ok, msg, cfg_idx))
        self._worker.start()

    def _on_finished(self, ok: bool, msg: str, cfg_idx: int):
        self.editor.set_running(False)
        if ok:
            self.editor.set_status(*STATUS_DONE)
            self.console.append(f"✔ {msg}")
        elif "Stopped" in msg:
            self.editor.set_status(*STATUS_STOPPED)
            self.console.append(f"■ {msg}")
        else:
            self.editor.set_status(*STATUS_FAILED)
            self.console.append(f"✗ {msg}")

        self._worker = None
        if self._run_all_queue:
            next_idx = self._run_all_queue.pop(0)
            if 0 <= next_idx < len(self._configs):
                self.list_widget.setCurrentRow(next_idx)
                self._start_worker(self._configs[next_idx], next_idx)
            else:
                self._finish_run_all()
        else:
            self.run_all_btn.setEnabled(True)

    def _finish_run_all(self):
        self.run_all_btn.setEnabled(True)
        self.console.append("━━━  All configs finished.  ━━━")

    def _stop(self):
        if self._worker:
            self._run_all_queue.clear()
            self._worker.stop()

    def _run_all(self):
        if not self._configs or (self._worker and self._worker.isRunning()):
            return
        queue = [i for i, c in enumerate(self._configs) if c.get("base_path")]
        if not queue:
            QMessageBox.warning(self, "No Paths", "Please set Base Paths for your configs first.")
            return
        first = queue.pop(0)
        self._run_all_queue = queue
        self.list_widget.setCurrentRow(first)
        self._start_worker(self._configs[first], first)

    # ── Persistence ───────────────────────────────────────────────────────────

    def _auto_load(self):
        if _PERSIST.exists():
            try:
                with open(_PERSIST, "r", encoding="utf-8") as f:
                    self._configs = json.load(f)
                self._refresh_list()
                if self._configs:
                    self.list_widget.setCurrentRow(0)
                self.console.append(f"Loaded {len(self._configs)} config(s) from {_PERSIST.name}")
            except Exception as e:
                self.console.append(f"[WARN] Could not load {_PERSIST.name}: {e}")

    def _auto_save(self):
        try:
            with open(_PERSIST, "w", encoding="utf-8") as f:
                json.dump(self._configs, f, indent=2)
        except Exception as e:
            self.console.append(f"[WARN] Auto-save failed: {e}")

    def _save_configs(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Configs", str(_PERSIST), "JSON Files (*.json)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._configs, f, indent=2)
            self.console.append(f"Configs saved → {path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _load_configs(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Configs", str(_PERSIST), "JSON Files (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._configs = json.load(f)
            self._refresh_list()
            if self._configs:
                self.list_widget.setCurrentRow(0)
            self.console.append(f"Loaded {len(self._configs)} config(s) from {path}")
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))

    def closeEvent(self, event):
        if self._current_idx >= 0:
            self._configs[self._current_idx] = self.editor.read_config()
        self._auto_save()
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
        super().closeEvent(event)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Extraction Runner")
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)

    palette = QPalette()
    palette.setColor(QPalette.Window,          QColor("#1e1e2e"))
    palette.setColor(QPalette.WindowText,      QColor("#cdd6f4"))
    palette.setColor(QPalette.Base,            QColor("#181825"))
    palette.setColor(QPalette.AlternateBase,   QColor("#313244"))
    palette.setColor(QPalette.Text,            QColor("#cdd6f4"))
    palette.setColor(QPalette.Button,          QColor("#313244"))
    palette.setColor(QPalette.ButtonText,      QColor("#cdd6f4"))
    palette.setColor(QPalette.Highlight,       QColor("#cba6f7"))
    palette.setColor(QPalette.HighlightedText, QColor("#1e1e2e"))
    app.setPalette(palette)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
