import sys
import os
import time
import random
import logging
import traceback
import pyautogui
from pynput import keyboard
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QSpinBox, QDoubleSpinBox,
    QTextEdit, QGroupBox, QMessageBox, QComboBox, QCheckBox,
    QGridLayout, QFrame, QSizePolicy
)
from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot, Qt
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon

# ==========================================
# 1. Logging Setup
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("automation.log", mode='a', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)
pyautogui.FAILSAFE = True

# ==========================================
# 2. Style Constants
# ==========================================
BG            = "#f5f5f3"
CARD_BG       = "#ffffff"
PANEL_BG      = "#f0eeea"
BORDER        = "#dddbd4"
BORDER_FOCUS  = "#378add"
TEXT_PRIMARY  = "#1a1a18"
TEXT_MUTED    = "#5f5e5a"
TEXT_DIM      = "#888780"
SUCCESS_BG    = "#eaf3de"
SUCCESS_FG    = "#3b6d11"
SUCCESS_BR    = "#97c459"
DANGER        = "#a32d2d"
DANGER_BG     = "#fcebeb"
WARNING       = "#854f0b"

APP_STYLE = f"""
QMainWindow, QWidget {{
    background-color: {BG};
    color: {TEXT_PRIMARY};
    font-family: 'Segoe UI', 'SF Pro Display', 'Helvetica Neue', Arial, sans-serif;
    font-size: 13px;
}}

/* ── Group boxes ──────────────────────────── */
QGroupBox {{
    background-color: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 10px;
    margin-top: 14px;
    padding: 14px 16px 12px 16px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.4px;
    color: {TEXT_MUTED};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    top: -1px;
    padding: 0 6px;
    background-color: {CARD_BG};
}}

/* ── Labels ───────────────────────────────── */
QLabel {{
    color: {TEXT_MUTED};
    font-size: 12px;
    background: transparent;
}}
QLabel#heading {{
    color: {TEXT_PRIMARY};
    font-size: 18px;
    font-weight: 500;
}}
QLabel#subheading {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}
QLabel#path_label {{
    color: {TEXT_DIM};
    font-size: 11px;
    font-style: italic;
}}

/* ── Spin boxes ───────────────────────────── */
QSpinBox, QDoubleSpinBox {{
    background-color: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    color: {TEXT_PRIMARY};
    padding: 5px 8px;
    min-height: 28px;
    font-size: 13px;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {BORDER_FOCUS};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    background-color: {BORDER};
    border: none;
    width: 16px;
    border-radius: 3px;
    margin: 2px;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: #c0beb6;
}}

/* ── Combo box ────────────────────────────── */
QComboBox {{
    background-color: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    color: {TEXT_PRIMARY};
    padding: 5px 8px;
    min-height: 28px;
    font-size: 13px;
}}
QComboBox:focus {{ border: 1px solid {BORDER_FOCUS}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background-color: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    color: {TEXT_PRIMARY};
    selection-background-color: #e6f1fb;
    selection-color: {TEXT_PRIMARY};
    padding: 4px;
}}

/* ── Check box ────────────────────────────── */
QCheckBox {{
    color: {TEXT_PRIMARY};
    font-size: 12px;
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border-radius: 4px;
    border: 1px solid {BORDER};
    background-color: {PANEL_BG};
}}
QCheckBox::indicator:checked {{
    background-color: {SUCCESS_BG};
    border: 1px solid {SUCCESS_BR};
    image: none;
}}
QCheckBox::indicator:hover {{
    border: 1px solid {BORDER_FOCUS};
}}

/* ── Text edit (log console) ──────────────── */
QTextEdit {{
    background-color: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
    color: {TEXT_MUTED};
    font-family: 'Cascadia Code', 'Fira Code', 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    padding: 10px;
}}

/* ── Scrollbar ────────────────────────────── */
QScrollBar:vertical {{
    background: {PANEL_BG};
    width: 6px;
    border-radius: 3px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {TEXT_DIM}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

/* ── Generic QPushButton ──────────────────── */
QPushButton {{
    background-color: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 7px;
    color: {TEXT_PRIMARY};
    padding: 8px 14px;
    font-size: 12px;
    font-weight: 500;
    min-height: 32px;
}}
QPushButton:hover {{
    background-color: #e8e6e0;
    border: 1px solid #c0beb6;
}}
QPushButton:pressed {{ background-color: {BORDER}; }}
QPushButton:disabled {{ color: {TEXT_DIM}; border-color: {BORDER}; }}

/* ── Browse buttons ───────────────────────── */
QPushButton#browse_btn {{
    background-color: {PANEL_BG};
    border: 1px dashed {BORDER};
    border-radius: 7px;
    color: {TEXT_MUTED};
    padding: 8px 14px;
    font-size: 12px;
    text-align: left;
}}
QPushButton#browse_btn:hover {{
    border: 1px dashed {BORDER_FOCUS};
    color: {BORDER_FOCUS};
    background-color: #e6f1fb;
}}
QPushButton#browse_btn[selected="true"] {{
    border: 1px solid {SUCCESS_BR};
    color: {SUCCESS_FG};
    background-color: {SUCCESS_BG};
}}

/* ── START button ─────────────────────────── */
QPushButton#start_btn {{
    background-color: {TEXT_PRIMARY};
    border: none;
    border-radius: 8px;
    color: #ffffff;
    font-size: 13px;
    font-weight: 500;
    min-height: 44px;
}}
QPushButton#start_btn:hover {{ background-color: #2c2c2a; border: none; }}
QPushButton#start_btn:pressed {{ background-color: #444441; }}
QPushButton#start_btn:disabled {{ background-color: {BORDER}; color: {TEXT_DIM}; }}

/* ── STOP button ──────────────────────────── */
QPushButton#stop_btn {{
    background-color: transparent;
    border: 1px solid {BORDER};
    border-radius: 8px;
    color: {DANGER};
    font-size: 13px;
    font-weight: 500;
    min-height: 44px;
}}
QPushButton#stop_btn:hover {{
    background-color: {DANGER_BG};
    border: 1px solid #f09595;
}}
QPushButton#stop_btn:disabled {{ color: {TEXT_DIM}; border-color: {BORDER}; }}

/* ── Divider ──────────────────────────────── */
QFrame#divider {{
    background-color: {BORDER};
    max-height: 1px;
    border: none;
}}
"""

# ==========================================
# 3. Automation Worker Thread
# ==========================================
class AutomationWorker(QThread):
    log_signal      = pyqtSignal(str)
    error_signal    = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.is_running = True
        self.screen_width, self.screen_height = pyautogui.size()

    def apply_randomization(self, base_delay):
        if self.config['humanize']:
            variance = base_delay * 0.20
            return random.uniform(base_delay - variance, base_delay + variance)
        return base_delay

    def perform_action(self, x, y, action_type):
        if not (0 <= x < self.screen_width and 0 <= y < self.screen_height):
            raise ValueError(f"Coordinates ({x}, {y}) are outside screen bounds.")
        if action_type == 'Left Click':
            pyautogui.click(x, y)
        elif action_type == 'Right Click':
            pyautogui.click(x, y, button='right')
        elif action_type == 'Double Click':
            pyautogui.doubleClick(x, y)
        elif action_type == 'Hover':
            pyautogui.moveTo(x, y, duration=0.2)
        else:
            pyautogui.moveTo(x, y)

    def run(self):
        try:
            initial_delay = self.config['initial_delay']
            if initial_delay > 0:
                self.log_signal.emit(f"⏱  Starting in {initial_delay:.0f}s — switch to your target window.")
                time.sleep(initial_delay)

            self.log_signal.emit("▶  Running  ·  Move mouse to screen corner to abort (fail-safe).")
            cycle_count = 1

            while self.is_running:
                if self.config['max_cycles'] > 0 and cycle_count > self.config['max_cycles']:
                    self.log_signal.emit(f"✓  Max cycles ({self.config['max_cycles']}) reached.")
                    break

                self.log_signal.emit(f"┄  Cycle {cycle_count}")

                # Image 1
                self.log_signal.emit("   Searching for Image 1…")
                img1_found = False
                t0 = time.time()
                while self.is_running and not img1_found:
                    if time.time() - t0 > self.config['search_timeout']:
                        self.log_signal.emit(f"   ⚠  Image 1 not found after {self.config['search_timeout']}s. Restarting cycle.")
                        break
                    try:
                        matches = list(pyautogui.locateAllOnScreen(self.config['img1_path'], confidence=self.config['confidence']))
                        if matches:
                            matches.sort(key=lambda b: b.top)
                            cx, cy = pyautogui.center(matches[0])
                            tx = cx + self.config['img1_offset_x']
                            ty = cy + self.config['img1_offset_y']
                            self.log_signal.emit(f"   ✓  Image 1 → {self.config['img1_action']} at ({tx}, {ty})")
                            self.perform_action(tx, ty, self.config['img1_action'])
                            img1_found = True
                        else:
                            time.sleep(0.5)
                    except pyautogui.ImageNotFoundException:
                        time.sleep(0.5)
                    except ValueError as ve:
                        self.error_signal.emit(str(ve)); break

                if not self.is_running: break
                if not img1_found:
                    time.sleep(self.apply_randomization(self.config['cycle_delay'])); continue

                time.sleep(self.apply_randomization(self.config['click_delay']))

                # Image 2
                self.log_signal.emit("   Searching for Image 2…")
                img2_found = False
                t0 = time.time()
                while self.is_running and not img2_found:
                    if time.time() - t0 > self.config['search_timeout']:
                        self.log_signal.emit(f"   ⚠  Image 2 not found after {self.config['search_timeout']}s. Restarting cycle.")
                        break
                    try:
                        m2 = pyautogui.locateOnScreen(self.config['img2_path'], confidence=self.config['confidence'])
                        if m2:
                            cx, cy = pyautogui.center(m2)
                            tx = cx + self.config['img2_offset_x']
                            ty = cy + self.config['img2_offset_y']
                            self.log_signal.emit(f"   ✓  Image 2 → {self.config['img2_action']} at ({tx}, {ty})")
                            self.perform_action(tx, ty, self.config['img2_action'])
                            img2_found = True
                        else:
                            time.sleep(0.5)
                    except pyautogui.ImageNotFoundException:
                        time.sleep(0.5)
                    except ValueError as ve:
                        self.error_signal.emit(str(ve)); break

                if not self.is_running: break

                delay = self.apply_randomization(self.config['cycle_delay'])
                self.log_signal.emit(f"   Cycle {cycle_count} done · next in {delay:.1f}s")
                cycle_count += 1

                elapsed = 0.0
                while self.is_running and elapsed < delay:
                    time.sleep(0.1); elapsed += 0.1

        except pyautogui.FailSafeException:
            self.error_signal.emit("FAIL-SAFE: Mouse moved to corner. Automation aborted.")
        except Exception as e:
            logger.error(traceback.format_exc())
            self.error_signal.emit(f"Critical error: {e}")
        finally:
            self.log_signal.emit("■  Stopped.")
            self.finished_signal.emit()

    def stop(self):
        self.is_running = False


# ==========================================
# 4. Compact labeled field helper
# ==========================================
def labeled_row(label_text, widget):
    """Returns a QWidget containing a label above the input widget."""
    container = QWidget()
    container.setStyleSheet("background: transparent;")
    v = QVBoxLayout(container)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(4)
    lbl = QLabel(label_text)
    lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 600; letter-spacing: 0.6px;")
    v.addWidget(lbl)
    v.addWidget(widget)
    return container


def make_spinbox(min_val=0, max_val=9999, step=1, default=0, decimals=None, suffix=""):
    if decimals is not None:
        w = QDoubleSpinBox()
        w.setDecimals(decimals)
        w.setSingleStep(step)
    else:
        w = QSpinBox()
    w.setRange(min_val, max_val)
    w.setValue(default)
    if suffix:
        w.setSuffix(suffix)
    return w


def divider():
    f = QFrame()
    f.setObjectName("divider")
    f.setFrameShape(QFrame.Shape.HLine)
    f.setFixedHeight(1)
    return f


# ==========================================
# 5. Main Window
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Automation Bot")
        self.resize(680, 620)
        self.setMinimumWidth(640)
        self.worker = None
        self.hotkey_listener = None
        self.img1_path = ""
        self.img2_path = ""
        self.init_ui()
        self.setup_hotkeys()

    # ── UI construction ────────────────────────────────────────────
    def init_ui(self):
        root = QWidget()
        root.setStyleSheet(f"background-color: {BG};")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(16, 14, 16, 12)
        outer.setSpacing(8)

        # ── Header ─────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(0)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        h1 = QLabel("Automation Bot")
        h1.setObjectName("heading")
        sub = QLabel("Image recognition · click automation · cycle control")
        sub.setObjectName("subheading")
        title_col.addWidget(h1)
        title_col.addWidget(sub)

        self.status_badge = QLabel("Idle")
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.status_badge.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 500; "
            f"background: {PANEL_BG}; "
            f"border: 1px solid {BORDER}; border-radius: 6px; padding: 3px 10px;"
        )

        header.addLayout(title_col)
        header.addStretch()
        header.addWidget(self.status_badge)
        outer.addLayout(header)
        outer.addWidget(divider())

        # ── Targets ────────────────────────────────────────────────
        targets_group = QGroupBox("Target Images")
        tg_layout = QVBoxLayout(targets_group)
        tg_layout.setContentsMargins(12, 10, 12, 8)
        tg_layout.setSpacing(6)

        for idx in (1, 2):
            row = QHBoxLayout()
            row.setSpacing(10)

            btn = QPushButton(f"  ＋  Select Image {idx}")
            btn.setObjectName("browse_btn")
            btn.setProperty("selected", "false")
            btn.setMinimumWidth(190)
            btn.clicked.connect(lambda _, n=idx: self.browse_image(n))

            cmb = QComboBox()
            cmb.addItems(["Left Click", "Right Click", "Double Click", "Hover"])
            cmb.setFixedWidth(130)

            spinx = make_spinbox(-2000, 2000, 1, 0)
            spinx.setPrefix("X  ")
            spinx.setFixedWidth(90)

            spiny = make_spinbox(-2000, 2000, 1, 0)
            spiny.setPrefix("Y  ")
            spiny.setFixedWidth(90)

            path_lbl = QLabel("No file selected")
            path_lbl.setObjectName("path_label")
            path_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

            row.addWidget(btn)
            row.addWidget(labeled_row("Action", cmb))
            row.addWidget(labeled_row("X Offset", spinx))
            row.addWidget(labeled_row("Y Offset", spiny))
            row.addStretch()

            tg_layout.addLayout(row)
            tg_layout.addWidget(path_lbl)
            if idx == 1:
                tg_layout.addWidget(divider())

            if idx == 1:
                self.btn_browse1, self.cmb_action1 = btn, cmb
                self.spin_x1, self.spin_y1 = spinx, spiny
                self.lbl_path1 = path_lbl
            else:
                self.btn_browse2, self.cmb_action2 = btn, cmb
                self.spin_x2, self.spin_y2 = spinx, spiny
                self.lbl_path2 = path_lbl

        outer.addWidget(targets_group)

        # ── Settings ───────────────────────────────────────────────
        settings_group = QGroupBox("Timing & Behaviour")
        sg = QGridLayout(settings_group)
        sg.setContentsMargins(12, 10, 12, 8)
        sg.setHorizontalSpacing(12)
        sg.setVerticalSpacing(6)

        self.spin_initial_delay = make_spinbox(0, 60, 0.5, 3.0, decimals=1, suffix=" s")
        self.spin_click_delay   = make_spinbox(0, 60, 0.5, 1.5, decimals=1, suffix=" s")
        self.spin_cycle_delay   = make_spinbox(0, 300, 0.5, 3.0, decimals=1, suffix=" s")
        self.spin_max_cycles    = make_spinbox(0, 99999, 1, 0)
        self.spin_max_cycles.setSpecialValueText("∞")
        self.spin_timeout       = make_spinbox(1, 300, 1, 15, decimals=1, suffix=" s")
        self.spin_conf          = make_spinbox(10, 99, 5, 85, decimals=None, suffix=" %")

        pairs = [
            ("Init Delay",    self.spin_initial_delay, "Img 1 → 2 Delay", self.spin_click_delay),
            ("Cycle Delay",   self.spin_cycle_delay,   "Max Cycles",       self.spin_max_cycles),
            ("Search Timeout", self.spin_timeout,      "Match Confidence", self.spin_conf),
        ]
        for row_i, (l1, w1, l2, w2) in enumerate(pairs):
            sg.addWidget(labeled_row(l1, w1), row_i, 0)
            sg.addWidget(labeled_row(l2, w2), row_i, 1)

        self.chk_humanize = QCheckBox("Humanize delays  (randomize ± 20% to reduce detection)")
        self.chk_humanize.setChecked(True)
        sg.addWidget(self.chk_humanize, 3, 0, 1, 2)

        outer.addWidget(settings_group)

        # ── Controls ───────────────────────────────────────────────
        ctrl = QHBoxLayout()
        ctrl.setSpacing(10)

        self.btn_start = QPushButton("▶  START")
        self.btn_start.setObjectName("start_btn")
        self.btn_start.clicked.connect(self.start_automation)

        self.btn_stop = QPushButton("■  STOP  ·  F9")
        self.btn_stop.setObjectName("stop_btn")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_automation)

        ctrl.addWidget(self.btn_start, 3)
        ctrl.addWidget(self.btn_stop, 2)
        outer.addLayout(ctrl)

        # ── Log console ────────────────────────────────────────────
        log_header = QHBoxLayout()
        log_lbl = QLabel("EXECUTION LOG")
        log_lbl.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 10px; font-weight: 700; letter-spacing: 1.4px;"
        )
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(60)
        clear_btn.setFixedHeight(22)
        clear_btn.setStyleSheet(
            f"background: transparent; border: none; color: {TEXT_DIM}; font-size: 11px;"
            f"padding: 0;"
        )
        clear_btn.clicked.connect(lambda: self.log_console.clear())
        log_header.addWidget(log_lbl)
        log_header.addStretch()
        log_header.addWidget(clear_btn)
        outer.addLayout(log_header)

        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMinimumHeight(100)
        self.log_console.setMaximumHeight(180)
        outer.addWidget(self.log_console)
        outer.addStretch()

        self.setCentralWidget(root)

    # ── Hotkey ─────────────────────────────────────────────────────
    def setup_hotkeys(self):
        def on_press(key):
            if key == keyboard.Key.f9 and self.worker and self.worker.is_running:
                self.log_message("F9 — emergency stop requested.")
                self.stop_automation()
        self.hotkey_listener = keyboard.Listener(on_press=on_press)
        self.hotkey_listener.start()

    # ── Browse ─────────────────────────────────────────────────────
    def browse_image(self, img_num):
        path, _ = QFileDialog.getOpenFileName(
            self, f"Select Image {img_num}", "",
            "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )
        if not path:
            return
        name = os.path.basename(path)
        short = name if len(name) <= 32 else name[:29] + "…"
        if img_num == 1:
            self.img1_path = path
            self.btn_browse1.setText(f"  ✓  {short}")
            self.btn_browse1.setProperty("selected", "true")
            self.btn_browse1.style().unpolish(self.btn_browse1)
            self.btn_browse1.style().polish(self.btn_browse1)
            self.lbl_path1.setText(path)
        else:
            self.img2_path = path
            self.btn_browse2.setText(f"  ✓  {short}")
            self.btn_browse2.setProperty("selected", "true")
            self.btn_browse2.style().unpolish(self.btn_browse2)
            self.btn_browse2.style().polish(self.btn_browse2)
            self.lbl_path2.setText(path)

    # ── Logging ────────────────────────────────────────────────────
    @pyqtSlot(str)
    def log_message(self, message):
        logger.info(message)
        self.log_console.append(message)
        self.log_console.verticalScrollBar().setValue(
            self.log_console.verticalScrollBar().maximum()
        )

    @pyqtSlot(str)
    def handle_error(self, msg):
        logger.error(msg)
        self.log_console.append(
            f"<span style='color:#ff6b6b;font-weight:600;'>✗  {msg}</span>"
        )

    # ── Validation ─────────────────────────────────────────────────
    def validate_inputs(self):
        if not self.img1_path or not self.img2_path:
            QMessageBox.warning(self, "Missing Images", "Please select both target images before starting.")
            return False
        for label, path in [("Image 1", self.img1_path), ("Image 2", self.img2_path)]:
            if not os.path.exists(path):
                QMessageBox.critical(self, "File Not Found", f"{label} not found:\n{path}")
                return False
        return True

    # ── Start / Stop ───────────────────────────────────────────────
    def start_automation(self):
        if not self.validate_inputs():
            return
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.log_console.clear()
        self._set_status("Running", SUCCESS_FG)

        conf_pct = self.spin_conf.value() / 100.0

        config = {
            'img1_path':      self.img1_path,
            'img1_action':    self.cmb_action1.currentText(),
            'img1_offset_x':  self.spin_x1.value(),
            'img1_offset_y':  self.spin_y1.value(),
            'img2_path':      self.img2_path,
            'img2_action':    self.cmb_action2.currentText(),
            'img2_offset_x':  self.spin_x2.value(),
            'img2_offset_y':  self.spin_y2.value(),
            'initial_delay':  self.spin_initial_delay.value(),
            'click_delay':    self.spin_click_delay.value(),
            'cycle_delay':    self.spin_cycle_delay.value(),
            'max_cycles':     self.spin_max_cycles.value(),
            'search_timeout': self.spin_timeout.value(),
            'confidence':     conf_pct,
            'humanize':       self.chk_humanize.isChecked(),
        }

        self.worker = AutomationWorker(config)
        self.worker.log_signal.connect(self.log_message)
        self.worker.error_signal.connect(self.handle_error)
        self.worker.finished_signal.connect(self.on_automation_finished)
        self.worker.start()

    def stop_automation(self):
        if self.worker:
            self.log_message("Stop requested…")
            self.worker.stop()
        self._set_status("Stopping", WARNING)

    @pyqtSlot()
    def on_automation_finished(self):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._set_status("Idle", TEXT_MUTED)

    def _set_status(self, text, color):
        self.status_badge.setText(text)
        self.status_badge.setStyleSheet(
            f"color: {color}; font-size: 11px; font-weight: 500; "
            f"background: {PANEL_BG}; "
            f"border: 1px solid {color}; border-radius: 6px; padding: 3px 10px;"
        )

    # ── Cleanup ────────────────────────────────────────────────────
    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        event.accept()


# ==========================================
# 6. Entry point
# ==========================================
if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
