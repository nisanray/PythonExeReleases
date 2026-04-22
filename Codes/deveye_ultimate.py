import sys
import json
import os
import csv
import random
import shutil
from datetime import datetime, date, timedelta
try:
    import winsound
except ImportError:
    winsound = None

if sys.platform == "win32":
    import winreg
else:
    winreg = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QSystemTrayIcon, QMenu, 
    QMainWindow, QFrame, QDialog, QSpinBox, QListWidget,
    QCheckBox, QFormLayout, QGraphicsOpacityEffect, QGraphicsDropShadowEffect,
    QTabWidget, QComboBox, QProgressBar, QSlider, QFontComboBox,
    QFileDialog, QMessageBox, QGroupBox, QListWidgetItem
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRectF, QPoint, QUrl, QEvent
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QPen, QBrush, QShortcut, QKeySequence, QCursor
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer

APP_NAME = "DevEye Ultimate"
DATA_FILE_NAME = "deveye_data.json"


def get_data_file_path():
    appdata_dir = os.getenv("APPDATA")
    if not appdata_dir:
        appdata_dir = os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
    data_dir = os.path.join(appdata_dir, APP_NAME)
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, DATA_FILE_NAME)


DATA_FILE = get_data_file_path()


def get_legacy_data_candidates():
    candidates = []
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(base_dir, DATA_FILE_NAME))

    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates.append(os.path.join(exe_dir, DATA_FILE_NAME))

    candidates.append(os.path.join(os.getcwd(), DATA_FILE_NAME))

    seen = set()
    unique_candidates = []
    for path in candidates:
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized not in seen:
            seen.add(normalized)
            unique_candidates.append(path)
    return unique_candidates
###

# ================== HEALTH TIPS & AFFIRMATIONS ==================
HEALTH_TIPS = [
    "Focus on an object 20 feet away to relax your ciliary muscles.",
    "Blink rapidly for a few seconds to moisten your eyes.",
    "Roll your eyes gently in a circle to stretch the eye muscles.",
    "Close your eyes tightly for 3 seconds, then relax completely.",
    "Palming: Rub your hands together and gently cup them over your closed eyes.",
    "Look out a window at the furthest point you can see.",
    "Gently massage your temples in small circles.",
    "Splash cold water on your closed eyelids if you can."
]

AFFIRMATIONS = [
    "You're doing great. One break at a time.",
    "Protecting your eyes today = clearer vision tomorrow.",
    "Rest is part of the process. You've earned this.",
    "Your eyes work hard. Show them some love.",
    "Progress, not perfection. Keep going."
]

# ================== PRESETS & THEMES ==================
POMODORO_PRESETS = {
    "Custom": {"work_mins": 25, "break_secs": 300, "long_break_mins": 15, "long_break_interval": 4},
    "Classic 20-20-20": {"work_mins": 20, "break_secs": 20, "long_break_mins": 0, "long_break_interval": 0},
    "Pomodoro (25/5/15)": {"work_mins": 25, "break_secs": 300, "long_break_mins": 15, "long_break_interval": 4},
    "Deep Work (90/15)": {"work_mins": 90, "break_secs": 900, "long_break_mins": 30, "long_break_interval": 2},
}

BG_COLOR = "#F5F5F7"
SURFACE_COLOR = "#FFFFFF"
TEXT_PRIMARY = "#1D1D1F"
TEXT_MUTED = "#6E6E73"
DANGER_COLOR = "#FF3B30"
WARNING_COLOR = "#FF9500"
SUCCESS_COLOR = "#34C759"

THEMES = {
    "Emerald (Default)": {"accent": "#10B981", "hover": "#059669"},
    "Ocean Blue": {"accent": "#0EA5E9", "hover": "#0284C7"},
    "Amethyst Purple": {"accent": "#8B5CF6", "hover": "#7C3AED"},
    "Rose Pink": {"accent": "#F43F5E", "hover": "#E11D48"},
    "Amber Gold": {"accent": "#F59E0B", "hover": "#D97706"},
    "Neon Cyan": {"accent": "#06B6D4", "hover": "#0891B2"},
}

MINI_PLAYER_BG_PRESETS = {
    "Theme Surface": "#FFFFFF",
    "Theme Accent": "accent",
    "Midnight": "#111827",
    "Slate": "#E5E5EA",
    "Charcoal": "#D1D1D6",
    "Graphite": "#F0F0F2",
}


def resolve_mini_bg_color(choice, accent_color):
    color_value = MINI_PLAYER_BG_PRESETS.get(choice, SURFACE_COLOR)
    if color_value == "accent":
        return accent_color
    return color_value


def resolve_mini_text_color(choice):
    return "#FFFFFF" if choice in ("Theme Accent", "Midnight") else TEXT_PRIMARY


def get_stylesheet(accent_color, accent_hover, font_family="Segoe UI", font_size=13,
                   mini_bg_choice="Theme Surface"):
    try:
        font_size = int(font_size)
    except (TypeError, ValueError):
        font_size = 13
    if font_size < 8:
        font_size = 13

    mini_bg_color = resolve_mini_bg_color(mini_bg_choice, accent_color)
    return f"""
    QWidget {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 {BG_COLOR}); color: {TEXT_PRIMARY}; font-family: 'SF Pro Display', 'SF Pro Text', '{font_family}', 'Segoe UI', sans-serif; font-size: {font_size}px; }}
    
    QFrame#StatCard {{ background-color: rgba(255, 255, 255, 0.92); border-radius: 22px; border: 1px solid rgba(0, 0, 0, 0.06); }}
    QLabel#CardTitle {{ color: {TEXT_MUTED}; font-size: 10px; font-weight: 700; letter-spacing: 1.2px; }}
    QLabel#CardValue {{ color: {TEXT_PRIMARY}; font-size: 24px; font-weight: 600; }}
    
    QLabel#TimerLabel {{ font-size: 60px; font-weight: 700; color: {TEXT_PRIMARY}; letter-spacing: -1px; }}
    QLabel#Subtitle {{ color: {TEXT_MUTED}; font-size: 13px; font-weight: 500; }}
    QLabel#StreakBadge {{ background-color: rgba(255, 149, 0, 0.12); color: {WARNING_COLOR}; font-weight: 700; font-size: 12px; border-radius: 999px; padding: 4px 10px; }}
    
    QLineEdit {{ background-color: rgba(255, 255, 255, 0.96); border: 1px solid rgba(0, 0, 0, 0.08); border-radius: 14px; padding: 8px 12px; color: {TEXT_PRIMARY}; }}
    QLineEdit:focus {{ border: 1px solid {accent_color}; }}
    
    QListWidget {{ background-color: rgba(255, 255, 255, 0.96); border: 1px solid rgba(0, 0, 0, 0.08); border-radius: 18px; padding: 6px; outline: none; }}
    QListWidget::item {{ padding: 10px 8px; border-radius: 10px; }}
    QListWidget::item:selected {{ background-color: rgba(0, 113, 227, 0.10); border-radius: 10px; color: {TEXT_PRIMARY}; }}

    QPushButton {{ background-color: rgba(255, 255, 255, 0.96); border: 1px solid rgba(0, 0, 0, 0.08); border-radius: 16px; padding: 10px 16px; color: {TEXT_PRIMARY}; font-weight: 600; min-height: 40px; }}
    QPushButton:hover {{ background-color: rgba(255, 255, 255, 1.0); border: 1px solid rgba(0, 0, 0, 0.12); }}
    QPushButton:disabled {{ background-color: rgba(255, 255, 255, 0.6); color: #B0B0B5; border: 1px solid rgba(0, 0, 0, 0.06); }}
    
    QPushButton#PrimaryButton {{ background-color: {accent_color}; border: none; color: #ffffff; }}
    QPushButton#PrimaryButton:hover {{ background-color: {accent_hover}; }}
    QPushButton#DangerButton {{ background-color: transparent; border: 1px solid rgba(255, 59, 48, 0.35); color: {DANGER_COLOR}; }}
    QPushButton#DangerButton:hover {{ background-color: rgba(255, 59, 48, 0.08); }}
    
    QPushButton#MiniBtn {{ border-radius: 999px; padding: 0 8px; min-width: 44px; min-height: 28px; background-color: transparent; border: 1px solid transparent; font-size: 11px; color: {resolve_mini_text_color(mini_bg_choice)}; }}
    QPushButton#MiniBtn:hover {{ background-color: rgba(255, 255, 255, 0.12); color: {resolve_mini_text_color(mini_bg_choice)}; border: 1px solid rgba(255, 255, 255, 0.18); }}
    QFrame#MiniPlayerFrame {{ background-color: {mini_bg_color}; border-radius: 20px; border: 1px solid rgba(0, 0, 0, 0.08); }}
    QLabel#MiniTimeLabel {{ background-color: transparent; border: none; padding: 0; margin: 0; color: {resolve_mini_text_color(mini_bg_choice)}; font-size: 15px; font-weight: 700; }}
    QLabel#MiniPhaseDot {{ background-color: transparent; border: none; padding: 0; margin: 0; font-size: 10px; color: #10B981; }}
    
    QTabWidget::pane {{ border: 1px solid rgba(0, 0, 0, 0.08); border-radius: 18px; background-color: rgba(255, 255, 255, 0.90); top: -1px; }}
    QTabBar::tab {{ background: {BG_COLOR}; color: {TEXT_MUTED}; padding: 8px 16px; border: 1px solid transparent; border-top-left-radius: 14px; border-top-right-radius: 14px; font-weight: 600; }}
    QTabBar::tab:selected {{ color: {accent_color}; border: 1px solid rgba(0, 0, 0, 0.08); border-bottom-color: rgba(255, 255, 255, 0.90); background: rgba(255, 255, 255, 0.90); }}
    
    QSpinBox, QComboBox {{ background-color: rgba(255, 255, 255, 0.98); border: 1px solid rgba(0, 0, 0, 0.10); border-radius: 12px; padding: 8px 12px; color: {TEXT_PRIMARY}; min-height: 38px; }}
    QSpinBox::up-button, QSpinBox::down-button {{ width: 0px; }}
    
    QCheckBox {{ color: {TEXT_PRIMARY}; spacing: 12px; font-size: 12px; }}
    QCheckBox::indicator {{ width: 34px; height: 18px; border-radius: 9px; border: 2px solid rgba(0, 0, 0, 0.16); background-color: #FFFFFF; }}
    QCheckBox::indicator:checked {{ background-color: {accent_color}; border: 2px solid {accent_color}; }}
    
    QGroupBox {{ border: 1px solid rgba(0, 0, 0, 0.08); border-radius: 18px; margin-top: 12px; padding-top: 15px; color: {TEXT_MUTED}; font-size: 11px; font-weight: 700; letter-spacing: 1px; background-color: rgba(255, 255, 255, 0.92); }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}

    QProgressBar#GoalBar {{ background-color: rgba(0, 0, 0, 0.06); border: none; border-radius: 999px; text-align: center; color: transparent; height: 8px; }}
    QProgressBar#GoalBar::chunk {{ background-color: {accent_color}; border-radius: 999px; }}
    """

def get_overlay_style(opacity_pct):
    alpha = int((opacity_pct / 100.0) * 255)
    return f"""
    QWidget {{ background-color: rgba(10, 10, 12, {alpha}); color: #FFFFFF; }}
    QFrame#OverlayPanel {{ background-color: rgba(0, 0, 0, 0.98); border: none; border-radius: 30px; }}
    QFrame#OverlayPanel QLabel {{ color: #FFFFFF; background-color: transparent; }}
    QLabel#OverlayTitle {{ font-size: 42px; font-weight: 700; letter-spacing: -0.8px; }}
    QLabel#OverlaySub {{ font-size: 20px; font-weight: 400; }}
    QLabel#OverlayAffirm {{ font-size: 16px; font-weight: 500; }}
    QLabel#OverlaySession {{ font-size: 13px; }}
    """


# ================== DATA MANAGER ==================
class DataManager:
    DATA_VERSION = 1  # Increment when data format changes

    @staticmethod
    def migrate_legacy_file_if_needed():
        if os.path.exists(DATA_FILE):
            return

        for legacy_file in get_legacy_data_candidates():
            if not os.path.exists(legacy_file):
                continue
            try:
                os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
                shutil.copy2(legacy_file, DATA_FILE)
                return
            except OSError:
                continue

    @staticmethod
    def get_defaults():
        return {
            "version": DataManager.DATA_VERSION,
            "stats": {
                "completed": 0, "missed": 0, "skipped": 0, "partial": 0,
                "streak": 0, "last_date": "", "total_focus_mins": 0
            },
            "history": [],
            "settings": {
                "preset": "Classic 20-20-20",
                "work_mins": 20, "break_secs": 20, 
                "long_break_mins": 0, "long_break_interval": 0,
                "current_session_count": 0,
                "strict_mode": False, "theme": "Emerald (Default)",
                "daily_goal_hrs": 4, "sound_fx": True, "auto_resume": False,
                "mini_opacity": 90, "overlay_opacity": 95,
                "mini_bg_color": "Theme Surface",
                "compact_mode": False, 
                "font_family": "Segoe UI", "font_size": 13,
                "custom_break_msg": "", "show_affirmations": True, "show_eye_tips": True,
                "startup_minimized": False, "idle_detection": False, "idle_threshold_mins": 5,
                "show_session_label": True,
                "after_break_flow": "Auto Restart",
                "sound_mode": "System Beep",
                "custom_sound_file": "",
                "mini_player_x": None,
                "mini_player_y": None,
                "text_to_speech": False,
                "run_on_startup": False
            }

        }

    @staticmethod
    def load():
        default_data = DataManager.get_defaults()
        DataManager.migrate_legacy_file_if_needed()
        if not os.path.exists(DATA_FILE): return default_data
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                for key, val in default_data.items():
                    if key not in data: 
                        data[key] = val
                    elif isinstance(val, dict):
                        for subkey, subval in val.items():
                            if subkey not in data[key]: data[key][subkey] = subval

                # Normalize legacy/corrupt shapes from older versions.
                if not isinstance(data.get("history"), list):
                    data["history"] = []
                if not isinstance(data.get("stats"), dict):
                    data["stats"] = dict(default_data["stats"])
                if not isinstance(data.get("settings"), dict):
                    data["settings"] = dict(default_data["settings"])

                try:
                    fs = int(data["settings"].get("font_size", 13))
                except (TypeError, ValueError):
                    fs = 13
                data["settings"]["font_size"] = fs if fs >= 8 else 13

                return data
        except (json.JSONDecodeError, IOError) as e:
            # Backup corrupt file before resetting to prevent data loss
            backup_path = f"{DATA_FILE}.corrupt.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
            try:
                os.rename(DATA_FILE, backup_path)
                print(f"Data file was corrupt. Backed up to: {backup_path}")
            except Exception:
                pass  # If backup fails, still return defaults
            return default_data

    @staticmethod
    def save(data):
        try:
            os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
            with open(DATA_FILE, "w") as f:
                json.dump(data, f, indent=4)
            return True
        except OSError as e:
            print(f"Failed to save data: {e}")
            return False

    @staticmethod
    def log_session(data, session_type, duration_mins, label=""):
        entry = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "type": session_type,
            "duration": duration_mins,
            "tag": label or "Deep Focus"
        }
        if "history" not in data or not isinstance(data.get("history"), list):
            data["history"] = []
        data["history"].insert(0, entry)
        data["history"] = data["history"][:200]

    @staticmethod
    def export_csv(data, path):
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Type", "Duration (minutes)", "Tag"])
            for entry in data.get("history", []):
                writer.writerow([
                    entry.get("date", ""), entry.get("type", ""),
                    entry.get("duration", ""), entry.get("tag", "")
                ])


# ================== CUSTOM UI WIDGETS ==================
class CircularProgress(QWidget):
    def __init__(self, accent_color, parent=None):
        super().__init__(parent)
        self.setFixedSize(200, 200)
        self.max_value = 100
        self.current_value = 100
        self.text = ""
        self.accent_color = accent_color
        self.text_color = TEXT_PRIMARY

    def set_values(self, current, maximum, text):
        self.current_value = current
        self.max_value = maximum
        self.text = str(text)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(10, 10, self.width() - 20, self.height() - 20)
        
        pen_bg = QPen(QColor(SURFACE_COLOR))
        pen_bg.setWidth(12)
        pen_bg.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_bg)
        painter.drawArc(rect, 0, 360 * 16)

        if self.max_value > 0:
            progress_ratio = self.current_value / self.max_value
            span_angle = int(progress_ratio * -360 * 16)
            pen_fg = QPen(QColor(self.accent_color))
            pen_fg.setWidth(12)
            pen_fg.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen_fg)
            painter.drawArc(rect, 90 * 16, span_angle)

        painter.setPen(QPen(QColor(self.text_color)))
        font = painter.font()
        font.setPixelSize(42)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text)
        painter.end()


class StatCard(QFrame):
    def __init__(self, title, initial_value, color):
        super().__init__()
        self.setObjectName("StatCard")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 12)
        
        self.title_label = QLabel(title.upper())
        self.title_label.setObjectName("CardTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.value_label = QLabel(str(initial_value))
        self.value_label.setObjectName("CardValue")
        self.value_label.setStyleSheet(f"color: {color};")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value):
        self.value_label.setText(str(value))


class SessionLabelDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Focus Tag")
        self.setFixedSize(340, 140)
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Tag this focus session (optional):"))
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("e.g. Code Review, Studying...")
        self.edit.returnPressed.connect(self.accept)
        layout.addWidget(self.edit)

        btns = QHBoxLayout()
        skip_btn = QPushButton("Skip")
        skip_btn.clicked.connect(self.accept)
        ok_btn = QPushButton("Start")
        ok_btn.setObjectName("PrimaryButton")
        ok_btn.clicked.connect(self.accept)
        
        btns.addWidget(skip_btn)
        btns.addStretch()
        btns.addWidget(ok_btn)
        layout.addLayout(btns)

    def get_label(self):
        return self.edit.text().strip()


class FocusGraphWidget(QWidget):
    def __init__(self, data, accent_color, parent=None):
        super().__init__(parent)
        self.data = data
        self.accent_color = accent_color
        self.setMinimumHeight(150)

    def get_series(self):
        totals = {}
        today = date.today()
        for offset in range(6, -1, -1):
            day_key = (today - timedelta(days=offset)).isoformat()
            totals[day_key] = 0.0

        for entry in self.data.get("history", []):
            try:
                entry_date = datetime.strptime(entry.get("date", ""), "%Y-%m-%d %H:%M").date().isoformat()
            except ValueError:
                continue

            if entry_date not in totals:
                continue

            entry_type = entry.get("type", "")
            if entry_type in ("completed", "partial"):
                try:
                    totals[entry_date] += float(entry.get("duration", 0))
                except (TypeError, ValueError):
                    continue

        return list(totals.items())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(8, 24, -8, -22)

        series = self.get_series()
        if not series:
            painter.setPen(QColor(TEXT_MUTED))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No history yet")
            painter.end()
            return

        max_value = max((value for _, value in series), default=0)
        max_value = max(max_value, 1)

        bar_count = len(series)
        gap = 8
        bar_width = max(14, int((rect.width() - gap * (bar_count - 1)) / bar_count))
        total_width = bar_width * bar_count + gap * (bar_count - 1)
        start_x = rect.left() + max(0, (rect.width() - total_width) // 2)
        baseline = rect.bottom() - 18
        chart_height = rect.height() - 30

        painter.setPen(QPen(QColor(0, 0, 0, 20), 1))
        painter.drawLine(rect.left(), baseline, rect.right(), baseline)

        bar_color = QColor(self.accent_color)
        label_color = QColor(TEXT_MUTED)

        x = start_x
        for day_key, value in series:
            bar_height = int((value / max_value) * chart_height)
            bar_rect = QRectF(x, baseline - bar_height, bar_width, bar_height)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(bar_color.red(), bar_color.green(), bar_color.blue(), 220))
            painter.drawRoundedRect(bar_rect, 6, 6)

            painter.setPen(label_color)
            day_label = datetime.strptime(day_key, "%Y-%m-%d").strftime("%a")
            painter.drawText(QRectF(x - 4, baseline + 2, bar_width + 8, 12), Qt.AlignmentFlag.AlignCenter, day_label)

            if value > 0:
                painter.drawText(QRectF(x - 12, baseline - bar_height - 16, bar_width + 24, 12), Qt.AlignmentFlag.AlignCenter, f"{value:.0f}m")

            x += bar_width + gap

        painter.end()


class HistoryDialog(QDialog):
    def __init__(self, data, theme_style, accent_color, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Data & History")
        self.setFixedSize(470, 560)
        self.setStyleSheet(theme_style)
        self.data = data
        layout = QVBoxLayout(self)

        self.graph = FocusGraphWidget(self.data, accent_color)
        layout.addWidget(self.graph)
        
        self.list_widget = QListWidget()
        self.populate_list()
        layout.addWidget(self.list_widget)
        
        # Management buttons layout
        mgt_layout = QHBoxLayout()
        btn_json_export = QPushButton("Export JSON")
        btn_json_export.clicked.connect(self.export_json)
        btn_csv_export = QPushButton("Export CSV")
        btn_csv_export.clicked.connect(self.export_csv)
        btn_json_import = QPushButton("Import JSON")
        btn_json_import.clicked.connect(self.import_json)
        
        mgt_layout.addWidget(btn_json_export)
        mgt_layout.addWidget(btn_csv_export)
        mgt_layout.addWidget(btn_json_import)
        
        # Bottom Actions
        act_layout = QHBoxLayout()
        btn_clear = QPushButton("Reset Stats")
        btn_clear.setObjectName("DangerButton")
        btn_clear.clicked.connect(self.clear_history)
        btn_close = QPushButton("Close")
        btn_close.setObjectName("PrimaryButton")
        btn_close.clicked.connect(self.accept)
        
        act_layout.addWidget(btn_clear)
        act_layout.addStretch()
        act_layout.addWidget(btn_close)
        
        layout.addLayout(mgt_layout)
        layout.addSpacing(10)
        layout.addLayout(act_layout)

    def populate_list(self):
        self.list_widget.clear()
        history = self.data.get("history", [])
        if not history:
            self.list_widget.addItem("No sessions recorded yet. Time to focus!")
        else:
            for entry in history:
                icon = {"completed": "✅", "missed": "⏰", "skipped": "⏭", "partial": "🧩"}.get(entry.get("type", ""), "•")
                self.list_widget.addItem(f"{icon} {entry.get('date', '')} | {entry.get('duration', '?')}m | {entry.get('tag', 'Untagged')}")

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "deveye_history.csv", "CSV files (*.csv)")
        if path:
            DataManager.export_csv(self.data, path)
            QMessageBox.information(self, "Success", "History exported to CSV.")

    def export_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Backup", "deveye_backup.json", "JSON Files (*.json)")
        if path:
            with open(path, "w") as f: json.dump(self.data, f, indent=4)
            QMessageBox.information(self, "Success", "Data backup exported.")

    def import_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Backup", "", "JSON Files (*.json)")
        if path:
            try:
                with open(path, "r") as f: new_data = json.load(f)
                self.data.update(new_data)
                DataManager.save(self.data)
                self.populate_list()
                QMessageBox.information(self, "Success", "Backup imported successfully. Please restart the app for full effect.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import: {e}")

    def clear_history(self):
        reply = QMessageBox.question(self, 'Confirm Reset', 'Clear all history and reset stats?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.data["stats"] = {"completed": 0, "missed": 0, "skipped": 0, "partial": 0, "streak": 0, "last_date": "", "total_focus_mins": 0}
            self.data["settings"]["current_session_count"] = 0
            self.data["history"] = []
            DataManager.save(self.data)
            self.populate_list()
            
            if self.parent():
                self.parent().update_stats()


class MiniPlayer(QWidget):
    def __init__(self, parent_app):
        super().__init__()
        self.app = parent_app
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(235, 58)
        self.old_pos = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        
        self.bg_frame = QFrame()
        self.bg_frame.setObjectName("MiniPlayerFrame")
        bg_layout = QHBoxLayout(self.bg_frame)
        bg_layout.setContentsMargins(12, 4, 12, 4)
        bg_layout.setSpacing(8)
        
        self.phase_dot = QLabel("●")
        self.phase_dot.setObjectName("MiniPhaseDot")

        self.time_label = QLabel("00:00")
        self.time_label.setObjectName("MiniTimeLabel")
        
        self.btn_pause = QPushButton("Pause")
        self.btn_pause.setObjectName("MiniBtn")
        self.btn_pause.setFixedSize(56, 28)
        self.btn_pause.clicked.connect(self.app.toggle_pause)

        self.btn_expand = QPushButton("Open")
        self.btn_expand.setObjectName("MiniBtn")
        self.btn_expand.setFixedSize(50, 28)
        self.btn_expand.clicked.connect(self.restore_main)

        bg_layout.addWidget(self.phase_dot)
        bg_layout.addWidget(self.time_label)
        bg_layout.addStretch()
        bg_layout.addWidget(self.btn_pause)
        bg_layout.addWidget(self.btn_expand)
        
        layout.addWidget(self.bg_frame)

    def restore_main(self):
        self.hide()
        self.app.show_normal()

    def update_time(self, text, paused, strict_mode=False, phase="focus"):
        self.time_label.setText(text)
        self.btn_pause.setText("Resume" if paused else "Pause")
        text_color = resolve_mini_text_color(self.app.data["settings"].get("mini_bg_color", "Theme Surface"))
        muted_color = "rgba(255, 255, 255, 0.72)" if text_color == "#FFFFFF" else TEXT_MUTED
        self.time_label.setStyleSheet(f"background-color: transparent; border: none; padding: 0; margin: 0; font-size: 16px; font-weight: bold; color: {muted_color if paused else text_color};")
        self.phase_dot.setStyleSheet(f"background-color: transparent; border: none; padding: 0; margin: 0; font-size: 10px; color: {'#F59E0B' if phase == 'break' else '#34C759'};")
        self.btn_pause.setStyleSheet(f"color: {text_color}; background-color: transparent; border: 1px solid transparent;")
        self.btn_expand.setStyleSheet(f"color: {text_color}; background-color: transparent; border: 1px solid transparent;")
        
        if strict_mode and not paused and phase == "focus":
            self.btn_pause.setDisabled(True)
        else:
            self.btn_pause.setDisabled(False)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos is not None:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None
        # Save position for persistence
        pos = self.pos()
        self.app.data["settings"]["mini_player_x"] = pos.x()
        self.app.data["settings"]["mini_player_y"] = pos.y()
        DataManager.save(self.app.data)


class SettingsDialog(QDialog):
    def __init__(self, app_instance, parent=None):
        super().__init__(parent)
        self.app = app_instance
        self.settings = self.app.data["settings"]
        self.setWindowTitle("Preferences")
        self.setFixedSize(480, 560)
        
        colors = self.app.get_theme_colors()
        self.setStyleSheet(get_stylesheet(
            colors["accent"], colors["hover"],
            self.settings.get("font_family", "Segoe UI"),
            self.settings.get("font_size", 13),
            self.settings.get("mini_bg_color", "Theme Surface")
        ))

        main_layout = QVBoxLayout(self)
        tabs = QTabWidget()
        
        # --- TAB 1: General (Timer) ---
        tab_core = QWidget()
        core_layout = QVBoxLayout(tab_core)
        core_layout.setSpacing(10)
        core_layout.setContentsMargins(15, 15, 15, 15)

        preset_grp = QGroupBox("QUICK PRESETS")
        pl = QVBoxLayout(preset_grp)
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(list(POMODORO_PRESETS.keys()))
        self.preset_combo.setCurrentText(self.settings.get("preset", "Classic 20-20-20"))
        self.preset_combo.currentTextChanged.connect(self.apply_preset)
        pl.addWidget(self.preset_combo)

        manual_grp = QGroupBox("MANUAL TIMINGS")
        form = QFormLayout(manual_grp)
        
        self.work_spin = QSpinBox()
        self.work_spin.setRange(1, 240)
        self.work_spin.setValue(self.settings.get("work_mins", 25))
        self.work_spin.setSuffix(" min")
        
        self.break_spin = QSpinBox()
        self.break_spin.setRange(5, 1800)
        self.break_spin.setValue(self.settings.get("break_secs", 300))
        self.break_spin.setSuffix(" sec")

        self.long_break_spin = QSpinBox()
        self.long_break_spin.setRange(0, 60)
        self.long_break_spin.setValue(self.settings.get("long_break_mins", 0))
        self.long_break_spin.setSuffix(" min (0=Off)")

        self.long_break_interval = QSpinBox()
        self.long_break_interval.setRange(0, 10)
        self.long_break_interval.setValue(self.settings.get("long_break_interval", 4))
        self.long_break_interval.setSuffix(" sessions")

        self.goal_spin = QSpinBox()
        self.goal_spin.setRange(1, 16)
        self.goal_spin.setValue(self.settings.get("daily_goal_hrs", 4))
        self.goal_spin.setSuffix(" hrs")
        
        form.addRow("Focus Session:", self.work_spin)
        form.addRow("Short Break:", self.break_spin)
        form.addRow("Long Break:", self.long_break_spin)
        form.addRow("Long Break After:", self.long_break_interval)
        form.addRow("Daily Focus Goal:", self.goal_spin)

        core_layout.addWidget(preset_grp)
        core_layout.addWidget(manual_grp)
        core_layout.addStretch()
        
        # --- TAB 2: Behavior ---
        tab_behavior = QWidget()
        behavior_layout = QVBoxLayout(tab_behavior)
        behavior_layout.setSpacing(10)
        behavior_layout.setContentsMargins(15, 15, 15, 15)

        beh_grp = QGroupBox("SESSION BEHAVIOR")
        bl = QVBoxLayout(beh_grp)
        self.strict_check = QCheckBox("Strict Mode (Disable Skip & Manual Pause)")
        self.strict_check.setChecked(self.settings.get("strict_mode", False))
        
        self.sound_check = QCheckBox("Enable Sound FX")
        self.sound_check.setChecked(self.settings.get("sound_fx", True))

        self.resume_check = QCheckBox("Auto-resume focus after break")
        self.resume_check.setChecked(self.settings.get("auto_resume", False))

        self.startup_check = QCheckBox("Start Minimized to Tray")
        self.startup_check.setChecked(self.settings.get("startup_minimized", False))

        self.session_label_check = QCheckBox("Show Focus Tag Prompt")
        self.session_label_check.setChecked(self.settings.get("show_session_label", True))

        self.startup_run_check = QCheckBox("Run on System Startup")
        self.startup_run_check.setChecked(self.settings.get("run_on_startup", False))

        self.after_break_combo = QComboBox()

        self.after_break_combo.addItems(["Auto Restart", "Ask Every Time"])
        self.after_break_combo.setCurrentText(self.settings.get("after_break_flow", "Auto Restart"))

        bl.addWidget(self.strict_check)
        bl.addWidget(self.sound_check)
        bl.addWidget(self.resume_check)
        bl.addWidget(self.startup_check)
        bl.addWidget(self.session_label_check)
        bl.addWidget(self.startup_run_check)
        bl.addWidget(QLabel("After Break:"))

        bl.addWidget(self.after_break_combo)

        idle_grp = QGroupBox("IDLE DETECTION")
        il = QVBoxLayout(idle_grp)
        self.idle_check = QCheckBox("Pause timer when away from PC")
        self.idle_check.setChecked(self.settings.get("idle_detection", False))
        idle_row = QHBoxLayout()
        idle_row.addWidget(QLabel("Idle Threshold:"))
        self.idle_spin = QSpinBox()
        self.idle_spin.setRange(1, 60)
        self.idle_spin.setValue(self.settings.get("idle_threshold_mins", 5))
        self.idle_spin.setSuffix(" min")
        idle_row.addWidget(self.idle_spin)
        idle_row.addStretch()
        il.addWidget(self.idle_check)
        il.addLayout(idle_row)

        behavior_layout.addWidget(beh_grp)
        behavior_layout.addWidget(idle_grp)
        behavior_layout.addStretch()

        # --- TAB 3: Appearance ---
        tab_app = QWidget()
        app_layout = QVBoxLayout(tab_app)
        app_layout.setSpacing(10)
        app_layout.setContentsMargins(15, 15, 15, 15)

        ui_grp = QGroupBox("USER INTERFACE")
        ul = QFormLayout(ui_grp)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(THEMES.keys()))
        self.theme_combo.setCurrentText(self.settings.get("theme", "Emerald (Default)"))

        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentText(self.settings.get("font_family", "Segoe UI"))

        self.font_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_slider.setRange(11, 18)
        self.font_slider.setValue(self.settings.get("font_size", 13))
        self.font_label = QLabel(f"{self.font_slider.value()}px")
        self.font_slider.valueChanged.connect(lambda v: self.font_label.setText(f"{v}px"))
        
        font_layout = QHBoxLayout()
        font_layout.addWidget(self.font_slider)
        font_layout.addWidget(self.font_label)

        self.compact_check = QCheckBox("Compact Dashboard (Hide Stats)")
        self.compact_check.setChecked(self.settings.get("compact_mode", False))

        self.mini_bg_combo = QComboBox()
        self.mini_bg_combo.addItems(list(MINI_PLAYER_BG_PRESETS.keys()))
        self.mini_bg_combo.setCurrentText(self.settings.get("mini_bg_color", "Theme Surface"))

        ul.addRow("UI Theme:", self.theme_combo)
        ul.addRow("Font Family:", self.font_combo)
        ul.addRow("Font Size:", font_layout)
        ul.addRow("Mini BG Color:", self.mini_bg_combo)
        ul.addRow("", self.compact_check)

        op_grp = QGroupBox("OPACITY")
        opl = QFormLayout(op_grp)
        self.mini_slider = QSlider(Qt.Orientation.Horizontal)
        self.mini_slider.setRange(20, 100)
        self.mini_slider.setValue(self.settings.get("mini_opacity", 90))

        self.overlay_slider = QSlider(Qt.Orientation.Horizontal)
        self.overlay_slider.setRange(40, 100)
        self.overlay_slider.setValue(self.settings.get("overlay_opacity", 95))
        opl.addRow("Mini Player:", self.mini_slider)
        opl.addRow("Break Overlay:", self.overlay_slider)

        app_layout.addWidget(ui_grp)
        app_layout.addWidget(op_grp)
        app_layout.addStretch()

        # --- TAB 4: Sound ---
        tab_sound = QWidget()
        sound_layout = QVBoxLayout(tab_sound)
        sound_layout.setSpacing(10)
        sound_layout.setContentsMargins(15, 15, 15, 15)

        sound_grp = QGroupBox("SOUND PLAYBACK")
        sl = QVBoxLayout(sound_grp)

        self.sound_mode_combo = QComboBox()
        self.sound_mode_combo.addItems(["System Beep", "Custom Audio File"])
        self.sound_mode_combo.setCurrentText(self.settings.get("sound_mode", "System Beep"))

        self.custom_sound_button = QPushButton("Choose Audio File")
        self.custom_sound_button.clicked.connect(self.choose_sound_file)
        self.custom_sound_button.setMinimumHeight(42)

        self.custom_sound_path = self.settings.get("custom_sound_file", "")
        self.custom_sound_label = QLabel(self.custom_sound_path or "No file selected")
        self.custom_sound_label.setWordWrap(True)
        self.custom_sound_label.setStyleSheet("color: #6E6E73; font-size: 11px;")
        self.custom_sound_label.setMinimumHeight(24)

        self.sound_hint = QLabel("MP3 and WAV files are supported. System Beep uses the OS default alert sound.")
        self.sound_hint.setWordWrap(True)
        self.sound_hint.setStyleSheet("color: #6E6E73; font-size: 11px;")

        sl.addWidget(QLabel("Sound Mode:"))
        sl.addWidget(self.sound_mode_combo)
        sl.addWidget(self.custom_sound_button)
        sl.addWidget(self.custom_sound_label)
        sl.addWidget(self.sound_hint)
        sound_layout.addWidget(sound_grp)
        sound_layout.addStretch()

        self.sound_mode_combo.currentTextChanged.connect(self.update_sound_controls)
        self.update_sound_controls(self.sound_mode_combo.currentText())

        # --- TAB 4: Overlay Settings ---
        tab_overlay = QWidget()
        overlay_layout = QVBoxLayout(tab_overlay)
        overlay_layout.setSpacing(10)
        overlay_layout.setContentsMargins(15, 15, 15, 15)

        over_grp = QGroupBox("BREAK SCREEN CONTENT")
        ov_l = QVBoxLayout(over_grp)
        self.tips_check = QCheckBox("Rotate Eye Health Tips")
        self.tips_check.setChecked(self.settings.get("show_eye_tips", True))
        self.affirm_check = QCheckBox("Show Motivational Affirmations")
        self.affirm_check.setChecked(self.settings.get("show_affirmations", True))
        self.tts_check = QCheckBox("Text-to-Speech (Offline)")
        self.tts_check.setChecked(self.settings.get("text_to_speech", False))
        self.tts_check.setToolTip("Read health tips and affirmations aloud using system voice")
        ov_l.addWidget(self.tips_check)
        ov_l.addWidget(self.affirm_check)
        ov_l.addWidget(self.tts_check)
        
        msg_grp = QGroupBox("CUSTOM MESSAGE")
        ml = QVBoxLayout(msg_grp)
        ml.addWidget(QLabel("Override the 'Rest Your Eyes' title:"))
        self.msg_input = QLineEdit(self.settings.get("custom_break_msg", ""))
        self.msg_input.setPlaceholderText("e.g. Stretch and hydrate! ")
        ml.addWidget(self.msg_input)

        overlay_layout.addWidget(over_grp)
        overlay_layout.addWidget(msg_grp)
        overlay_layout.addStretch()

        tabs.addTab(tab_core, "Timer")
        tabs.addTab(tab_behavior, "Behavior")
        tabs.addTab(tab_app, "Appearance")
        tabs.addTab(tab_overlay, "Overlay")
        tabs.addTab(tab_sound, "Sound")

        save_btn = QPushButton("Apply Changes")
        save_btn.setObjectName("PrimaryButton")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self.accept)

        main_layout.addWidget(tabs)
        main_layout.addWidget(save_btn)

    def apply_preset(self, preset_name):
        if preset_name == "Custom": return
        p = POMODORO_PRESETS.get(preset_name, {})
        self.work_spin.setValue(p.get("work_mins", 20))
        self.break_spin.setValue(p.get("break_secs", 20))
        self.long_break_spin.setValue(p.get("long_break_mins", 0))
        self.long_break_interval.setValue(p.get("long_break_interval", 0))

    def get_settings(self):
        return {
            "preset": self.preset_combo.currentText(),
            "work_mins": self.work_spin.value(),
            "break_secs": self.break_spin.value(),
            "long_break_mins": self.long_break_spin.value(),
            "long_break_interval": self.long_break_interval.value(),
            "daily_goal_hrs": self.goal_spin.value(),
            "theme": self.theme_combo.currentText(),
            "strict_mode": self.strict_check.isChecked(),
            "sound_fx": self.sound_check.isChecked(),
            "sound_mode": self.sound_mode_combo.currentText(),
            "custom_sound_file": self.custom_sound_path if self.sound_mode_combo.currentText() == "Custom Audio File" else "",
            "auto_resume": self.resume_check.isChecked(),
            "startup_minimized": self.startup_check.isChecked(),
            "show_session_label": self.session_label_check.isChecked(),
            "after_break_flow": self.after_break_combo.currentText(),
            "idle_detection": self.idle_check.isChecked(),
            "idle_threshold_mins": self.idle_spin.value(),
            "mini_opacity": self.mini_slider.value(),
            "overlay_opacity": self.overlay_slider.value(),
            "mini_bg_color": self.mini_bg_combo.currentText(),
            "compact_mode": self.compact_check.isChecked(),
            "font_family": self.font_combo.currentText(),
            "font_size": self.font_slider.value(),
            "show_eye_tips": self.tips_check.isChecked(),
            "show_affirmations": self.affirm_check.isChecked(),
            "custom_break_msg": self.msg_input.text(),
            "text_to_speech": self.tts_check.isChecked(),
            "run_on_startup": self.startup_run_check.isChecked()
        }


    def update_sound_controls(self, mode):
        is_custom = mode == "Custom Audio File"
        self.custom_sound_button.setEnabled(is_custom)
        self.custom_sound_label.setEnabled(is_custom)
        self.custom_sound_label.setText(self.custom_sound_path or "No file selected")

    def choose_sound_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose Audio File", "", "Audio Files (*.wav *.mp3);;WAV Files (*.wav);;MP3 Files (*.mp3)")
        if path:
            # Validate file exists and is readable
            if not os.path.exists(path):
                QMessageBox.warning(self, "Invalid File", "Selected file does not exist.")
                return
            # Validate file size (max 10MB to prevent issues)
            try:
                size = os.path.getsize(path)
                if size > 10 * 1024 * 1024:  # 10MB limit
                    QMessageBox.warning(self, "File Too Large", "Audio file must be smaller than 10MB.")
                    return
                if size == 0:
                    QMessageBox.warning(self, "Empty File", "Selected file is empty.")
                    return
            except OSError:
                QMessageBox.warning(self, "Invalid File", "Cannot read selected file.")
                return
            self.custom_sound_path = path
            self.custom_sound_label.setText(path)


# ================== OVERLAY SCREEN ==================
class BreakScreen(QWidget):
    def __init__(self, app_instance, accent_color, on_done, on_skip):
        super().__init__()
        self.app = app_instance
        self.settings = self.app.data["settings"]
        self.accent_color = accent_color
        self.on_done = on_done
        self.on_skip = on_skip
        
        self._tip_index = 0
        self._affirm_index = 0
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setStyleSheet(get_overlay_style(self.settings.get("overlay_opacity", 95)))
        
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.animation.setDuration(800)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_countdown)
        self.tip_timer = QTimer()
        self.tip_timer.timeout.connect(self.rotate_tip)
        self.audio_output = None
        self.media_player = None
        self.tts_engine = None

        self.setup_ui()

    def speak_text(self, text):
        if not self.settings.get("text_to_speech", False):
            return
        if pyttsx3 is None:
            return
        try:
            if self.tts_engine is None:
                self.tts_engine = pyttsx3.init()
                # Try to select a female voice
                voices = self.tts_engine.getProperty('voices')
                for voice in voices:
                    voice_name = voice.name.lower()
                    # Common female voice indicators
                    if any(keyword in voice_name for keyword in ['female', 'woman', 'girl', 'zira', 'samantha', 'victoria', 'karen', 'susan', 'heera', 'google us english']):
                        self.tts_engine.setProperty('voice', voice.id)
                        break
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
        except Exception:
            pass

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(0)

        self.panel = QFrame()
        self.panel.setObjectName("OverlayPanel")
        self.panel.setFixedWidth(860)
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(44, 36, 44, 36)
        panel_layout.setSpacing(18)

        self.title = QLabel("Rest Your Eyes")
        self.title.setObjectName("OverlayTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.sub = QLabel("")
        self.sub.setObjectName("OverlaySub")
        self.sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub.setWordWrap(True)
        
        self.affirm_label = QLabel("")
        self.affirm_label.setObjectName("OverlayAffirm")
        self.affirm_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.affirm_label.setWordWrap(True)

        self.progress_ring = CircularProgress(self.accent_color)
        self.progress_ring.setStyleSheet("background: transparent;")
        
        self.session_info = QLabel("")
        self.session_info.setObjectName("OverlaySession")
        self.session_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.session_info.setStyleSheet("background-color: transparent;")

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        
        self.done_btn = QPushButton(" I'm Done")
        self.done_btn.setFixedSize(160, 45)
        self.done_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.done_btn.clicked.connect(self.done)

        self.skip_btn = QPushButton("Skip Break")
        self.skip_btn.setFixedSize(140, 45)
        self.skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skip_btn.clicked.connect(self.skip)

        btn_layout.addWidget(self.done_btn)
        btn_layout.addWidget(self.skip_btn)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        panel_layout.addWidget(self.title)
        panel_layout.addWidget(self.sub)
        panel_layout.addWidget(self.affirm_label)
        panel_layout.addSpacing(20)
        panel_layout.addWidget(self.progress_ring, alignment=Qt.AlignmentFlag.AlignCenter)
        panel_layout.addWidget(self.session_info)
        panel_layout.addSpacing(18)
        panel_layout.addLayout(btn_layout)

        layout.addStretch()
        layout.addWidget(self.panel, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()

    def start(self, settings, theme_data, session_num=0, total_sessions=0, is_long_break=False):
        self.settings = settings
        self.accent_color = theme_data["accent"]
        self.setStyleSheet(get_overlay_style(self.settings.get("overlay_opacity", 95)))
        
        custom_msg = self.settings.get("custom_break_msg", "").strip()
        self.title.setText(custom_msg if custom_msg else ("LONG BREAK" if is_long_break else "Rest Your Eyes"))
        
        self.done_btn.setStyleSheet(f"background-color: {self.accent_color}; border: none; color: white; border-radius: 8px; font-weight: bold; font-size: 14px;")
        self.skip_btn.setStyleSheet(f"background-color: transparent; border: 1px solid {DANGER_COLOR}; color: {DANGER_COLOR}; border-radius: 8px; font-weight: bold; font-size: 14px;")
        self.progress_ring.accent_color = self.accent_color
        self.progress_ring.text_color = "#FFFFFF"

        self.total_time = (self.settings.get("long_break_mins", 0) * 60) if is_long_break else self.settings.get("break_secs", 20)
        self.time_left = self.total_time
        self.progress_ring.set_values(self.time_left, self.total_time, self.time_left)
        
        self.skip_btn.setVisible(not self.settings.get("strict_mode", False))

        if session_num > 0 and total_sessions > 0 and not is_long_break:
            self.session_info.setText(f"Session {session_num} of {total_sessions} before long break")
        else:
            self.session_info.setText("")

        if self.settings.get("show_affirmations", True):
            affirm_text = AFFIRMATIONS[self._affirm_index % len(AFFIRMATIONS)]
            self.affirm_label.setText(affirm_text)
            self._affirm_index += 1
            self.speak_text(affirm_text)
        else:
            self.affirm_label.setText("")

        if self.settings.get("show_eye_tips", True):
            tip_text = HEALTH_TIPS[self._tip_index % len(HEALTH_TIPS)]
            self.sub.setText(" " + tip_text)
            self._tip_index += 1
            self.tip_timer.start(7000)
            self.speak_text(tip_text)
        else:
            self.sub.setText("Close your eyes and relax.")
            self.tip_timer.stop()

        self.play_sound()

        self.showFullScreen()
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.start()
        self.timer.start(1000)

    def rotate_tip(self):
        self._tip_index += 1
        tip_text = HEALTH_TIPS[self._tip_index % len(HEALTH_TIPS)]
        self.sub.setText(" " + tip_text)
        self.speak_text(tip_text)

    def update_countdown(self):
        self.time_left -= 1
        self.progress_ring.set_values(self.time_left, self.total_time, self.time_left)

        # Escalation Beeps
        if self.settings.get("sound_fx", True):
            if self.time_left == self.total_time // 2 or (5 >= self.time_left > 0):
                self.play_sound()

        if self.time_left <= 0:
            self.stop_all()
            self.on_done(missed=True)

    def stop_all(self):
        self.timer.stop()
        self.tip_timer.stop()
        # Cleanup media player resources to prevent memory leaks
        if self.media_player:
            self.media_player.stop()
            self.media_player.deleteLater()
            self.media_player = None
        if self.audio_output:
            self.audio_output.deleteLater()
            self.audio_output = None
        # Cleanup TTS engine
        if self.tts_engine:
            try:
                self.tts_engine.stop()
            except Exception:
                pass
        self.close()

    def play_sound(self):
        if not self.settings.get("sound_fx", True):
            return

        mode = self.settings.get("sound_mode", "System Beep")
        sound_file = self.settings.get("custom_sound_file", "")

        if mode == "Custom Audio File" and sound_file:
            try:
                if os.path.exists(sound_file):
                    if self.media_player is None:
                        self.audio_output = QAudioOutput()
                        self.media_player = QMediaPlayer()
                        self.media_player.setAudioOutput(self.audio_output)
                    self.audio_output.setVolume(1.0)
                    self.media_player.setSource(QUrl.fromLocalFile(sound_file))
                    self.media_player.play()
                    return
            except Exception:
                pass

        QApplication.beep()

    def done(self):
        self.stop_all()
        self.on_done(missed=False)

    def skip(self):
        self.stop_all()
        self.on_skip()


# ================== MAIN APP DASHBOARD ==================
class DevEyeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.data = DataManager.load()
        self.check_streak()
        
        self.is_paused = False
        self.paused_by_idle = False
        self.current_phase = "focus"
        self.current_session_label = ""
        self.time_left_secs = self.data["settings"]["work_mins"] * 60
        self._session_count = self.data["settings"].get("current_session_count", 0)
        
        self.setWindowTitle("DevEye Ultimate")
        
        # INCREASED WINDOW SIZE TO ACCOMMODATE ALL BUTTONS WITH NATIVE PADDING
        self.setFixedSize(620, 520)
        
        self.mini_player = MiniPlayer(self)
        self.init_ui()
        self.apply_current_theme()
        self.init_tray()
        self.init_shortcuts()

        self.break_screen = BreakScreen(self, THEMES[self.data["settings"]["theme"]]["accent"], self.handle_done, self.handle_skip)

        self.tick_timer = QTimer()
        self.tick_timer.timeout.connect(self.tick)
        
        # Idle Tracking setup
        # Note: Idle detection runs on 60-second intervals, so pause timing may be up to ~1 minute later than threshold
        self.last_cursor_pos = QCursor.pos()
        self.idle_minutes = 0
        self.idle_timer = QTimer()
        self.idle_timer.timeout.connect(self.check_idle)
        self.idle_timer.start(60000) # Check every 1 minute
        
        # Install event filter for keyboard activity detection
        QApplication.instance().installEventFilter(self)

        if not self.data["settings"].get("startup_minimized", False):
            self.prompt_label_and_start()
        else:
            self.is_paused = True
            self.btn_pause.setText("Start")
            self.btn_pause.setObjectName("PrimaryButton")

        self.update_daily_goal()
        self.update_timer_display()

    def check_streak(self):
        # Streaks update only after a focus session is actually completed.
        if "streak" not in self.data["stats"]:
            self.data["stats"]["streak"] = 0
        if "last_date" not in self.data["stats"]:
            self.data["stats"]["last_date"] = ""

    def update_streak_after_completion(self):
        today = date.today().isoformat()
        last = self.data["stats"].get("last_date", "")
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        if last == today:
            return
        if last == yesterday:
            self.data["stats"]["streak"] += 1
        else:
            self.data["stats"]["streak"] = 1
        self.data["stats"]["last_date"] = today

    def eventFilter(self, obj, event):
        # Detect keyboard activity to reset idle timer
        if event.type() == QEvent.Type.KeyPress:
            if self.data["settings"].get("idle_detection", False):
                self.idle_minutes = 0
                # Trigger activity prompt if paused by idle
                if self.paused_by_idle and self.is_paused and self.current_phase == "focus":
                    msg = QMessageBox(self)
                    msg.setWindowTitle("You're back")
                    msg.setText("Activity detected. What would you like to do?")
                    resume_btn = msg.addButton("Resume", QMessageBox.ButtonRole.AcceptRole)
                    start_new_btn = msg.addButton("Start New", QMessageBox.ButtonRole.DestructiveRole)
                    msg.exec()

                    if msg.clickedButton() == start_new_btn:
                        self.record_partial_focus_before_restart()
                        self.paused_by_idle = False
                        self.reset_timer(user_triggered=True)
                    elif msg.clickedButton() == resume_btn:
                        self.toggle_pause()
                    else:
                        # Dialog closed without explicit choice, clear idle flag
                        self.paused_by_idle = False
        return super().eventFilter(obj, event)

    def check_idle(self):
        current_pos = QCursor.pos()
        if current_pos == self.last_cursor_pos:
            self.idle_minutes += 1
        else:
            self.idle_minutes = 0
            self.last_cursor_pos = current_pos

            # Ask what to do only if pause was caused by idle detection.
            if self.data["settings"].get("idle_detection", False) and self.paused_by_idle and self.is_paused and self.current_phase == "focus":
                msg = QMessageBox(self)
                msg.setWindowTitle("You're back")
                msg.setText("Activity detected. What would you like to do?")
                resume_btn = msg.addButton("Resume", QMessageBox.ButtonRole.AcceptRole)
                start_new_btn = msg.addButton("Start New", QMessageBox.ButtonRole.DestructiveRole)
                msg.exec()

                if msg.clickedButton() == start_new_btn:
                    self.record_partial_focus_before_restart()
                    self.paused_by_idle = False
                    self.reset_timer(user_triggered=True)
                elif msg.clickedButton() == resume_btn:
                    self.toggle_pause()
                else:
                    # Dialog closed without explicit choice, clear idle flag
                    self.paused_by_idle = False

        if self.data["settings"].get("idle_detection", False):
            thresh = self.data["settings"].get("idle_threshold_mins", 5)
            if self.idle_minutes >= thresh and not self.is_paused and self.current_phase == "focus":
                self.toggle_pause(from_idle=True)
                self.paused_by_idle = True
                self.tray.showMessage("Idle Detected", f"Focus paused after {thresh} mins of inactivity.", QSystemTrayIcon.MessageIcon.Information, 3000)

    def init_shortcuts(self):
        QShortcut(QKeySequence("Space"), self).activated.connect(self.toggle_pause)
        QShortcut(QKeySequence("Esc"), self).activated.connect(self.launch_mini_player)
        QShortcut(QKeySequence("Ctrl+,"), self).activated.connect(self.open_settings)
        QShortcut(QKeySequence("Ctrl+B"), self).activated.connect(self.force_break)

    def get_theme_colors(self):
        return THEMES.get(self.data["settings"].get("theme", "Emerald (Default)"), THEMES["Emerald (Default)"])

    def apply_current_theme(self):
        colors = self.get_theme_colors()
        font_family = self.data["settings"].get("font_family", "Segoe UI")
        font_size = self.data["settings"].get("font_size", 13)
        style = get_stylesheet(
            colors["accent"], colors["hover"],
            font_family, font_size,
            self.data["settings"].get("mini_bg_color", "Theme Surface")
        )
        self.setStyleSheet(style)
        self.mini_player.setStyleSheet(style)
        self.mini_player.setWindowOpacity(self.data["settings"].get("mini_opacity", 90) / 100.0)
        self.update_stats() 

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(30, 20, 30, 20)

        # --- HEADER & DAILY GOAL ---
        top_bar = QHBoxLayout()
        title_box = QHBoxLayout()
        title_label = QLabel("DevEye")
        title_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {TEXT_PRIMARY};")
        
        self.streak_badge = QLabel(f"🔥 {self.data['stats'].get('streak', 1)} Day Streak")
        self.streak_badge.setObjectName("StreakBadge")

        title_box.addWidget(title_label)
        title_box.addSpacing(10)
        title_box.addWidget(self.streak_badge)
        title_box.addStretch()

        self.btn_mini = QPushButton("Mini Player")
        self.btn_mini.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mini.setToolTip("Switch to Mini Player (Esc)")
        self.btn_mini.clicked.connect(self.launch_mini_player)
        top_bar.addLayout(title_box)
        top_bar.addWidget(self.btn_mini)

        self.goal_container = QWidget()
        goal_layout = QVBoxLayout(self.goal_container)
        goal_layout.setContentsMargins(0, 0, 0, 0)
        goal_layout.setSpacing(5)
        goal_labels = QHBoxLayout()
        self.goal_text = QLabel("Daily Focus Goal")
        self.goal_text.setObjectName("Subtitle")
        self.goal_progress_text = QLabel("0 / 4 hrs")
        self.goal_progress_text.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; font-weight: bold;")
        goal_labels.addWidget(self.goal_text)
        goal_labels.addStretch()
        goal_labels.addWidget(self.goal_progress_text)
        
        self.goal_bar = QProgressBar()
        self.goal_bar.setObjectName("GoalBar")
        self.goal_bar.setTextVisible(False)
        self.goal_bar.setMaximum(100)
        
        goal_layout.addLayout(goal_labels)
        goal_layout.addWidget(self.goal_bar)

        # --- TIMER AREA ---
        timer_layout = QVBoxLayout()
        timer_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        timer_layout.setSpacing(4)
        
        self.phase_label = QLabel("FOCUS SESSION")
        self.phase_label.setObjectName("Subtitle")
        self.phase_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.session_label_display = QLabel("")
        self.session_label_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.session_label_display.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; font-style: italic;")

        self.timer_label = QLabel()
        self.timer_label.setObjectName("TimerLabel")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.session_counter_label = QLabel("")
        self.session_counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.session_counter_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")

        timer_layout.addWidget(self.phase_label)
        timer_layout.addWidget(self.session_label_display)
        timer_layout.addWidget(self.timer_label)
        timer_layout.addWidget(self.session_counter_label)

        # --- STATS CARDS ---
        self.stats_container = QWidget()
        stats_layout = QHBoxLayout(self.stats_container)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(10)
        
        self.card_completed = StatCard("Sessions", 0, TEXT_PRIMARY) 
        self.card_focus = StatCard("Focus Hrs", "0.0", SUCCESS_COLOR)
        self.card_missed = StatCard("Missed", 0, WARNING_COLOR)
        self.card_skipped = StatCard("Skipped", 0, DANGER_COLOR)
        
        stats_layout.addWidget(self.card_completed)
        stats_layout.addWidget(self.card_focus)
        stats_layout.addWidget(self.card_missed)
        stats_layout.addWidget(self.card_skipped)

        # --- CONTROLS ---
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)
        
        self.btn_pause = QPushButton("Pause")
        self.btn_pause.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pause.clicked.connect(self.toggle_pause)

        self.btn_force_break = QPushButton("Break Now")
        self.btn_force_break.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_force_break.clicked.connect(self.force_break)
        
        btn_history = QPushButton("History")
        btn_history.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_history.clicked.connect(self.open_history)

        btn_settings = QPushButton("Settings")
        btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_settings.clicked.connect(self.open_settings)
        
        btn_quit = QPushButton("Quit")
        btn_quit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_quit.setObjectName("DangerButton")
        btn_quit.clicked.connect(self.quit_app)
        
        controls_layout.addWidget(self.btn_pause)
        controls_layout.addWidget(self.btn_force_break)
        controls_layout.addWidget(btn_history)
        controls_layout.addWidget(btn_settings)
        controls_layout.addWidget(btn_quit)

        # --- ASSEMBLE ---
        main_layout.addLayout(top_bar)
        main_layout.addSpacing(15)
        main_layout.addWidget(self.goal_container)
        main_layout.addStretch()
        main_layout.addLayout(timer_layout)
        main_layout.addStretch()
        main_layout.addWidget(self.stats_container)
        main_layout.addSpacing(25)
        main_layout.addLayout(controls_layout)
        
        self.apply_compact_mode()

    def apply_compact_mode(self):
        compact = self.data["settings"].get("compact_mode", False)
        self.goal_container.setVisible(not compact)
        self.stats_container.setVisible(not compact)
        self.setFixedSize(620, 330 if compact else 520)

    def create_tray_icon_image(self):
        pixmap = QPixmap(128, 128)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        accent = self.get_theme_colors()["accent"]
        painter.setBrush(QColor(accent))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(8, 8, 112, 112)
        
        pen = QPen(QColor(BG_COLOR))
        pen.setWidth(8)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(24, 24, 80, 80)
        painter.end()
        return QIcon(pixmap)

    def init_tray(self):
        self.tray = QSystemTrayIcon(self.create_tray_icon_image())
        self.tray.setToolTip("DevEye Ultimate")
        menu = QMenu()
        
        accent = self.get_theme_colors()["accent"]
        menu.setStyleSheet(f"QMenu {{ background-color: {SURFACE_COLOR}; color: {TEXT_PRIMARY}; border: 1px solid #334155; }} QMenu::item:selected {{ background-color: {accent}; }}")

        menu.addAction("Open Dashboard").triggered.connect(self.show_normal)
        menu.addAction("Mini Player").triggered.connect(self.launch_mini_player)
        menu.addAction("Break Now").triggered.connect(self.force_break)
        menu.addSeparator()
        menu.addAction("Exit").triggered.connect(self.exit_app)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self.show_normal() if r == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()

    def show_normal(self):
        self.mini_player.hide()
        self.show()
        self.raise_()
        self.activateWindow()

    def launch_mini_player(self):
        self.hide()
        # Restore saved position or use default
        saved_x = self.data["settings"].get("mini_player_x")
        saved_y = self.data["settings"].get("mini_player_y")
        if saved_x is not None and saved_y is not None:
            self.mini_player.move(saved_x, saved_y)
        elif self.mini_player.old_pos is None:
            screen = QApplication.primaryScreen().availableGeometry()
            self.mini_player.move(screen.width() - 220, 50)
        self.mini_player.show()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray.showMessage("DevEye Ultimate", "Running in background.", QSystemTrayIcon.MessageIcon.Information, 2000)

    def quit_app(self):
        self.hide()
        self.tray.showMessage("DevEye Ultimate", "Running in background.", QSystemTrayIcon.MessageIcon.Information, 2000)

    def exit_app(self):
        reply = QMessageBox.question(self, 'Confirm Exit', 'Are you sure you want to exit DevEye Ultimate?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.tray.hide()
            QApplication.quit()

    def tick(self):
        if self.is_paused: return
        self.time_left_secs -= 1
        
        if self.time_left_secs <= 0:
            self.tick_timer.stop()
            self._trigger_break()
        else:
            self.update_timer_display()

    def _trigger_break(self, increment_count=True):
        s = self.data["settings"]
        if increment_count:
            self._session_count += 1
        interval = s.get("long_break_interval", 0)
        long_break_mins = s.get("long_break_mins", 0)
        
        is_long_break = False
        if interval > 0 and long_break_mins > 0 and (self._session_count % interval == 0):
            is_long_break = True

        self.data["settings"]["current_session_count"] = self._session_count
        DataManager.save(self.data)
        self.current_phase = "break"
        self.phase_label.setText("BREAK TIME")

        session_num = self._session_count % interval if interval > 0 else 0
        self.break_screen.start(self.data["settings"], self.get_theme_colors(), session_num, interval, is_long_break)

    def force_break(self):
        self.tick_timer.stop()
        self._trigger_break(increment_count=False)

    def update_timer_display(self):
        mins, secs = divmod(self.time_left_secs, 60)
        time_str = f"{mins:02d}:{secs:02d}"
        self.timer_label.setText(time_str)
        self.mini_player.update_time(time_str, self.is_paused, self.data["settings"].get("strict_mode", False), self.current_phase)
        
        interval = self.data["settings"].get("long_break_interval", 0)
        if interval > 0:
            remaining = interval - (self._session_count % interval)
            self.session_counter_label.setText(f"Session {self._session_count + 1} | {remaining} until long break")
        else:
            self.session_counter_label.setText(f"Session {self._session_count + 1}")

        if self.current_session_label:
            self.session_label_display.setText(f"Tag: {self.current_session_label}")
        else:
            self.session_label_display.setText("")

    def update_daily_goal(self):
        total_mins = self.data["stats"].get("total_focus_mins", 0)
        goal_mins = self.data["settings"]["daily_goal_hrs"] * 60
        
        progress = int((total_mins / goal_mins) * 100) if goal_mins > 0 else 0
        self.goal_bar.setValue(min(progress, 100))
        
        hrs_done = round(total_mins / 60, 1)
        self.goal_progress_text.setText(f"{hrs_done} / {self.data['settings']['daily_goal_hrs']} hrs")
        self.streak_badge.setText(f"🔥 {self.data['stats'].get('streak', 1)} Day Streak")

    def prompt_label_and_start(self):
        if self.data["settings"].get("show_session_label", True):
            dlg = SessionLabelDialog(self)
            colors = self.get_theme_colors()
            dlg.setStyleSheet(get_stylesheet(
                colors["accent"], colors["hover"],
                self.data["settings"].get("font_family", "Segoe UI"),
                self.data["settings"].get("font_size", 13),
                self.data["settings"].get("mini_bg_color", "Theme Surface")
            ))
            dlg.exec()
            self.current_session_label = dlg.get_label()
        
        self.tick_timer.start(1000)

    def reset_timer(self, user_triggered=False):
        self.current_phase = "focus"
        self.current_session_label = ""  # Clear previous session label
        self.phase_label.setText("FOCUS SESSION")
        self.time_left_secs = self.data["settings"]["work_mins"] * 60
        self.update_timer_display()

        self.is_paused = False
        self.btn_pause.setText("Pause")
        self.btn_pause.setObjectName("")

        if not user_triggered:
            self.prompt_label_and_start()
        else:
            self.tick_timer.start(1000)



    def after_break_flow(self):
        flow_mode = self.data["settings"].get("after_break_flow", "Auto Restart")
        if flow_mode == "Ask Every Time":
            reply = QMessageBox.question(
                self,
                "Restart Focus?",
                "The break is over. Start the next focus session now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.reset_timer(user_triggered=True)
            else:
                self.is_paused = True
                self.btn_pause.setText("Start")
                self.btn_pause.setObjectName("PrimaryButton")
                self.apply_current_theme()
        else:
            self.reset_timer(user_triggered=True)

    def toggle_pause(self, from_idle=False):
        # Strict mode blocks manual pauses, but idle detection can still pause via from_idle=True
        if not from_idle and not self.is_paused and self.data["settings"].get("strict_mode", False) and self.current_phase == "focus":
            return 
            
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.paused_by_idle = from_idle
            self.btn_pause.setText("Resume")
            self.btn_pause.setObjectName("PrimaryButton")
            self.timer_label.setStyleSheet(f"color: {TEXT_MUTED};")
        else:
            if self.current_phase == "break" or self.time_left_secs <= 0:
                self.paused_by_idle = False
                self.reset_timer(user_triggered=True)
                return
            self.paused_by_idle = False
            self.btn_pause.setText("Pause")
            self.btn_pause.setObjectName("")
            self.timer_label.setStyleSheet(f"color: {TEXT_PRIMARY};")
            
            # If we're starting fresh, trigger the label prompt
            if self.time_left_secs == self.data["settings"]["work_mins"] * 60 and not self.tick_timer.isActive():
                self.prompt_label_and_start()
            
        self.apply_current_theme() 
        self.update_timer_display()

    def open_history(self):
        colors = self.get_theme_colors()
        theme_style = get_stylesheet(
            colors["accent"], colors["hover"],
            self.data["settings"].get("font_family", "Segoe UI"),
            self.data["settings"].get("font_size", 13),
            self.data["settings"].get("mini_bg_color", "Theme Surface")
        )
        hist_dialog = HistoryDialog(self.data, theme_style, colors["accent"], self)
        hist_dialog.exec()

    def open_settings(self):
        dialog = SettingsDialog(self, self)
        if dialog.exec():
            previous_settings = self.data["settings"]
            new_settings = dialog.get_settings()
            if new_settings.get("sound_mode") != "Custom Audio File":
                new_settings["custom_sound_file"] = ""
            new_settings["current_session_count"] = previous_settings.get("current_session_count", 0)
            new_settings["mini_player_x"] = previous_settings.get("mini_player_x")
            new_settings["mini_player_y"] = previous_settings.get("mini_player_y")
            self.data["settings"] = new_settings
            DataManager.save(self.data)
            
            self.apply_current_theme()
            self.apply_compact_mode()
            self.tray.setIcon(self.create_tray_icon_image()) 
            self.update_timer_display()    
            self.update_daily_goal()
            
            if self.data["settings"].get("run_on_startup", False) != previous_settings.get("run_on_startup", False):
                self.toggle_startup(self.data["settings"].get("run_on_startup", False))
            
            if self.data["settings"].get("strict_mode", False) and self.current_phase == "focus":
                self.btn_pause.setDisabled(not self.is_paused)
                self.btn_force_break.setDisabled(True)
            else:
                self.btn_pause.setDisabled(False)
                self.btn_force_break.setDisabled(False)

    def toggle_startup(self, enabled):
        if winreg is None:
            return
        
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "DevEyeUltimate"
        
        # Determine the command to run
        if getattr(sys, 'frozen', False):
            # Running as EXE
            cmd = f'"{sys.executable}"'
        else:
            # Running as script
            cmd = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if enabled:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            QMessageBox.warning(self, "Startup Error", f"Failed to modify startup settings: {e}")


    def update_stats(self):
        accent = self.get_theme_colors()["accent"]
        self.card_completed.set_value(self.data["stats"]["completed"])
        self.card_completed.value_label.setStyleSheet(f"color: {accent};")
        self.card_missed.set_value(self.data["stats"]["missed"])
        self.card_skipped.set_value(self.data["stats"]["skipped"])
        
        total_hrs = round(self.data["stats"].get("total_focus_mins", 0) / 60, 1)
        self.card_focus.set_value(str(total_hrs))
        self.update_daily_goal()

    def record_partial_focus_before_restart(self):
        if self.current_phase != "focus":
            return

        total_focus_secs = self.data["settings"]["work_mins"] * 60
        elapsed_secs = max(0, total_focus_secs - self.time_left_secs)
        if elapsed_secs <= 0:
            return

        elapsed_mins = round(elapsed_secs / 60, 1)
        self.data["stats"]["total_focus_mins"] += elapsed_mins
        self.data["stats"]["partial"] += 1
        DataManager.log_session(self.data, "partial", elapsed_mins, self.current_session_label or "Partial (Restarted)")
        DataManager.save(self.data)
        self.update_stats()

    def handle_done(self, missed=False):
        if missed: 
            self.data["stats"]["missed"] += 1
            DataManager.log_session(self.data, "missed", self.data["settings"]["work_mins"], self.current_session_label)
        else: 
            self.data["stats"]["completed"] += 1
            self.data["stats"]["total_focus_mins"] += self.data["settings"]["work_mins"]
            DataManager.log_session(self.data, "completed", self.data["settings"]["work_mins"], self.current_session_label)
            self.update_streak_after_completion()
            
        DataManager.save(self.data)
        self.update_stats()
        self.after_break_flow()

    def handle_skip(self):
        self.data["stats"]["skipped"] += 1
        DataManager.log_session(self.data, "skipped", self.data["settings"]["work_mins"], self.current_session_label)
        DataManager.save(self.data)
        self.update_stats()
        self.after_break_flow()


# ================== RUN ==================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
        
    window = DevEyeApp()
    if window.data["settings"].get("startup_minimized", False):
        QTimer.singleShot(0, window.launch_mini_player)
    else:
        window.show()
        
    sys.exit(app.exec())