import sys
import json
import os
import csv
import random
from datetime import datetime, date, timedelta
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QSystemTrayIcon, QMenu, 
    QMainWindow, QFrame, QDialog, QSpinBox, QListWidget,
    QCheckBox, QFormLayout, QGraphicsOpacityEffect, QGraphicsDropShadowEffect,
    QTabWidget, QComboBox, QProgressBar, QSlider, QFontComboBox,
    QFileDialog, QMessageBox, QGroupBox, QListWidgetItem
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRectF, QPoint
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QPen, QBrush, QShortcut, QKeySequence, QCursor

DATA_FILE = "deveye_data.json"

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

    QPushButton {{ background-color: rgba(255, 255, 255, 0.96); border: 1px solid rgba(0, 0, 0, 0.08); border-radius: 16px; padding: 8px 14px; color: {TEXT_PRIMARY}; font-weight: 600; min-height: 38px; }}
    QPushButton:hover {{ background-color: rgba(255, 255, 255, 1.0); border: 1px solid rgba(0, 0, 0, 0.12); }}
    QPushButton:disabled {{ background-color: rgba(255, 255, 255, 0.6); color: #B0B0B5; border: 1px solid rgba(0, 0, 0, 0.06); }}
    
    QPushButton#PrimaryButton {{ background-color: {accent_color}; border: none; color: #ffffff; }}
    QPushButton#PrimaryButton:hover {{ background-color: {accent_hover}; }}
    QPushButton#DangerButton {{ background-color: transparent; border: 1px solid rgba(255, 59, 48, 0.35); color: {DANGER_COLOR}; }}
    QPushButton#DangerButton:hover {{ background-color: rgba(255, 59, 48, 0.08); }}
    
    QPushButton#MiniBtn {{ border-radius: 999px; padding: 0; min-width: 26px; min-height: 26px; background-color: rgba(255, 255, 255, 0.96); border: 1px solid rgba(0, 0, 0, 0.08); font-size: 12px; }}
    QPushButton#MiniBtn:hover {{ background-color: rgba(255, 255, 255, 1.0); color: {accent_color}; border: 1px solid rgba(0, 0, 0, 0.12); }}
    QFrame#MiniPlayerFrame {{ background-color: {mini_bg_color}; border-radius: 20px; border: 1px solid rgba(0, 0, 0, 0.08); }}
    
    QTabWidget::pane {{ border: 1px solid rgba(0, 0, 0, 0.08); border-radius: 18px; background-color: rgba(255, 255, 255, 0.90); top: -1px; }}
    QTabBar::tab {{ background: {BG_COLOR}; color: {TEXT_MUTED}; padding: 8px 16px; border: 1px solid transparent; border-top-left-radius: 14px; border-top-right-radius: 14px; font-weight: 600; }}
    QTabBar::tab:selected {{ color: {accent_color}; border: 1px solid rgba(0, 0, 0, 0.08); border-bottom-color: rgba(255, 255, 255, 0.90); background: rgba(255, 255, 255, 0.90); }}
    
    QSpinBox, QComboBox {{ background-color: rgba(255, 255, 255, 0.96); border: 1px solid rgba(0, 0, 0, 0.08); border-radius: 12px; padding: 6px 10px; color: {TEXT_PRIMARY}; }}
    QSpinBox::up-button, QSpinBox::down-button {{ width: 0px; }}
    
    QCheckBox {{ color: {TEXT_PRIMARY}; spacing: 12px; }}
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
    QWidget {{ background-color: rgba(18, 18, 20, {alpha}); color: #FFFFFF; }}
    QLabel#OverlayTitle {{ font-size: 42px; font-weight: 700; letter-spacing: -0.8px; color: #FFFFFF; }}
    QLabel#OverlaySub {{ font-size: 20px; color: rgba(255, 255, 255, 0.85); font-weight: 400; }}
    QLabel#OverlayAffirm {{ font-size: 16px; color: rgba(255, 255, 255, 0.95); font-weight: 500; }}
    """

# ================== DATA MANAGER ==================
class DataManager:
    @staticmethod
    def get_defaults():
        return {
            "stats": {
                "completed": 0, "missed": 0, "skipped": 0, 
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
                "show_session_label": True
            }
        }

    @staticmethod
    def load():
        default_data = DataManager.get_defaults()
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
        except: return default_data

    @staticmethod
    def save(data):
        with open(DATA_FILE, "w") as f: json.dump(data, f, indent=4)

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
            writer.writerow(["Date", "Type", "Duration (mins)", "Tag"])
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

        painter.setPen(QPen(QColor("#FFFFFF")))
        font = painter.font()
        font.setPixelSize(48)
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


class HistoryDialog(QDialog):
    def __init__(self, data, theme_style, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Data & History")
        self.setFixedSize(450, 400)
        self.setStyleSheet(theme_style)
        self.data = data
        layout = QVBoxLayout(self)
        
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
                icon = {"completed": "✅", "missed": "⏰", "skipped": "⏭"}.get(entry.get("type", ""), "•")
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
            self.data["stats"] = {"completed": 0, "missed": 0, "skipped": 0, "streak": 0, "last_date": "", "total_focus_mins": 0}
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
        self.setFixedSize(180, 50)
        self.old_pos = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        self.bg_frame = QFrame()
        self.bg_frame.setObjectName("MiniPlayerFrame")
        bg_layout = QHBoxLayout(self.bg_frame)
        bg_layout.setContentsMargins(12, 0, 12, 0)
        
        self.phase_dot = QLabel("●")
        self.phase_dot.setStyleSheet("font-size: 10px; color: #10B981;")

        self.time_label = QLabel("00:00")
        self.time_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        self.btn_pause = QPushButton("Pause")
        self.btn_pause.setObjectName("MiniBtn")
        self.btn_pause.setFixedSize(26, 26)
        self.btn_pause.clicked.connect(self.app.toggle_pause)

        self.btn_expand = QPushButton("Open")
        self.btn_expand.setObjectName("MiniBtn")
        self.btn_expand.setFixedSize(26, 26)
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
        self.time_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {TEXT_MUTED if paused else TEXT_PRIMARY};")
        self.phase_dot.setStyleSheet(f"font-size: 10px; color: {'#F59E0B' if phase == 'break' else '#10B981'};")
        
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

        bl.addWidget(self.strict_check)
        bl.addWidget(self.sound_check)
        bl.addWidget(self.resume_check)
        bl.addWidget(self.startup_check)
        bl.addWidget(self.session_label_check)

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
        ov_l.addWidget(self.tips_check)
        ov_l.addWidget(self.affirm_check)
        
        msg_grp = QGroupBox("CUSTOM MESSAGE")
        ml = QVBoxLayout(msg_grp)
        ml.addWidget(QLabel("Override the 'Rest Your Eyes' title:"))
        self.msg_input = QLineEdit(self.settings.get("custom_break_msg", ""))
        self.msg_input.setPlaceholderText("e.g. Stretch and hydrate! 💧")
        ml.addWidget(self.msg_input)

        overlay_layout.addWidget(over_grp)
        overlay_layout.addWidget(msg_grp)
        overlay_layout.addStretch()

        tabs.addTab(tab_core, "Timer")
        tabs.addTab(tab_behavior, "Behavior")
        tabs.addTab(tab_app, "Appearance")
        tabs.addTab(tab_overlay, "Overlay")

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
            "auto_resume": self.resume_check.isChecked(),
            "startup_minimized": self.startup_check.isChecked(),
            "show_session_label": self.session_label_check.isChecked(),
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
            "custom_break_msg": self.msg_input.text()
        }


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
        
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)

        self.title = QLabel("Rest Your Eyes")
        self.title.setObjectName("OverlayTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.sub = QLabel("")
        self.sub.setObjectName("OverlaySub")
        self.sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.affirm_label = QLabel("")
        self.affirm_label.setObjectName("OverlayAffirm")
        self.affirm_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.progress_ring = CircularProgress(self.accent_color)
        
        self.session_info = QLabel("")
        self.session_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.session_info.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 13px;")

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        
        self.done_btn = QPushButton("✓ I'm Done")
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

        layout.addStretch()
        layout.addWidget(self.title)
        layout.addWidget(self.sub)
        layout.addWidget(self.affirm_label)
        layout.addSpacing(30)
        layout.addWidget(self.progress_ring, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.session_info)
        layout.addSpacing(40)
        layout.addLayout(btn_layout)
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

        self.total_time = (self.settings.get("long_break_mins", 0) * 60) if is_long_break else self.settings.get("break_secs", 20)
        self.time_left = self.total_time
        self.progress_ring.set_values(self.time_left, self.total_time, self.time_left)
        
        self.skip_btn.setVisible(not self.settings.get("strict_mode", False))

        if session_num > 0 and total_sessions > 0 and not is_long_break:
            self.session_info.setText(f"Session {session_num} of {total_sessions} before long break")
        else:
            self.session_info.setText("")

        if self.settings.get("show_affirmations", True):
            self.affirm_label.setText(AFFIRMATIONS[self._affirm_index % len(AFFIRMATIONS)])
            self._affirm_index += 1
        else:
            self.affirm_label.setText("")

        if self.settings.get("show_eye_tips", True):
            self.sub.setText("💡 " + HEALTH_TIPS[self._tip_index % len(HEALTH_TIPS)])
            self._tip_index += 1
            self.tip_timer.start(7000)
        else:
            self.sub.setText("Close your eyes and relax.")
            self.tip_timer.stop()

        if self.settings.get("sound_fx", True):
            QApplication.beep()

        self.showFullScreen()
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.start()
        self.timer.start(1000)

    def rotate_tip(self):
        self._tip_index += 1
        self.sub.setText("💡 " + HEALTH_TIPS[self._tip_index % len(HEALTH_TIPS)])

    def update_countdown(self):
        self.time_left -= 1
        self.progress_ring.set_values(self.time_left, self.total_time, self.time_left)

        # Escalation Beeps
        if self.settings.get("sound_fx", True):
            if self.time_left == self.total_time // 2 or (5 >= self.time_left > 0):
                QApplication.beep()

        if self.time_left <= 0:
            self.stop_all()
            self.on_done(missed=True)

    def stop_all(self):
        self.timer.stop()
        self.tip_timer.stop()
        self.close()

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
        self.last_cursor_pos = QCursor.pos()
        self.idle_minutes = 0
        self.idle_timer = QTimer()
        self.idle_timer.timeout.connect(self.check_idle)
        self.idle_timer.start(60000) # Check every 1 minute

        if not self.data["settings"].get("startup_minimized", False):
            self.prompt_label_and_start()
        else:
            self.is_paused = True
            self.btn_pause.setText("Start")
            self.btn_pause.setObjectName("PrimaryButton")

        self.update_daily_goal()
        self.update_timer_display()

    def check_streak(self):
        today = date.today().isoformat()
        last = self.data["stats"].get("last_date", "")
        if last == today: return
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        if last == yesterday:
            self.data["stats"]["streak"] += 1
        elif last != today:
            self.data["stats"]["streak"] = 1
        self.data["stats"]["last_date"] = today
        DataManager.save(self.data)

    def check_idle(self):
        current_pos = QCursor.pos()
        if current_pos == self.last_cursor_pos:
            self.idle_minutes += 1
        else:
            self.idle_minutes = 0
            self.last_cursor_pos = current_pos

        if self.data["settings"].get("idle_detection", False):
            thresh = self.data["settings"].get("idle_threshold_mins", 5)
            if self.idle_minutes >= thresh and not self.is_paused and self.current_phase == "focus":
                self.toggle_pause()
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
        btn_quit.clicked.connect(QApplication.quit)
        
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
        menu.addAction("Quit").triggered.connect(QApplication.quit)

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
        if self.mini_player.old_pos is None:
            screen = QApplication.primaryScreen().availableGeometry()
            self.mini_player.move(screen.width() - 220, 50)
        self.mini_player.show()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray.showMessage("DevEye Ultimate", "Running in background.", QSystemTrayIcon.MessageIcon.Information, 2000)

    def tick(self):
        if self.is_paused: return
        self.time_left_secs -= 1
        
        if self.time_left_secs <= 0:
            self.tick_timer.stop()
            self._trigger_break()
        else:
            self.update_timer_display()

    def _trigger_break(self):
        s = self.data["settings"]
        self._session_count += 1
        interval = s.get("long_break_interval", 0)
        long_break_mins = s.get("long_break_mins", 0)
        
        is_long_break = False
        if interval > 0 and long_break_mins > 0 and (self._session_count % interval == 0):
            is_long_break = True

        self.data["settings"]["current_session_count"] = self._session_count
        self.current_phase = "break"
        self.phase_label.setText("BREAK TIME")

        session_num = self._session_count % interval if interval > 0 else 0
        self.break_screen.start(self.data["settings"], self.get_theme_colors(), session_num, interval, is_long_break)

    def force_break(self):
        self.tick_timer.stop()
        self._trigger_break()

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
        self.phase_label.setText("FOCUS SESSION")
        self.time_left_secs = self.data["settings"]["work_mins"] * 60
        self.update_timer_display()
        
        if not user_triggered and not self.data["settings"].get("auto_resume", False):
            self.is_paused = True
            self.btn_pause.setText("Start")
            self.btn_pause.setObjectName("PrimaryButton")
            self.apply_current_theme() 
        else:
            if not user_triggered:
                self.prompt_label_and_start()
            else:
                self.tick_timer.start(1000)

    def toggle_pause(self):
        if not self.is_paused and self.data["settings"].get("strict_mode", False) and self.current_phase == "focus":
            return 
            
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.btn_pause.setText("Resume")
            self.btn_pause.setObjectName("PrimaryButton")
            self.timer_label.setStyleSheet(f"color: {TEXT_MUTED};")
        else:
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
        hist_dialog = HistoryDialog(self.data, theme_style, self)
        hist_dialog.exec()

    def open_settings(self):
        dialog = SettingsDialog(self, self)
        if dialog.exec():
            self.data["settings"] = dialog.get_settings()
            DataManager.save(self.data)
            
            self.apply_current_theme()
            self.apply_compact_mode()
            self.tray.setIcon(self.create_tray_icon_image()) 
            self.update_timer_display()    
            self.update_daily_goal()
            
            if self.data["settings"].get("strict_mode", False) and self.current_phase == "focus":
                self.btn_pause.setDisabled(not self.is_paused)
                self.btn_force_break.setDisabled(True)
            else:
                self.btn_pause.setDisabled(False)
                self.btn_force_break.setDisabled(False)

    def update_stats(self):
        accent = self.get_theme_colors()["accent"]
        self.card_completed.set_value(self.data["stats"]["completed"])
        self.card_completed.value_label.setStyleSheet(f"color: {accent};")
        self.card_missed.set_value(self.data["stats"]["missed"])
        self.card_skipped.set_value(self.data["stats"]["skipped"])
        
        total_hrs = round(self.data["stats"].get("total_focus_mins", 0) / 60, 1)
        self.card_focus.set_value(str(total_hrs))
        self.update_daily_goal()

    def handle_done(self, missed=False):
        if missed: 
            self.data["stats"]["missed"] += 1
            DataManager.log_session(self.data, "missed", self.data["settings"]["work_mins"], self.current_session_label)
        else: 
            self.data["stats"]["completed"] += 1
            self.data["stats"]["total_focus_mins"] += self.data["settings"]["work_mins"]
            DataManager.log_session(self.data, "completed", self.data["settings"]["work_mins"], self.current_session_label)
            
        DataManager.save(self.data)
        self.update_stats()
        self.reset_timer()

    def handle_skip(self):
        self.data["stats"]["skipped"] += 1
        DataManager.log_session(self.data, "skipped", self.data["settings"]["work_mins"], self.current_session_label)
        DataManager.save(self.data)
        self.update_stats()
        self.reset_timer()


# ================== RUN ==================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
        
    window = DevEyeApp()
    if not window.data["settings"].get("startup_minimized", False):
        window.show()
        
    sys.exit(app.exec())