import sys
import os
import time
import random
import logging
import traceback
import pyautogui
from pynput import keyboard
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFileDialog, 
                             QSpinBox, QDoubleSpinBox, QTextEdit, QGroupBox, 
                             QMessageBox, QComboBox, QCheckBox, QGridLayout)
from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot

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

# Enable PyAutoGUI Fail-Safe (Moving mouse to any corner of the screen aborts the script)
pyautogui.FAILSAFE = True

# ==========================================
# 2. Automation Worker Thread
# ==========================================
class AutomationWorker(QThread):
    log_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.is_running = True
        self.screen_width, self.screen_height = pyautogui.size()

    def apply_randomization(self, base_delay):
        """Applies a +/- 20% random variance if humanize is enabled."""
        if self.config['humanize']:
            variance = base_delay * 0.20
            return random.uniform(base_delay - variance, base_delay + variance)
        return base_delay

    def perform_action(self, x, y, action_type):
        """Validates coordinates and performs the requested mouse action."""
        # Error Handling: Screen Bounds Check
        if not (0 <= x < self.screen_width and 0 <= y < self.screen_height):
            raise ValueError(f"Calculated coordinates ({x}, {y}) are outside screen bounds!")

        if action_type == 'Left Click':
            pyautogui.click(x, y)
        elif action_type == 'Right Click':
            pyautogui.click(x, y, button='right')
        elif action_type == 'Double Click':
            pyautogui.doubleClick(x, y)
        elif action_type == 'Hover':
            pyautogui.moveTo(x, y, duration=0.2)
        else:
            self.log_signal.emit(f"Unknown action: {action_type}. Defaulting to Hover.")
            pyautogui.moveTo(x, y)

    def run(self):
        try:
            initial_delay = self.config['initial_delay']
            if initial_delay > 0:
                self.log_signal.emit(f"Starting in {initial_delay} seconds. Switch to your target window now!")
                time.sleep(initial_delay)

            self.log_signal.emit("Automation actively running... (Fail-Safe: Move mouse to any screen corner to abort)")
            cycle_count = 1
            
            while self.is_running:
                if self.config['max_cycles'] > 0 and cycle_count > self.config['max_cycles']:
                    self.log_signal.emit(f"Maximum cycles ({self.config['max_cycles']}) reached. Stopping.")
                    break

                self.log_signal.emit(f"--- Starting Cycle {cycle_count} ---")
                
                # --- STEP 1: Process Image 1 ---
                self.log_signal.emit("Searching for Image 1...")
                img1_found = False
                search_start_time = time.time()
                
                while self.is_running and not img1_found:
                    if time.time() - search_start_time > self.config['search_timeout']:
                        self.log_signal.emit(f"Timeout: Image 1 not found after {self.config['search_timeout']}s. Restarting cycle.")
                        break 

                    try:
                        matches = list(pyautogui.locateAllOnScreen(self.config['img1_path'], confidence=self.config['confidence']))
                        if matches:
                            matches.sort(key=lambda box: box.top)
                            top_match = matches[0]
                            center_x, center_y = pyautogui.center(top_match)
                            
                            # Apply Offsets
                            target_x = center_x + self.config['img1_offset_x']
                            target_y = center_y + self.config['img1_offset_y']
                            
                            self.log_signal.emit(f"Image 1 found. Applying '{self.config['img1_action']}' at ({target_x}, {target_y}).")
                            self.perform_action(target_x, target_y, self.config['img1_action'])
                            img1_found = True
                        else:
                            time.sleep(0.5) 
                    except pyautogui.ImageNotFoundException:
                        time.sleep(0.5)
                    except ValueError as ve:
                        self.error_signal.emit(str(ve))
                        break # Skip this image if out of bounds
                        
                if not self.is_running: break
                
                if not img1_found:
                    time.sleep(self.apply_randomization(self.config['cycle_delay']))
                    continue

                # Wait before finding Image 2
                time.sleep(self.apply_randomization(self.config['click_delay']))

                # --- STEP 2: Process Image 2 ---
                self.log_signal.emit("Searching for Image 2...")
                img2_found = False
                search_start_time = time.time()
                
                while self.is_running and not img2_found:
                    if time.time() - search_start_time > self.config['search_timeout']:
                        self.log_signal.emit(f"Timeout: Image 2 not found after {self.config['search_timeout']}s. Restarting cycle.")
                        break

                    try:
                        match2 = pyautogui.locateOnScreen(self.config['img2_path'], confidence=self.config['confidence'])
                        if match2:
                            center_x, center_y = pyautogui.center(match2)
                            
                            # Apply Offsets
                            target_x = center_x + self.config['img2_offset_x']
                            target_y = center_y + self.config['img2_offset_y']
                            
                            self.log_signal.emit(f"Image 2 found. Applying '{self.config['img2_action']}' at ({target_x}, {target_y}).")
                            self.perform_action(target_x, target_y, self.config['img2_action'])
                            img2_found = True
                        else:
                            time.sleep(0.5)
                    except pyautogui.ImageNotFoundException:
                        time.sleep(0.5)
                    except ValueError as ve:
                        self.error_signal.emit(str(ve))
                        break
                
                if not self.is_running: break
                
                cycle_delay = self.apply_randomization(self.config['cycle_delay'])
                self.log_signal.emit(f"Cycle {cycle_count} complete. Waiting {cycle_delay:.2f}s.")
                cycle_count += 1
                
                sleep_time_passed = 0
                while self.is_running and sleep_time_passed < cycle_delay:
                    time.sleep(0.1)
                    sleep_time_passed += 0.1

        except pyautogui.FailSafeException:
            # Error Handling: PyAutoGUI Fail-Safe Triggered
            self.error_signal.emit("HARDWARE FAIL-SAFE TRIGGERED: Mouse moved to corner of screen. Automation Aborted.")
        except Exception as e:
            # General Error Catching
            error_trace = traceback.format_exc()
            logger.error(f"Critical error in worker thread:\n{error_trace}")
            self.error_signal.emit(f"Critical Error: {str(e)}")
        finally:
            self.log_signal.emit("Automation stopped.")
            self.finished_signal.emit()

    def stop(self):
        self.is_running = False

# ==========================================
# 3. Main GUI Application
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced Image Automation Bot")
        self.resize(650, 750)
        
        self.worker = None
        self.hotkey_listener = None
        
        self.img1_path = ""
        self.img2_path = ""
        
        self.init_ui()
        self.setup_hotkeys()

    def init_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        # --- Image Targets Group ---
        img_group = QGroupBox("Target Configuration (Offsets & Actions)")
        img_layout = QGridLayout()
        
        # Headers
        img_layout.addWidget(QLabel("<b>Target</b>"), 0, 0)
        img_layout.addWidget(QLabel("<b>Action</b>"), 0, 1)
        img_layout.addWidget(QLabel("<b>X Offset</b>"), 0, 2)
        img_layout.addWidget(QLabel("<b>Y Offset</b>"), 0, 3)

        # Image 1 Controls
        self.btn_browse1 = QPushButton("Select Img 1")
        self.btn_browse1.clicked.connect(lambda: self.browse_image(1))
        self.cmb_action1 = QComboBox()
        self.cmb_action1.addItems(["Left Click", "Right Click", "Double Click", "Hover"])
        self.spin_x1 = QSpinBox()
        self.spin_x1.setRange(-2000, 2000)
        self.spin_y1 = QSpinBox()
        self.spin_y1.setRange(-2000, 2000)
        self.lbl_path1 = QLabel("Not selected")
        self.lbl_path1.setStyleSheet("color: gray; font-size: 10px;")

        img_layout.addWidget(self.btn_browse1, 1, 0)
        img_layout.addWidget(self.cmb_action1, 1, 1)
        img_layout.addWidget(self.spin_x1, 1, 2)
        img_layout.addWidget(self.spin_y1, 1, 3)
        img_layout.addWidget(self.lbl_path1, 2, 0, 1, 4)

        # Image 2 Controls
        self.btn_browse2 = QPushButton("Select Img 2")
        self.btn_browse2.clicked.connect(lambda: self.browse_image(2))
        self.cmb_action2 = QComboBox()
        self.cmb_action2.addItems(["Left Click", "Right Click", "Double Click", "Hover"])
        self.spin_x2 = QSpinBox()
        self.spin_x2.setRange(-2000, 2000)
        self.spin_y2 = QSpinBox()
        self.spin_y2.setRange(-2000, 2000)
        self.lbl_path2 = QLabel("Not selected")
        self.lbl_path2.setStyleSheet("color: gray; font-size: 10px;")

        img_layout.addWidget(self.btn_browse2, 3, 0)
        img_layout.addWidget(self.cmb_action2, 3, 1)
        img_layout.addWidget(self.spin_x2, 3, 2)
        img_layout.addWidget(self.spin_y2, 3, 3)
        img_layout.addWidget(self.lbl_path2, 4, 0, 1, 4)

        img_group.setLayout(img_layout)
        main_layout.addWidget(img_group)

        # --- Timing & Settings Group ---
        settings_group = QGroupBox("Timing & Behavior")
        set_layout = QGridLayout()

        set_layout.addWidget(QLabel("Init Delay (s):"), 0, 0)
        self.spin_initial_delay = QDoubleSpinBox()
        self.spin_initial_delay.setValue(3.0)
        set_layout.addWidget(self.spin_initial_delay, 0, 1)

        set_layout.addWidget(QLabel("Delay Img1->Img2 (s):"), 1, 0)
        self.spin_click_delay = QDoubleSpinBox()
        self.spin_click_delay.setValue(1.5)
        set_layout.addWidget(self.spin_click_delay, 1, 1)

        set_layout.addWidget(QLabel("Cycle Delay (s):"), 2, 0)
        self.spin_cycle_delay = QDoubleSpinBox()
        self.spin_cycle_delay.setValue(3.0)
        set_layout.addWidget(self.spin_cycle_delay, 2, 1)

        set_layout.addWidget(QLabel("Max Cycles (0=∞):"), 0, 2)
        self.spin_max_cycles = QSpinBox()
        self.spin_max_cycles.setMaximum(99999)
        set_layout.addWidget(self.spin_max_cycles, 0, 3)

        set_layout.addWidget(QLabel("Search Timeout (s):"), 1, 2)
        self.spin_timeout = QDoubleSpinBox()
        self.spin_timeout.setValue(15.0)
        set_layout.addWidget(self.spin_timeout, 1, 3)

        set_layout.addWidget(QLabel("Match Confidence:"), 2, 2)
        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(0.1, 0.99)
        self.spin_conf.setSingleStep(0.05)
        self.spin_conf.setValue(0.85)
        set_layout.addWidget(self.spin_conf, 2, 3)

        # Anti-Bot Feature
        self.chk_humanize = QCheckBox("Humanize Delays (Randomize +/- 20%)")
        self.chk_humanize.setChecked(True)
        set_layout.addWidget(self.chk_humanize, 3, 0, 1, 4)

        settings_group.setLayout(set_layout)
        main_layout.addWidget(settings_group)

        # --- Controls ---
        controls_layout = QHBoxLayout()
        self.btn_start = QPushButton("START")
        self.btn_start.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; height: 45px; font-size: 14px;")
        self.btn_start.clicked.connect(self.start_automation)
        
        self.btn_stop = QPushButton("STOP (HotKey: F9)")
        self.btn_stop.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; height: 45px; font-size: 14px;")
        self.btn_stop.clicked.connect(self.stop_automation)
        self.btn_stop.setEnabled(False)
        
        controls_layout.addWidget(self.btn_start)
        controls_layout.addWidget(self.btn_stop)
        main_layout.addLayout(controls_layout)

        # --- Logs ---
        main_layout.addWidget(QLabel("Execution Logs (Hover mouse to screen corner to emergency stop):"))
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: Consolas;")
        main_layout.addWidget(self.log_console)

        self.setCentralWidget(central_widget)

    def setup_hotkeys(self):
        def on_press(key):
            if key == keyboard.Key.f9:
                if self.worker and self.worker.is_running:
                    self.log_message("F9 pressed! Emergency stopping...")
                    self.stop_automation()

        self.hotkey_listener = keyboard.Listener(on_press=on_press)
        self.hotkey_listener.start()

    def browse_image(self, img_num):
        file_path, _ = QFileDialog.getOpenFileName(self, f"Select Image {img_num}", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            filename = os.path.basename(file_path)
            if img_num == 1:
                self.img1_path = file_path
                self.btn_browse1.setText(f"Img 1: {filename}")
                self.lbl_path1.setText(file_path)
            else:
                self.img2_path = file_path
                self.btn_browse2.setText(f"Img 2: {filename}")
                self.lbl_path2.setText(file_path)

    @pyqtSlot(str)
    def log_message(self, message):
        logger.info(message)
        self.log_console.append(message)
        scrollbar = self.log_console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @pyqtSlot(str)
    def handle_error(self, error_msg):
        logger.error(error_msg)
        self.log_console.append(f"<font color='#ff5555'><b>ERROR:</b> {error_msg}</font>")

    def validate_inputs(self):
        """Error Handling: Check files and inputs before running."""
        if not self.img1_path or not self.img2_path:
            QMessageBox.warning(self, "Missing Images", "Please select both target images.")
            return False
            
        if not os.path.exists(self.img1_path):
            QMessageBox.critical(self, "File Not Found", f"Cannot find Image 1:\n{self.img1_path}")
            return False
            
        if not os.path.exists(self.img2_path):
            QMessageBox.critical(self, "File Not Found", f"Cannot find Image 2:\n{self.img2_path}")
            return False

        return True

    def start_automation(self):
        if not self.validate_inputs():
            return

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.log_console.clear()
        
        # Package settings into a configuration dictionary
        config = {
            'img1_path': self.img1_path,
            'img1_action': self.cmb_action1.currentText(),
            'img1_offset_x': self.spin_x1.value(),
            'img1_offset_y': self.spin_y1.value(),
            
            'img2_path': self.img2_path,
            'img2_action': self.cmb_action2.currentText(),
            'img2_offset_x': self.spin_x2.value(),
            'img2_offset_y': self.spin_y2.value(),
            
            'initial_delay': self.spin_initial_delay.value(),
            'click_delay': self.spin_click_delay.value(),
            'cycle_delay': self.spin_cycle_delay.value(),
            'max_cycles': self.spin_max_cycles.value(),
            'search_timeout': self.spin_timeout.value(),
            'confidence': self.spin_conf.value(),
            'humanize': self.chk_humanize.isChecked()
        }

        self.worker = AutomationWorker(config)
        self.worker.log_signal.connect(self.log_message)
        self.worker.error_signal.connect(self.handle_error)
        self.worker.finished_signal.connect(self.on_automation_finished)
        
        self.worker.start()

    def stop_automation(self):
        if self.worker:
            self.log_message("Stop requested. Halting...")
            self.worker.stop()

    @pyqtSlot()
    def on_automation_finished(self):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        event.accept()

# ==========================================
# 4. App Execution
# ==========================================
if __name__ == '__main__':
    if hasattr(sys, 'frozen'):
        QApplication.setAttribute(pyqtSlot, True)
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion") 
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())