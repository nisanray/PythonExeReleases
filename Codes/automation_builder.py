import sys
import threading
import time
import json
import os
import subprocess
import logging
import copy
from typing import List
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QMenuBar, QMenu,
    QPushButton, QLabel, QListWidget, QSpinBox, QCheckBox, QSplitter, QFrame, QInputDialog,
    QMessageBox, QDialog, QComboBox, QFileDialog, QLineEdit, QDoubleSpinBox, QListWidgetItem,
    QFormLayout, QGroupBox, QSizePolicy, QGridLayout, QTextEdit, QStyleFactory
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QKeySequence, QFont, QCursor, QPalette, QPixmap

try:
    import pyautogui
    # Configure PyAutoGUI settings for better reliability
    pyautogui.FAILSAFE = False  # Disable fail-safe for production use
    pyautogui.PAUSE = 0.1      # Pause between actions for stability
    logging.info("PyAutoGUI imported and configured successfully")
    logging.debug(f"Screen size: {pyautogui.size()}")
    
    # Safely import pyscreeze to handle ImageNotFoundException gracefully
    try:
        import pyscreeze
        ImageNotFoundException = pyscreeze.ImageNotFoundException
    except ImportError:
        ImageNotFoundException = Exception

except ImportError as e:
    pyautogui = None
    ImageNotFoundException = Exception
    logging.error(f"PyAutoGUI not available - automation features disabled: {e}")
except Exception as e:
    pyautogui = None
    ImageNotFoundException = Exception
    logging.error(f"Failed to configure PyAutoGUI: {e}")

# Safe clipboard import to avoid Qt cross-thread crashes
try:
    import pyperclip
except ImportError:
    pyperclip = None
    logging.warning("pyperclip not found. Clipboard actions disabled.")

# --- Logging Setup ---
try:
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "automation.log")
    logging.basicConfig(
        level=logging.DEBUG, 
        format="%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info(f"Logging initialized. Log file: {log_file}")
except Exception as e:
    print(f"Failed to initialize logging: {e}")
    logging.basicConfig(level=logging.INFO)
    logging.error(f"Logging setup failed: {e}")

def lock_workstation():
    """Lock the workstation based on the operating system."""
    try:
        if sys.platform == "win32":
            logging.info("Attempting to lock Windows workstation")
            subprocess.call("rundll32.exe user32.dll,LockWorkStation")
        elif sys.platform.startswith("linux"):
            logging.info("Attempting to lock Linux workstation")
            if os.system("xdg-screensaver lock") != 0:
                os.system("gnome-screensaver-command -l || dm-tool lock")
        elif sys.platform == "darwin":
            logging.info("Attempting to lock macOS workstation")
            os.system(
                """/System/Library/CoreServices/Menu\\ Extras/User.menu/Contents/Resources/CGSession -suspend"""
            )
        else:
            logging.warning(f"Workstation locking not supported on platform: {sys.platform}")
    except Exception as e:
        logging.error(f"Failed to lock workstation: {e}")
###
# ---- Model for a sequence step ----
class Step:
    def __init__(self, action: str, params: dict, delay: float = 0.5, note: str = ""):
        self.action = action
        self.params = params
        self.delay = delay
        self.note = note

    def to_dict(self):
        return {
            "action": self.action,
            "params": self.params,
            "delay": self.delay,
            "note": self.note
        }

    @staticmethod
    def from_dict(d):
        return Step(d["action"], d["params"], d.get("delay", 0.5), d.get("note", ""))

    def __str__(self):
        p = self.params
        desc = ""
        icon = "🔹"
        if self.action == "Key Press":
            icon, desc = "⌨️", f"Key Press: '{p.get('key','')}'"
        elif self.action == "Type Text":
            icon, desc = "📝", f"Type: \"{p.get('text','')}\""
        elif self.action == "Mouse Click":
            icon, desc = "🖱️", f"Mouse Click ({p.get('button','left')}) at ({p.get('x',0)},{p.get('y',0)})"
        elif self.action == "Mouse Move":
            icon, desc = "↗️", f"Mouse Move to ({p.get('x',0)},{p.get('y',0)})"
        elif self.action == "Mouse Drag":
            icon, desc = "🤚", f"Mouse Drag to ({p.get('x',0)},{p.get('y',0)})"
        elif self.action == "Mouse Scroll":
            icon, desc = "📜", f"Mouse Scroll ({p.get('clicks',0)})"
        elif self.action == "Pause":
            icon, desc = "⏳", f"Pause {p.get('seconds',1)}s"
        elif self.action == "Key Down":
            icon, desc = "⬇️", f"Key Down: '{p.get('key','')}'"
        elif self.action == "Key Up":
            icon, desc = "⬆️", f"Key Up: '{p.get('key','')}'"
        elif self.action == "Image Click":
            inst = p.get('instance', 'first')
            tgt = p.get('target', 'center')
            conf = p.get('confidence', 0.9)
            icon, desc = "🖼️", f"Image Click ({inst}, {tgt}, {conf*100}%): '{os.path.basename(p.get('path',''))}'"
        elif self.action == "Wait Image":
            icon, desc = "👁️", f"Wait Image ({p.get('confidence',0.9)*100}%): '{os.path.basename(p.get('path',''))}' (Max {p.get('timeout',10)}s)"
        elif self.action == "Take Screenshot":
            icon, desc = "📸", f"Screenshot: '{os.path.basename(p.get('path',''))}'"
        elif self.action == "Hotkey":
            icon, desc = "🔥", f"Hotkey: {p.get('hotkey','')}"
        elif self.action == "Run Command":
            icon, desc = "🚀", f"Run: {p.get('command','')}"
        elif self.action == "Python Code":
            icon, desc = "🐍", f"Python Snippet ({len(p.get('code','').splitlines())} lines)"
        elif self.action == "Clipboard":
            icon, desc = "📋", f"Clipboard: Set Text"
        elif self.action == "Type Clipboard":
            icon, desc = "📋", "Type current clipboard content"
        elif self.action == "System Beep":
            icon, desc = "🔊", "Play system beep/alert"
        else:
            desc = f"{self.action}: {self.params}"
            
        if self.note:
            desc += f" [{self.note}]"
        if self.delay > 0:
            desc += f" (delay={self.delay:.2f}s)"
        return f"{icon} {desc}"

# --- Custom Button Styles ---
class StyledButton(QPushButton):
    def __init__(self, text, base_color, hover_color, pressed_color, *args, **kwargs):
        super().__init__(text, *args, **kwargs)
        self.base_color = base_color
        self.hover_color = hover_color
        self.pressed_color = pressed_color
        self.setStyleSheet(self.get_style(self.base_color))
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def enterEvent(self, event):
        self.setStyleSheet(self.get_style(self.hover_color))
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(self.get_style(self.base_color))
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.setStyleSheet(self.get_style(self.pressed_color))
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.setStyleSheet(self.get_style(self.hover_color))
        super().mouseReleaseEvent(event)

    def get_style(self, color):
        return f"background: {color}; color: #fff; font-weight: bold; border-radius: 6px; height: 36px; font-size: 15px; margin-bottom: 4px;"

class AnimatedButton(StyledButton):
    def __init__(self, text, base_color, hover_color, pressed_color, *args, **kwargs):
        super().__init__(text, base_color, hover_color, pressed_color, *args, **kwargs)
        self.animation = None
        self.is_animated = False
        self.original_text = text
        
    def start_pulse_animation(self, pulse_color="#ff6b6b"):
        if self.animation:
            self.animation.stop()
        self.animation = QPropertyAnimation(self, b"styleSheet")
        self.animation.setDuration(1000)
        self.animation.setLoopCount(-1)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        style1 = self.get_style(self.base_color)
        style2 = self.get_style(pulse_color)
        self.animation.setKeyValueAt(0, style1)
        self.animation.setKeyValueAt(0.5, style2)
        self.animation.setKeyValueAt(1, style1)
        self.animation.start()
        self.is_animated = True
        
    def stop_animation(self):
        if self.animation:
            self.animation.stop()
            self.animation = None
        self.setStyleSheet(self.get_style(self.base_color))
        self.is_animated = False
        
    def set_animated_text(self, text):
        self.setText(text)

# --- Unified Dialogs for Best UX ---
class UnifiedStepDialog(QDialog):
    """A highly customizable single-window dialog for adding/editing ALL regular steps."""
    step_confirmed = pyqtSignal(Step)

    def __init__(self, action: str, existing_step: Step = None, parent=None):
        super().__init__(parent)
        self.action = action
        self.existing = existing_step
        self.widgets = {} 
        
        mode = "Edit" if existing_step else "Add"
        self.setWindowTitle(f"{mode} Step: {action}")
        self.setMinimumWidth(450)
        
        logging.debug(f"Opened UnifiedStepDialog for {mode} {action}")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        action_group = QGroupBox("Action Parameters")
        action_group.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        form = QFormLayout(action_group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)
        
        p = self.existing.params if self.existing else {}

        try:
            if self.action == "Type Text":
                w = QLineEdit(p.get("text", ""))
                w.setPlaceholderText("Text to type out...")
                form.addRow("Text:", w)
                self.widgets["text"] = w

            elif self.action in ["Mouse Click", "Mouse Move"]:
                w_x = QSpinBox(); w_x.setRange(-10000, 10000); w_x.setValue(p.get("x", 0))
                w_y = QSpinBox(); w_y.setRange(-10000, 10000); w_y.setValue(p.get("y", 0))
                form.addRow("X Coordinate:", w_x)
                form.addRow("Y Coordinate:", w_y)
                self.widgets["x"] = w_x
                self.widgets["y"] = w_y
                if self.action == "Mouse Click":
                    w_btn = QComboBox()
                    w_btn.addItems(["left", "right", "middle"])
                    w_btn.setCurrentText(p.get("button", "left"))
                    form.addRow("Mouse Button:", w_btn)
                    self.widgets["button"] = w_btn

            elif self.action == "Mouse Drag":
                w_x = QSpinBox(); w_x.setRange(-10000, 10000); w_x.setValue(p.get("x", 0))
                w_y = QSpinBox(); w_y.setRange(-10000, 10000); w_y.setValue(p.get("y", 0))
                w_dur = QDoubleSpinBox(); w_dur.setRange(0.1, 10.0); w_dur.setSingleStep(0.1); w_dur.setValue(p.get("duration", 0.5))
                w_btn = QComboBox(); w_btn.addItems(["left", "right"]); w_btn.setCurrentText(p.get("button", "left"))
                form.addRow("Target X:", w_x)
                form.addRow("Target Y:", w_y)
                form.addRow("Duration (s):", w_dur)
                form.addRow("Button:", w_btn)
                self.widgets.update({"x": w_x, "y": w_y, "duration": w_dur, "button": w_btn})

            elif self.action == "Mouse Scroll":
                w = QSpinBox(); w.setRange(-10000, 10000); w.setSingleStep(10); w.setValue(p.get("clicks", -100))
                w.setToolTip("Positive numbers scroll UP, negative numbers scroll DOWN.")
                form.addRow("Scroll Clicks:", w)
                self.widgets["clicks"] = w

            elif self.action == "Pause":
                w = QDoubleSpinBox(); w.setRange(0.1, 3600); w.setSingleStep(0.5); w.setValue(p.get("seconds", 1.0))
                form.addRow("Pause (seconds):", w)
                self.widgets["seconds"] = w

            elif self.action in ["Image Click", "Wait Image"]:
                h_box = QHBoxLayout()
                w_path = QLineEdit(p.get("path", ""))
                w_path.setReadOnly(True)
                w_btn = QPushButton("Browse...")
                h_box.addWidget(w_path)
                h_box.addWidget(w_btn)
                form.addRow("Image File:", h_box)
                
                preview_lbl = QLabel("No Image Selected")
                preview_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                preview_lbl.setStyleSheet("border: 1px dashed #aaa; background: #f9f9f9; padding: 5px;")
                preview_lbl.setMinimumHeight(150)
                form.addRow("Preview:", preview_lbl)
                
                w_btn.clicked.connect(lambda: self.browse_image(w_path, preview_lbl))
                self.widgets["path"] = w_path
                
                if p.get("path", ""):
                    self.load_preview(p["path"], preview_lbl)

                # Shared image parameters
                w_conf = QDoubleSpinBox()
                w_conf.setRange(0.1, 1.0)
                w_conf.setSingleStep(0.05)
                w_conf.setValue(p.get("confidence", 0.9))
                w_conf.setToolTip("Image match confidence (requires OpenCV). 0.9 = 90% match.")
                form.addRow("Match Confidence:", w_conf)
                self.widgets["confidence"] = w_conf

                if self.action == "Image Click":
                    w_inst = QComboBox()
                    w_inst.addItems(["first", "last", "top", "bottom", "left", "right", "center"])
                    w_inst.setCurrentText(p.get("instance", "first"))
                    form.addRow("Match Instance:", w_inst)
                    self.widgets["instance"] = w_inst

                    w_tgt = QComboBox()
                    w_tgt.addItems(["center", "top-left", "top-right", "bottom-left", "bottom-right", "top-center", "bottom-center", "left-center", "right-center"])
                    w_tgt.setCurrentText(p.get("target", "center"))
                    form.addRow("Click Position:", w_tgt)
                    self.widgets["target"] = w_tgt

                if self.action == "Wait Image":
                    w_to = QDoubleSpinBox(); w_to.setRange(1.0, 3600.0); w_to.setValue(p.get("timeout", 10.0))
                    form.addRow("Timeout (s):", w_to)
                    self.widgets["timeout"] = w_to

            elif self.action == "Take Screenshot":
                h_box = QHBoxLayout()
                w_path = QLineEdit(p.get("path", "screenshot.png"))
                w_btn = QPushButton("Browse...")
                h_box.addWidget(w_path)
                h_box.addWidget(w_btn)
                form.addRow("Save Path:", h_box)
                w_btn.clicked.connect(lambda: self.browse_save_path(w_path))
                self.widgets["path"] = w_path

            elif self.action == "Run Command":
                w = QLineEdit(p.get("command", ""))
                w.setPlaceholderText("e.g. calc.exe or python script.py")
                form.addRow("Shell Command:", w)
                self.widgets["command"] = w

            elif self.action == "Python Code":
                w = QTextEdit(p.get("code", ""))
                w.setPlaceholderText("import pyautogui\npyautogui.alert('Hello')")
                w.setMinimumHeight(100)
                form.addRow("Python Code:", w)
                self.widgets["code"] = w

            elif self.action == "Clipboard":
                w = QLineEdit(p.get("text", ""))
                w.setPlaceholderText("Text to copy to clipboard...")
                form.addRow("Text to Copy:", w)
                self.widgets["text"] = w

            elif self.action in ["Type Clipboard", "System Beep"]:
                lbl = QLabel("No configuration needed for this step.")
                lbl.setStyleSheet("color: #7f8c8d; font-style: italic;")
                form.addRow(lbl)

            layout.addWidget(action_group)

            step_group = QGroupBox("Step Settings")
            step_group.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            step_form = QFormLayout(step_group)
            step_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
            
            self.delay_spin = QDoubleSpinBox()
            self.delay_spin.setRange(0, 30)
            self.delay_spin.setSingleStep(0.1)
            self.delay_spin.setValue(self.existing.delay if self.existing else 0.5)
            
            self.note_edit = QLineEdit(self.existing.note if self.existing else "")
            self.note_edit.setPlaceholderText("Optional description of this step...")
            
            step_form.addRow("Delay After (s):", self.delay_spin)
            step_form.addRow("Note:", self.note_edit)
            
            layout.addWidget(step_group)

            btn_h = QHBoxLayout()
            btn_h.addStretch(1)
            self.ok_btn = StyledButton("Save Step", "#27ae60", "#218c53", "#145d32")
            self.ok_btn.setFixedWidth(120)
            self.ok_btn.clicked.connect(self.accept_step)
            self.cancel_btn = StyledButton("Cancel", "#bdc3c7", "#979a9a", "#616a6b")
            self.cancel_btn.setFixedWidth(90)
            self.cancel_btn.clicked.connect(self.reject)
            
            btn_h.addWidget(self.ok_btn)
            btn_h.addWidget(self.cancel_btn)
            layout.addLayout(btn_h)

        except Exception as e:
            logging.error(f"Error generating UI for UnifiedStepDialog: {e}")
            QMessageBox.critical(self, "UI Error", f"Failed to build dialog:\n{e}")

    def browse_image(self, path_edit: QLineEdit, preview_lbl: QLabel):
        try:
            fname, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.jfif)")
            if fname:
                path_edit.setText(fname)
                self.load_preview(fname, preview_lbl)
        except Exception as e:
            logging.error(f"Error in image picker: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load image:\n{e}")

    def browse_save_path(self, path_edit: QLineEdit):
        fname, _ = QFileDialog.getSaveFileName(self, "Save Screenshot", "screenshot.png", "Images (*.png *.jpg)")
        if fname:
            path_edit.setText(fname)

    def load_preview(self, path: str, label: QLabel):
        if not os.path.exists(path):
            label.setText("Image not found on disk")
            return
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            label.setPixmap(pixmap.scaled(350, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            label.setText("Invalid Image Format")
            logging.warning(f"Selected invalid image file: {path}")

    def accept_step(self):
        try:
            params = {}
            for key, w in self.widgets.items():
                if isinstance(w, QSpinBox) or isinstance(w, QDoubleSpinBox):
                    params[key] = w.value()
                elif isinstance(w, QLineEdit):
                    val = w.text()
                    if not val and key in ["path", "command"]:
                        QMessageBox.warning(self, "Missing Input", f"{key.capitalize()} cannot be empty!")
                        return
                    params[key] = val
                elif isinstance(w, QTextEdit):
                    params[key] = w.toPlainText()
                elif isinstance(w, QComboBox):
                    params[key] = w.currentText()

            delay = self.delay_spin.value()
            note = self.note_edit.text()

            new_step = Step(self.action, params, delay, note)
            logging.debug(f"UnifiedStepDialog confirmed step: {new_step}")
            self.step_confirmed.emit(new_step)
            self.accept()
        except Exception as e:
            logging.error(f"Error accepting UnifiedStepDialog: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save step settings:\n{e}")

class KeyPressDialog(QDialog):
    step_confirmed = pyqtSignal(Step)
    def __init__(self, action: str, existing_step: Step=None, parent=None):
        super().__init__(parent)
        self.action = action
        self.existing = existing_step
        self._awaiting_key = False
        
        mode = "Edit" if existing_step else "Add"
        self.setWindowTitle(f"{mode} Step: {action}")
        self.setModal(True)
        self.setFixedWidth(420)
        
        p = existing_step.params if existing_step else {}
        self._captured_key = p.get("hotkey", p.get("key", ""))
        self._captured_display = self._captured_key if self._captured_key else "None captured"

        self.init_ui()

    def init_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(16, 16, 16, 16)
        vbox.setSpacing(13)
        
        h_key = QHBoxLayout()
        self.capture_btn = StyledButton("Click then Press Key", "#2980b9", "#20609b", "#133864")
        self.capture_btn.clicked.connect(self.begin_key_capture)
        h_key.addWidget(self.capture_btn, 2)
        
        self.captured_label = QLabel(f"<b>Captured:</b> {self._captured_display}")
        self.captured_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_key.addWidget(self.captured_label, 1)
        vbox.addLayout(h_key)

        step_group = QGroupBox("Step Settings")
        step_form = QFormLayout(step_group)
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0, 30); self.delay_spin.setSingleStep(0.1)
        self.delay_spin.setValue(self.existing.delay if self.existing else 0.5)
        
        self.note_edit = QLineEdit(self.existing.note if self.existing else "")
        self.note_edit.setPlaceholderText("Optional description...")
        
        step_form.addRow("Delay After (s):", self.delay_spin)
        step_form.addRow("Note:", self.note_edit)
        vbox.addWidget(step_group)

        btn_h = QHBoxLayout()
        btn_h.addStretch(1)
        self.ok_btn = StyledButton("Save Step", "#27ae60", "#218c53", "#145d32")
        self.ok_btn.clicked.connect(self.accept_step)
        self.cancel_btn = StyledButton("Cancel", "#bdc3c7", "#979a9a", "#616a6b")
        self.cancel_btn.clicked.connect(self.reject)
        btn_h.addWidget(self.ok_btn)
        btn_h.addWidget(self.cancel_btn)
        vbox.addLayout(btn_h)

    def begin_key_capture(self):
        try:
            self._awaiting_key = True
            self.capture_btn.setText("...Press any key...")
            self.grabKeyboard()
        except Exception as e:
            logging.error(f"Failed to begin key capture: {e}")
            self._awaiting_key = False

    def keyPressEvent(self, event):
        try:
            if self._awaiting_key:
                key = event.key()
                mods = event.modifiers().value
                kseq = QKeySequence(mods | key)
                kstr = kseq.toString()
                if not kstr: kstr = event.text()
                
                self._captured_key = kstr
                self._captured_display = kstr if kstr else "None captured"
                self.captured_label.setText(f"<b>Captured:</b> {self._captured_display}")
                self._awaiting_key = False
                self.capture_btn.setText("Click then Press Key")
                self.releaseKeyboard()
            else:
                super().keyPressEvent(event)
        except Exception as e:
            logging.error(f"Error in keyPressEvent: {e}")
            self._awaiting_key = False
            self.capture_btn.setText("Click then Press Key")
            try: self.releaseKeyboard()
            except: pass

    def accept_step(self):
        try:
            if not self._captured_key:
                QMessageBox.warning(self, "No Key", "Please capture a key first!")
                return
            
            note = self.note_edit.text()
            delay = self.delay_spin.value()
            param_key = "hotkey" if self.action == "Hotkey" else "key"
            
            new_step = Step(self.action, {param_key: self._captured_key}, delay, note)
            self.step_confirmed.emit(new_step)
            self.accept()
        except Exception as e:
            logging.error(f"Error accepting KeyPressDialog: {e}")

    def closeEvent(self, event):
        """Ensure keyboard is released if dialog is closed."""
        try:
            self.releaseKeyboard()
        except:
            pass
        super().closeEvent(event)

class CoordsOverlay(QDialog):
    closed = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(180, 60)
        self.move(QPoint(100, 100))
        self.setWindowTitle("Coords Overlay")
        self.label = QLabel(self)
        self.label.setFont(QFont("Consolas", 16, QFont.Weight.Bold))
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setGeometry(0, 0, 180, 60)
        self._dragging = False
        self._offset = QPoint(0, 0)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update_coords)
        self._timer.start(40)

    def update_coords(self):
        try:
            if pyautogui:
                x, y = pyautogui.position()
            else:
                pos = QCursor.pos()
                x, y = pos.x(), pos.y()
            self.label.setText(f"X: {x}\nY: {y}")
            self.label.setStyleSheet("color: #fff; background: rgba(44,62,80,0.85); border-radius: 12px; font-size: 18px;")
        except Exception as e:
            logging.error(f"Error updating coordinates: {e}")
            self.label.setText("Error\nGetting\nCoords")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._offset = event.pos()
        elif event.button() == Qt.MouseButton.RightButton:
            self._dragging = False
            self.hide()
            self.closed.emit()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            self.move(self.pos() + event.pos() - self._offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
        super().mouseReleaseEvent(event)

    def closeEvent(self, event):
        self._timer.stop()
        self.closed.emit()
        event.accept()

class MainWindow(QMainWindow):
    status_update = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        try:
            self.steps: List[Step] = []
            self.filename = None
            self.running = False
            self.paused = False
            self.abort_flag = threading.Event()
            self.overlay = None
            
            self.start_animation = None
            self.stop_animation = None
            self.emergency_stop_timer = QTimer()
            self.emergency_stop_timer.timeout.connect(self.check_emergency_stop)
            self.emergency_stop_timer.start(100)
            self.emergency_stop_active = False
            
            logging.info("MainWindow initialized")
            self.init_ui()
            
            self.status_update.connect(self.set_status)
            self.update_window_title()
            logging.info("Application started.")
        except Exception as e:
            logging.error(f"Failed to initialize MainWindow: {e}")
            raise

    def init_ui(self):
        self.init_menu_bar()
        main_widget = QWidget()
        main_vbox = QVBoxLayout(main_widget)
        main_vbox.setContentsMargins(2, 2, 2, 2)
        main_vbox.setSpacing(4)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)

        seq_frame = QFrame()
        seq_frame.setFrameShape(QFrame.Shape.Box)
        seq_vbox = QVBoxLayout(seq_frame)
        seq_label = QLabel("<b>Sequence Editor</b>")
        seq_label.setStyleSheet("font-size: 18px; margin: 8px 0;")
        seq_vbox.addWidget(seq_label)
        self.sequence_list = QListWidget()
        self.sequence_list.setStyleSheet("background: #fff; font-size: 13px; padding: 5px;")
        self.sequence_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.sequence_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.sequence_list.model().rowsMoved.connect(self.sync_steps_from_ui)
        self.sequence_list.itemDoubleClicked.connect(self.edit_step)
        seq_vbox.addWidget(self.sequence_list, 1)
        splitter.addWidget(seq_frame)
        splitter.setStretchFactor(0, 3)

        tools_frame = QFrame()
        tools_vbox = QVBoxLayout(tools_frame)
        tools_vbox.setContentsMargins(8, 12, 8, 8)

        add_label = QLabel("<b>Add Step</b>")
        add_label.setStyleSheet("font-size: 16px; margin-bottom: 8px;")
        tools_vbox.addWidget(add_label)
        
        add_grid = QGridLayout()
        add_grid.setSpacing(6)
        
        add_steps = [
            ("Key Press", "#27ae60", "#218c53", "#145d32"),
            ("Type Text", "#27ae60", "#218c53", "#145d32"),
            ("Mouse Click", "#2980b9", "#20609b", "#133864"),
            ("Mouse Move", "#2980b9", "#20609b", "#133864"),
            ("Pause", "#17a589", "#12705e", "#0e4a3d"),
            ("Key Down", "#f39c12", "#b9770e", "#874e04"),
            ("Key Up", "#f39c12", "#b9770e", "#874e04"),
            ("Hotkey", "#e74c3c", "#cb4335", "#922b21"),
            ("Image Click", "#8e44ad", "#6c3483", "#44225a"),
            ("Wait Image", "#8e44ad", "#6c3483", "#44225a"),
            ("Mouse Drag", "#2980b9", "#20609b", "#133864"),
            ("Mouse Scroll", "#2980b9", "#20609b", "#133864"),
            ("Take Screenshot", "#8e44ad", "#6c3483", "#44225a"),
            ("Run Command", "#34495e", "#2c3e50", "#1a252f"),
            ("Clipboard", "#34495e", "#2c3e50", "#1a252f"),
            ("Type Clipboard", "#34495e", "#2c3e50", "#1a252f"),
            ("Python Code", "#d35400", "#a04000", "#78281f"),
            ("System Beep", "#f39c12", "#b9770e", "#874e04")
        ]
        
        row, col = 0, 0
        for action, base, hover, pressed in add_steps:
            btn = StyledButton(f"+ {action}", base, hover, pressed)
            btn.clicked.connect(lambda checked, a=action: self.open_step_dialog(a))
            add_grid.addWidget(btn, row, col)
            col += 1
            if col > 1:
                col = 0
                row += 1
                
        tools_vbox.addLayout(add_grid)

        tools_vbox.addSpacing(18)
        manage_label = QLabel("<b>Step Management</b>")
        manage_label.setStyleSheet("font-size: 15px; margin-top: 10px;")
        tools_vbox.addWidget(manage_label)
        mgmt = [
            ("Edit Step", self.edit_step, "#bdc3c7", "#979a9a", "#616a6b"),
            ("Duplicate Step", self.duplicate_step, "#bdc3c7", "#979a9a", "#616a6b"),
            ("Remove Step", self.remove_step, "#bdc3c7", "#979a9a", "#616a6b")
        ]
        for text, handler, base, hover, pressed in mgmt:
            btn = StyledButton(text, base, hover, pressed)
            btn.clicked.connect(handler)
            tools_vbox.addWidget(btn)
        tools_vbox.addStretch(1)
        splitter.addWidget(tools_frame)
        splitter.setStretchFactor(1, 1)
        main_vbox.addWidget(splitter, 1)

        bottom_panel = QFrame()
        bottom_panel.setFrameShape(QFrame.Shape.Panel)
        bottom_panel.setStyleSheet("QFrame { background: #f3f3f3; border-top: 1px solid #ccc; }")
        bottom_hbox = QHBoxLayout(bottom_panel)
        bottom_hbox.setContentsMargins(10, 4, 10, 4)
        
        # Use Qt's Fusion style for QSpinBox to ensure vertical increment arrows across all OS
        fusion_style = QStyleFactory.create('Fusion')

        delay_label = QLabel("Start Delay (s):")
        delay_label.setStyleSheet("font-size: 13px;")
        self.start_delay_spin = QSpinBox()
        self.start_delay_spin.setStyle(fusion_style)
        self.start_delay_spin.setRange(0, 3600)
        self.start_delay_spin.setFixedWidth(80)
        self.start_delay_spin.setStyleSheet("font-size: 13px; background: #fff;")
        bottom_hbox.addWidget(delay_label)
        bottom_hbox.addWidget(self.start_delay_spin)

        self.reverse_checkbox = QCheckBox("Run in Reverse")
        self.reverse_checkbox.setStyleSheet("""
            QCheckBox:checked {
                color: #27ae60;
                font-weight: bold;
            }
        """)
        bottom_hbox.addWidget(self.reverse_checkbox)
        bottom_hbox.addSpacing(12)

        loop_label = QLabel("Loop Times:")
        loop_label.setStyleSheet("font-size: 13px;")
        self.loop_times_spin = QSpinBox()
        self.loop_times_spin.setStyle(fusion_style)
        self.loop_times_spin.setRange(0, 1000000)
        self.loop_times_spin.setFixedWidth(80)
        self.loop_times_spin.setStyleSheet("font-size: 13px; background: #fff;")
        loop_hint = QLabel("(0 = infinite)")
        loop_hint.setStyleSheet("font-size: 11px; color: #888;")
        bottom_hbox.addWidget(loop_label)
        bottom_hbox.addWidget(self.loop_times_spin)
        bottom_hbox.addWidget(loop_hint)
        bottom_hbox.addSpacing(12)

        lock_label = QLabel("Lock after (sec):")
        lock_label.setStyleSheet("font-size: 13px;")
        self.lock_after_spin = QSpinBox()
        self.lock_after_spin.setStyle(fusion_style)
        self.lock_after_spin.setRange(0, 3600)
        self.lock_after_spin.setFixedWidth(80)
        self.lock_after_spin.setStyleSheet("font-size: 13px; background: #fff;")
        bottom_hbox.addWidget(lock_label)
        bottom_hbox.addWidget(self.lock_after_spin)
        bottom_hbox.addSpacing(12)

        self.start_btn = AnimatedButton("Start", "#27ae60", "#218c53", "#145d32")
        self.start_btn.setFixedHeight(36)
        self.start_btn.setMinimumWidth(110)
        self.start_btn.clicked.connect(self.start_sequence)
        bottom_hbox.addWidget(self.start_btn)
        
        self.stop_btn = AnimatedButton("Stop", "#c0392b", "#922b21", "#6e2c00")
        self.stop_btn.setFixedHeight(36)
        self.stop_btn.setMinimumWidth(110)
        self.stop_btn.clicked.connect(self.stop_sequence)
        self.stop_btn.setEnabled(False)
        bottom_hbox.addWidget(self.stop_btn)
        
        save_btn = StyledButton("Save to DB", "#27ae60", "#218c53", "#145d32")
        save_btn.setFixedHeight(36)
        save_btn.setMinimumWidth(110)
        save_btn.clicked.connect(self.save_sequence)
        bottom_hbox.addWidget(save_btn)
        bottom_hbox.addStretch(1)
        
        self.coords_btn = StyledButton("Coords", "#229954", "#196f3d", "#145a32")
        self.coords_btn.setMinimumWidth(90)
        self.coords_btn.clicked.connect(self.toggle_coords_overlay)
        bottom_hbox.addWidget(self.coords_btn)
        
        main_vbox.addWidget(bottom_panel)
        self.setCentralWidget(main_widget)
        
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        logging.info("UI initialization completed")

    def init_menu_bar(self):
        menubar = QMenuBar(self)
        
        # File Menu
        file_menu = QMenu("File", self)
        new_action = file_menu.addAction("New")
        new_action.triggered.connect(self.file_new)
        open_action = file_menu.addAction("Open...")
        open_action.triggered.connect(self.file_open)
        save_action = file_menu.addAction("Save")
        save_action.triggered.connect(self.save_sequence)
        saveas_action = file_menu.addAction("Save As...")
        saveas_action.triggered.connect(self.save_sequence_as)
        menubar.addMenu(file_menu)
        
        # Help Menu
        help_menu = QMenu("Help", self)
        docs_action = help_menu.addAction("Documentation / Guide")
        docs_action.triggered.connect(self.show_help_dialog)
        menubar.addMenu(help_menu)
        
        self.setMenuBar(menubar)

    def show_help_dialog(self):
        """Displays a comprehensive help and documentation dialog."""
        dlg = QDialog(self)
        dlg.setWindowTitle("PyCHS Automation Builder - Documentation")
        dlg.setMinimumSize(700, 600)
        
        layout = QVBoxLayout(dlg)
        
        text_browser = QTextEdit()
        text_browser.setReadOnly(True)
        html_content = """
        <style>
            h2 { color: #2e7d32; border-bottom: 2px solid #2e7d32; padding-bottom: 5px; }
            h3 { color: #1565c0; margin-top: 15px; }
            h4 { color: #d84315; margin-bottom: 5px; }
            li { margin-bottom: 8px; }
            code { background: #f1f8e9; color: #2e7d32; padding: 2px 4px; border-radius: 4px; font-family: 'Consolas', monospace; font-weight: bold; }
            .tip { background: #e3f2fd; border-left: 4px solid #2196f3; padding: 12px; margin: 10px 0; border-radius: 0 4px 4px 0; }
            .warning { background: #fff3e0; border-left: 4px solid #ff9800; padding: 12px; margin: 10px 0; border-radius: 0 4px 4px 0; }
            .version-tag { color: #fff; background: #2e7d32; padding: 2px 8px; border-radius: 12px; font-size: 10px; font-weight: bold; }
        </style>
        <h2>🚀 Automation Builder <span class="version-tag">v6.0 STABLE</span></h2>
        <p>A high-performance visual automation engine for Windows. Construct complex workflows using a blend of basic inputs and advanced computer vision.</p>
        
        <h3>📂 **Getting Started**</h3>
        <ul>
            <li><b>Add Actions:</b> Click any button in the right-hand panel to insert a new step into your sequence.</li>
            <li><b>Edit & Refine:</b> Double-click any step in the list to fine-tune its coordinates, delays, or parameters.</li>
            <li><b>Drag & Drop:</b> Reorder your automation by dragging steps directly within the list.</li>
        </ul>

        <div class="tip">
            <b>📍 Point & Click:</b> Use the <b>"Coords"</b> overlay to find exact screen coordinates. The overlay is draggable; right-click it anytime to dismiss.
        </div>

        <h3>🛠️ **The V6 Toolkit**</h3>
        <ul>
            <li><h4>⌨️ Standard Input</h4>
                <ul>
                    <li><b>Type Text:</b> Injects text strings instantly. Useful for bulk data entry.</li>
                    <li><b>Hotkeys:</b> Full support for multi-key combos (e.g., <code>Ctrl+Alt+Delete</code>).</li>
                    <li><b>Hold States:</b> Use "Key Down" and "Key Up" to simulate sustained key presses.</li>
                </ul>
            </li>
            <li><h4>🖼️ Intelligent Vision</h4>
                <ul>
                    <li><b>Image Click:</b> Scans the screen for a specific image and clicks it relative to its position.</li>
                    <li><b>Wait Image:</b> Blocks execution until a specific UI element (like a button or modal) appears.</li>
                    <li><b>Confidence:</b> Adjust the match percentage to handle slight variants in UI rendering or anti-aliasing.</li>
                </ul>
            </li>
            <li><h4>🐍 Advanced Logic</h4>
                <ul>
                    <li><b>Python Snippets:</b> Write inline code for logic that isn't possible with static steps.
                        <br><code># Example: if os.path.exists('data.txt'): pyautogui.press('enter')</code></li>
                    <li><b>System Commands:</b> Launch external apps (e.g., <code>notepad.exe</code>) as part of your flow.</li>
                </ul>
            </li>
        </ul>

        <div class="warning">
            <b>🛡️ Emergency Stop (F12):</b>
            If the automation goes astray, press <b>F12</b> immediately. The application also includes <b>Fail-Safe</b>: move your mouse to any corner of the screen to hard-abort.
        </div>

        <p style='color: #7f8c8d; font-size: 11px; text-align: center; margin-top: 30px;'>
            Developed by PyCHS · Version 6.0 Stable Release Build · 2026 Edition
        </p>
        """
        text_browser.setHtml(html_content)
        layout.addWidget(text_browser)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = StyledButton("Got it!", "#2e7d32", "#1b5e20", "#1b5e20")
        close_btn.setFixedWidth(120)
        close_btn.clicked.connect(dlg.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        dlg.exec()

    def check_emergency_stop(self):
        try:
            if pyautogui:
                import keyboard
                if keyboard.is_pressed('f12'):
                    if not self.emergency_stop_active and self.running:
                        self.emergency_stop_active = True
                        logging.warning("Emergency stop activated via F12 hotkey!")
                        self.emergency_stop()
                        QTimer.singleShot(500, self.reset_emergency_stop)
        except ImportError:
            pass
        except Exception:
            pass

    def reset_emergency_stop(self):
        self.emergency_stop_active = False

    def emergency_stop(self):
        if self.running:
            logging.critical("EMERGENCY STOP TRIGGERED!")
            self.stop_sequence()
            self.status_update.emit("🛑 EMERGENCY STOP!")
            if hasattr(self.stop_btn, 'start_pulse_animation'):
                self.stop_btn.start_pulse_animation("#ff0000")
                QTimer.singleShot(2000, self.stop_btn.stop_animation)
                
    def keyPressEvent(self, event):
        try:
            if event.key() == Qt.Key.Key_F12:
                if self.running and not self.emergency_stop_active:
                    self.emergency_stop_active = True
                    self.emergency_stop()
                    QTimer.singleShot(500, self.reset_emergency_stop)
                event.accept()
                return
            super().keyPressEvent(event)
        except Exception as e:
            logging.error(f"Error in keyPressEvent: {e}")
            super().keyPressEvent(event)

    def update_window_title(self):
        name = self.filename if self.filename else "untitled_sequence.json"
        self.setWindowTitle(f"{name} - PyCHS Automation Builder - v6.0 Stable")

    def file_new(self):
        try:
            if self.steps and not self.confirm_discard_changes():
                return
            self.steps = []
            self.filename = None
            self.refresh_steps()
            self.update_window_title()
        except Exception as e:
            logging.error(f"Error creating new file: {e}")
            QMessageBox.critical(self, "Error", f"Failed to create new file: {e}")

    def file_open(self):
        try:
            fname, _ = QFileDialog.getOpenFileName(self, "Open Automation Sequence", "", "JSON Files (*.json)")
            if fname:
                with open(fname, "r", encoding='utf-8') as f:
                    data = json.load(f)
                self.steps = [Step.from_dict(s) for s in data]
                self.filename = os.path.basename(fname)
                self.refresh_steps()
                self.update_window_title()
        except Exception as e:
            logging.error(f"Failed to open sequence file: {e}")
            QMessageBox.critical(self, "Open Error", f"Failed to open sequence:\n{e}")

    def save_sequence(self):
        try:
            if not self.filename:
                return self.save_sequence_as()
            with open(self.filename, "w", encoding='utf-8') as f:
                json.dump([s.to_dict() for s in self.steps], f, indent=2)
            self.status_update.emit(f"Saved {self.filename}")
            self.update_window_title()
        except Exception as e:
            logging.error(f"Failed to save sequence: {e}")
            QMessageBox.critical(self, "Save Error", f"Failed to save:\n{e}")

    def save_sequence_as(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Save Sequence", "untitled_sequence.json", "JSON Files (*.json)")
        if fname:
            if not fname.endswith(".json"): fname += ".json"
            self.filename = fname
            self.save_sequence()

    def confirm_discard_changes(self):
        return QMessageBox.question(self, "Discard Changes?", "Discard current sequence?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def open_step_dialog(self, action: str, existing_step: Step = None, edit_index: int = -1):
        try:
            if action in ["Key Press", "Key Down", "Key Up", "Hotkey"]:
                dlg = KeyPressDialog(action, existing_step, self)
            else:
                dlg = UnifiedStepDialog(action, existing_step, self)
            
            def on_confirm(new_step):
                if edit_index >= 0:
                    self.steps[edit_index] = new_step
                else:
                    self.steps.append(new_step)
                self.refresh_steps()

            dlg.step_confirmed.connect(on_confirm)
            dlg.exec()
        except Exception as e:
            logging.error(f"Failed to open step dialog for {action}: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open dialog:\n{e}")

    def edit_step(self):
        idx = self.sequence_list.currentRow()
        if idx == -1 or idx >= len(self.steps):
            return
        step = self.steps[idx]
        self.open_step_dialog(step.action, existing_step=step, edit_index=idx)

    def duplicate_step(self):
        idx = self.sequence_list.currentRow()
        if idx == -1 or idx >= len(self.steps):
            return
        step = self.steps[idx]
        self.steps.insert(idx + 1, Step(step.action, step.params.copy(), step.delay, step.note))
        self.refresh_steps()

    def remove_step(self):
        idx = self.sequence_list.currentRow()
        if idx == -1 or idx >= len(self.steps):
            return
        del self.steps[idx]
        self.refresh_steps()

    def sync_steps_from_ui(self, *args):
        new_steps = []
        for i in range(self.sequence_list.count()):
            step = self.sequence_list.item(i).data(Qt.ItemDataRole.UserRole)
            if step: new_steps.append(step)
        self.steps = new_steps
        logging.debug("Reordered steps via UI Drag & Drop")

    def refresh_steps(self):
        try:
            self.sequence_list.clear()
            for i, step in enumerate(self.steps):
                item = QListWidgetItem(step.__str__())
                item.setData(Qt.ItemDataRole.UserRole, step)
                self.sequence_list.addItem(item)
        except Exception as e:
            logging.error(f"Failed to refresh steps: {e}")

    def toggle_coords_overlay(self):
        if self.overlay and self.overlay.isVisible():
            self.overlay.hide()
            self.overlay = None
            self.coords_btn.setText("Coords")
            return
        self.overlay = CoordsOverlay()
        self.overlay.closed.connect(self.overlay_closed)
        self.overlay.show()
        self.coords_btn.setText("Hide Coords")

    def overlay_closed(self):
        self.coords_btn.setText("Coords")
        self.overlay = None

    def start_sequence(self):
        if not self.steps:
            QMessageBox.warning(self, "No Steps", "Add at least one step.")
            return
        self.running = True
        self.paused = False
        self.abort_flag.clear()
        
        self.start_btn.setEnabled(False)
        self.start_btn.stop_animation()
        self.start_btn.set_animated_text("Running...")
        
        self.stop_btn.setEnabled(True)
        self.stop_btn.start_pulse_animation("#ff6b6b")
        self.stop_btn.set_animated_text("🛑 STOP")
        
        t = threading.Thread(target=self.run_sequence, daemon=True)
        t.start()

    def stop_sequence(self):
        self.running = False
        self.abort_flag.set()
        QTimer.singleShot(0, self._reset_ui_state)

    def interruptible_sleep(self, duration: float) -> bool:
        if duration <= 0: return True
        end_time = time.time() + duration
        while time.time() < end_time:
            if not self.running or self.abort_flag.is_set():
                return False
            time.sleep(0.05)
        return True

    def run_sequence(self):
        try:
            delay = self.start_delay_spin.value()
            loop_times = self.loop_times_spin.value()
            lock_delay = self.lock_after_spin.value()
            reverse = self.reverse_checkbox.isChecked()
            
            # Deepcopy sequence logic to prevent user mutations during runtime
            steps_snapshot = copy.deepcopy(self.steps)
            
            if delay > 0:
                for i in range(delay, 0, -1):
                    if not self.running or self.abort_flag.is_set(): return
                    self.status_update.emit(f"Starting in {i}s...")
                    time.sleep(1)
            
            loops_done = 0
            total_steps_executed = 0
            
            while self.running and not self.abort_flag.is_set():
                try:
                    current_steps = list(steps_snapshot)
                    if not current_steps: break
                    if reverse: current_steps = current_steps[::-1]
                    
                    for i, step in enumerate(current_steps):
                        if not self.running or self.abort_flag.is_set(): return
                        
                        step_num = i + 1
                        self.status_update.emit(f"Running step {step_num}/{len(current_steps)}: {step.action}")
                        
                        try:
                            self.execute_step(step)
                            total_steps_executed += 1
                            if step.delay > 0:
                                if not self.interruptible_sleep(step.delay): return
                        except Exception as step_error:
                            logging.error(f"Failed to execute step {step_num}: {step_error}")
                            continue
                    
                    loops_done += 1
                    if loop_times > 0 and loops_done >= loop_times: break
                        
                except Exception as loop_error:
                    logging.error(f"Error in execution loop {loops_done + 1}: {loop_error}")
                    loops_done += 1
                    if loops_done >= 100: break
            
            self.status_update.emit("Done.")
            
            if lock_delay > 0 and self.running:
                try:
                    self.status_update.emit(f"Locking in {lock_delay}s...")
                    if self.interruptible_sleep(lock_delay): lock_workstation()
                except Exception as lock_error:
                    logging.error(f"Error during workstation lock: {lock_error}")
                    
        except Exception as e:
            logging.error(f"Critical error in sequence execution: {e}")
            self.status_update.emit("Error occurred")
        finally:
            try:
                self.running = False
                QTimer.singleShot(0, self._reset_ui_state)
            except Exception as cleanup_error:
                logging.error(f"Error during cleanup: {cleanup_error}")

    def set_status(self, msg):
        try:
            self.statusBar().showMessage(msg)
        except Exception as e:
            logging.error(f"Failed to set status: {e}")

    def _reset_ui_state(self):
        try:
            if hasattr(self.start_btn, 'stop_animation'):
                self.start_btn.stop_animation()
                self.start_btn.set_animated_text("Start")
                self.start_btn.setEnabled(True)
            if hasattr(self.stop_btn, 'stop_animation'):
                self.stop_btn.stop_animation()
                self.stop_btn.set_animated_text("Stop")
                self.stop_btn.setEnabled(False)
        except Exception as e:
            logging.error(f"Error resetting UI: {e}")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)

    def execute_step(self, step: Step):
        original_failsafe = None
        def sanitize_key(k_str):
            if not k_str: return ""
            k_str = k_str.lower().strip()
            mapping = {'return': 'enter', 'pgup': 'pageup', 'pgdown': 'pagedown', 'del': 'delete', 'ins': 'insert', 'esc': 'escape', 'meta': 'win'}
            return mapping.get(k_str, k_str)

        try:
            if not pyautogui:
                time.sleep(0.5)
                return
            
            p = step.params
            
            original_failsafe = pyautogui.FAILSAFE
            pyautogui.FAILSAFE = False
            
            if step.action == "Key Press":
                key = sanitize_key(p.get("key", ""))
                if not key: raise ValueError("Key empty")
                pyautogui.press(key)
                
            elif step.action == "Type Text":
                text = p.get("text", "")
                if text is None: text = ""
                pyautogui.write(text)
                
            elif step.action == "Mouse Click":
                pyautogui.click(p["x"], p["y"], button=p.get("button", "left"))
                
            elif step.action == "Mouse Move":
                pyautogui.moveTo(p["x"], p["y"])
                
            elif step.action == "Pause":
                self.interruptible_sleep(p.get("seconds", 1))
                
            elif step.action == "Key Down":
                key = sanitize_key(p.get("key", ""))
                if not key: raise ValueError("Key empty")
                pyautogui.keyDown(key)
                
            elif step.action == "Key Up":
                key = sanitize_key(p.get("key", ""))
                if not key: raise ValueError("Key empty")
                pyautogui.keyUp(key)
                
            elif step.action == "Image Click":
                image_path = p.get("path", "")
                confidence = p.get("confidence", 0.9)
                if image_path and os.path.exists(image_path):
                    try:
                        try:
                            boxes = list(pyautogui.locateAllOnScreen(image_path, confidence=confidence))
                        except NotImplementedError:
                            logging.warning("OpenCV not installed. Match confidence will be ignored.")
                            boxes = list(pyautogui.locateAllOnScreen(image_path))
                            
                        if not boxes:
                            raise ImageNotFoundException()
                        
                        instance_pref = p.get("instance", "first")
                        if instance_pref == "last": box = boxes[-1]
                        elif instance_pref == "top": box = min(boxes, key=lambda b: b.top)
                        elif instance_pref == "bottom": box = max(boxes, key=lambda b: b.top)
                        elif instance_pref == "left": box = min(boxes, key=lambda b: b.left)
                        elif instance_pref == "right": box = max(boxes, key=lambda b: b.left)
                        elif instance_pref == "center":
                            sw, sh = pyautogui.size()
                            cx_screen, cy_screen = sw / 2, sh / 2
                            box = min(boxes, key=lambda b: ((b.left + b.width/2) - cx_screen)**2 + ((b.top + b.height/2) - cy_screen)**2)
                        else: box = boxes[0] 

                        target_pref = p.get("target", "center")
                        x, y, w, h = box.left, box.top, box.width, box.height
                        
                        if target_pref == "top-left": cx, cy = x, y
                        elif target_pref == "top-right": cx, cy = x + w, y
                        elif target_pref == "bottom-left": cx, cy = x, y + h
                        elif target_pref == "bottom-right": cx, cy = x + w, y + h
                        elif target_pref == "top-center": cx, cy = x + w/2, y
                        elif target_pref == "bottom-center": cx, cy = x + w/2, y + h
                        elif target_pref == "left-center": cx, cy = x, y + h/2
                        elif target_pref == "right-center": cx, cy = x + w, y + h/2
                        else: cx, cy = x + w/2, y + h/2 

                        pyautogui.click(cx, cy)
                        logging.debug(f"Successfully clicked image {image_path} at ({cx}, {cy})")
                    except ImageNotFoundException:
                        logging.warning(f"Image not found on screen: {image_path}")
                    except Exception as img_e:
                        logging.error(f"Image click failed: {img_e}")
                else:
                    self.interruptible_sleep(0.5)

            elif step.action == "Wait Image":
                image_path = p.get("path", "")
                timeout = p.get("timeout", 10.0)
                confidence = p.get("confidence", 0.9)
                if image_path and os.path.exists(image_path):
                    start_time = time.time()
                    found = False
                    while time.time() - start_time < timeout:
                        if not self.running or self.abort_flag.is_set(): return
                        try:
                            try:
                                if pyautogui.locateOnScreen(image_path, confidence=confidence):
                                    found = True
                                    break
                            except NotImplementedError:
                                if pyautogui.locateOnScreen(image_path):
                                    found = True
                                    break
                        except ImageNotFoundException:
                            pass
                        time.sleep(0.5)
                    if not found:
                        raise TimeoutError(f"Image not found within {timeout}s: {image_path}")
                else:
                    raise FileNotFoundError(f"Image file missing: {image_path}")
                    
            elif step.action == "Take Screenshot":
                path = p.get("path", "screenshot.png")
                base, ext = os.path.splitext(path)
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                actual_path = f"{base}_{timestamp}{ext}"
                pyautogui.screenshot(actual_path)
                logging.debug(f"Saved screenshot to {actual_path}")

            elif step.action == "Mouse Drag":
                pyautogui.dragTo(p["x"], p["y"], p.get("duration", 0.5), button=p.get("button", "left"))
                
            elif step.action == "Mouse Scroll":
                pyautogui.scroll(p.get("clicks", 0))
                
            elif step.action == "Run Command":
                subprocess.Popen(p.get("command", ""), shell=True)

            elif step.action == "Python Code":
                code = p.get("code", "")
                logging.debug(f"Executing Python snippet: \n{code}")
                local_ctx = {"pyautogui": pyautogui, "time": time, "os": os, "step": step}
                exec(code, globals(), local_ctx)

            elif step.action == "Clipboard":
                if pyperclip:
                    text = p.get("text", "")
                    pyperclip.copy(text)
                    logging.debug("Set clipboard text")
                else:
                    logging.error("pyperclip not installed. Cannot set clipboard.")
                
            elif step.action == "Type Clipboard":
                if pyperclip:
                    text = pyperclip.paste()
                    pyautogui.write(text)
                    logging.debug("Typed clipboard text")
                else:
                    logging.error("pyperclip not installed. Cannot type clipboard.")

            elif step.action == "System Beep":
                if sys.platform == "win32":
                    import winsound
                    winsound.MessageBeep()
                else:
                    sys.stdout.write('\a')
                    sys.stdout.flush()
                logging.debug("System beep")

            elif step.action == "Hotkey":
                hotkey_str = p.get("hotkey", "")
                if not hotkey_str: raise ValueError("Hotkey empty")
                keys = [sanitize_key(k) for k in hotkey_str.split("+") if k.strip()]
                if not keys: raise ValueError(f"Invalid hotkey: {hotkey_str}")
                pyautogui.hotkey(*keys)
                
        except pyautogui.FailSafeException:
            logging.error("Fail-safe triggered")
            QTimer.singleShot(0, self.stop_sequence)
        except Exception as e:
            logging.error(f"Error executing step '{step.action}': {e}")
        finally:
            try:
                if original_failsafe is not None:
                    pyautogui.FAILSAFE = original_failsafe
            except: pass

if __name__ == "__main__":
    try:
        logging.info("Starting Automation Application")
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except: pass  
        
        app = QApplication(sys.argv)
        app.setApplicationName("PyCHS Automation Builder")
        app.setApplicationVersion("6.0 Stable")
        app.setOrganizationName("PyCHS")
        
        win = MainWindow()
        win.show()
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"Critical error: {e}")
        try:
            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, "Startup Error", f"Failed to start:\n{e}")
        except: pass
        sys.exit(1)
