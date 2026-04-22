import sys
import os
import subprocess
import time
import ctypes
import random
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QSpinBox, QMessageBox, QTabWidget, 
                             QComboBox, QTimeEdit, QCheckBox, QSystemTrayIcon, QMenu, 
                             QGroupBox, QLineEdit, QFileDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTime, QTimer
from PyQt6.QtGui import QIcon, QAction
###

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

# Structure for reading exact mouse coordinates
class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

# ==========================================
# Siren & Jiggler Threads
# ==========================================
class SirenThread(QThread):
    def run(self):
        if HAS_KEYBOARD:
            for _ in range(50): keyboard.send('volume up') 
        if HAS_WINSOUND:
            for _ in range(15): 
                winsound.Beep(2500, 500)
                winsound.Beep(2000, 500)

class JigglerThread(QThread):
    def __init__(self):
        super().__init__()
        self.is_running = True

    def run(self):
        while self.is_running:
            for _ in range(60):
                if not self.is_running: return
                time.sleep(1)
            
            if not self.is_running: return
            try:
                ctypes.windll.user32.mouse_event(0x0001, 1, 1, 0, 0)
                time.sleep(0.05)
                ctypes.windll.user32.mouse_event(0x0001, -1, -1, 0, 0)
            except Exception:
                pass

    def stop(self):
        self.is_running = False

# ==========================================
# 1. Background Monitoring Thread
# ==========================================
class MonitorThread(QThread):
    tick = pyqtSignal(str)          
    warning = pyqtSignal(int)       
    execute_action = pyqtSignal()
    trigger_siren = pyqtSignal()

    def __init__(self, mode, target, action, force, extra=None):
        super().__init__()
        self.mode = mode          
        self.target = target      
        self.action = action      
        self.force = force        
        self.extra = extra        
        self.is_running = True
        self.warning_triggered = False
        
        self.cpu_overload_seconds = 0
        self.honeypot_mtime = None

    def run(self):
        if self.mode == 'honeypot' and os.path.exists(self.target):
            self.honeypot_mtime = os.path.getmtime(self.target)

        while self.is_running:
            try:
                if self.mode == 'timer': self._check_timer()
                elif self.mode == 'time': self._check_exact_time()
                elif self.mode == 'process': self._check_process()
                elif self.mode == 'network': self._check_network()
                elif self.mode == 'idle': self._check_idle()
                elif self.mode == 'usb': self._check_usb()
                elif self.mode == 'intrusion': self._check_intrusion()
                elif self.mode == 'jiggler_trap': self._check_jiggler_trap()
                elif self.mode == 'battery': self._check_battery()
                elif self.mode == 'wifi': self._check_wifi()
                elif self.mode == 'cpu': self._check_cpu()
                elif self.mode == 'quota': self._check_quota()
                elif self.mode == 'focus_kill': self._check_focus_kill()
                elif self.mode == 'vpn': self._check_vpn()
                elif self.mode == 'honeypot': self._check_honeypot()
            except Exception as e:
                self.tick.emit(f"Error: {str(e)}")
                break
            time.sleep(1) 

    def _trigger_event(self, grace_period=60, instant=False, sound_alarm=False):
        if sound_alarm:
            self.trigger_siren.emit()
            
        if instant:
            self.execute_action.emit()
            self.is_running = False
        elif not self.warning_triggered:
            self.mode = 'timer'
            self.target = time.time() + grace_period
            self.warning.emit(grace_period)
            self.warning_triggered = True

    def _check_timer(self):
        remaining = int(self.target - time.time())
        if remaining <= 0:
            self._trigger_event(instant=True)
        elif remaining <= 60 and not self.warning_triggered:
            self._trigger_event(grace_period=remaining)
        else:
            mins, secs = divmod(remaining, 60)
            hours, mins = divmod(mins, 60)
            self.tick.emit(f"Time Remaining: {hours:02d}:{mins:02d}:{secs:02d}")

    def _check_exact_time(self):
        now = datetime.now().time()
        now_td = timedelta(hours=now.hour, minutes=now.minute, seconds=now.second)
        target_td = timedelta(hours=self.target.hour, minutes=self.target.minute, seconds=self.target.second)
        diff = (target_td - now_td).total_seconds()
        if diff < 0: diff += 86400 

        if diff <= 1: self._trigger_event(instant=True)
        elif diff <= 60 and not self.warning_triggered: self._trigger_event(grace_period=int(diff))
        else: self.tick.emit(f"Target Time: {self.target.strftime('%H:%M:%S')} (in {int(diff)}s)")

    def _check_process(self):
        if not HAS_PSUTIL: return
        exists = any(p.info['name'].lower() == self.target.lower() for p in psutil.process_iter(['name']) if p.info['name'])
        if not exists:
            self.tick.emit(f"Process '{self.target}' closed. Initiating sequence...")
            self._trigger_event(grace_period=60)
        else: self.tick.emit(f"Monitoring process: '{self.target}'... (Running)")

    def _check_network(self):
        if not HAS_PSUTIL: return
        n1 = psutil.net_io_counters()
        time.sleep(2)
        n2 = psutil.net_io_counters()
        kbps = ((n2.bytes_recv - n1.bytes_recv) / 2) / 1024
        
        if kbps < self.target:
            self.tick.emit(f"Network drop detected ({kbps:.1f} KB/s). Initiating sequence...")
            self._trigger_event(grace_period=60)
        else: self.tick.emit(f"Network Speed: {kbps:.1f} KB/s (Threshold: {self.target} KB/s)")

    def _check_idle(self):
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
        idle_seconds = (ctypes.windll.kernel32.GetTickCount() - lii.dwTime) / 1000.0
        
        if idle_seconds >= self.target:
            self.tick.emit(f"Idle time exceeded {int(self.target)}s. Initiating sequence...")
            self._trigger_event(grace_period=60)
        else: self.tick.emit(f"User idle for: {int(idle_seconds)}s (Limit: {int(self.target)}s)")

    def _check_usb(self):
        if not HAS_PSUTIL: return
        drives = [p.mountpoint for p in psutil.disk_partitions()]
        if self.target not in drives:
            self.tick.emit(f"USB Key '{self.target}' disconnected! Action imminent...")
            self._trigger_event(grace_period=3)
        else: self.tick.emit(f"Monitoring USB Drive: '{self.target}'... (Connected)")

    def _check_intrusion(self):
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)

        if not hasattr(self, 'intrusion_armed'):
            self.arm_time = time.time() + self.target
            self.intrusion_armed = False
            self.tick.emit(f"Arming trap in {int(self.target)}s... Hands off!")
            return

        if not self.intrusion_armed:
            rem = int(self.arm_time - time.time())
            if rem <= 0:
                self.intrusion_armed = True
                ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
                self.baseline_input = lii.dwTime
                self.tick.emit("TRAP ARMED: Any input will trigger action instantly!")
            else: self.tick.emit(f"Arming trap in {rem}s... Hands off!")
            return

        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
        if lii.dwTime > self.baseline_input:
            self.tick.emit("INTRUSION DETECTED!")
            self._trigger_event(instant=True)

    def _check_jiggler_trap(self):
        pt = POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))

        # Setup Phase
        if not hasattr(self, 'jiggle_base'):
            self.jiggle_base = (pt.x, pt.y)
            self.jiggle_alt = (pt.x + 2, pt.y + 2) # Jiggle precisely 2 pixels down/right
            self.current_expected = self.jiggle_base
            self.tick.emit("Jiggler Trap ARMED: Jiggling. Do not touch mouse!")
            return

        # Check for external interference (Mouse moved away from expected position)
        dx = abs(pt.x - self.current_expected[0])
        dy = abs(pt.y - self.current_expected[1])

        # If it deviates by more than our strict 2-pixel path
        if dx > 2 or dy > 2:
            self.tick.emit("JIGGLER TRAP TRIPPED! Intended human movement detected.")
            self._trigger_event(instant=True)
            return

        # Toggle position
        if self.current_expected == self.jiggle_base:
            self.current_expected = self.jiggle_alt
        else:
            self.current_expected = self.jiggle_base

        # Snap mouse back to the precise point in the 2-point loop to keep it awake
        ctypes.windll.user32.SetCursorPos(self.current_expected[0], self.current_expected[1])
        ctypes.windll.user32.mouse_event(0x0001, 0, 0, 0, 0) # Trigger awake ping

    def _check_battery(self):
        if not HAS_PSUTIL: return
        bat = psutil.sensors_battery()
        if not bat: return
        if bat.percent <= self.target and not bat.power_plugged:
            self.tick.emit(f"Battery critically low ({bat.percent}%). Saving session...")
            self._trigger_event(grace_period=60)
        else:
            status = "Plugged in" if bat.power_plugged else "Discharging"
            self.tick.emit(f"Battery: {bat.percent}% ({status})")

    def _check_wifi(self):
        try:
            output = subprocess.check_output("netsh wlan show interfaces", shell=True).decode()
            if self.target not in output:
                self.tick.emit(f"Wi-Fi '{self.target}' disconnected! SECURING SYSTEM...")
                self._trigger_event(grace_period=3, sound_alarm=self.extra)
            else: self.tick.emit(f"Monitoring Wi-Fi: '{self.target}'... (Secured)")
        except: pass

    def _check_cpu(self):
        if not HAS_PSUTIL: return
        threshold_percent, limit_minutes = self.target
        current_cpu = psutil.cpu_percent(interval=None)
        
        if current_cpu >= threshold_percent:
            self.cpu_overload_seconds += 1
        else:
            self.cpu_overload_seconds = 0 

        if self.cpu_overload_seconds >= (limit_minutes * 60):
            self.tick.emit(f"THERMAL/CPU LIMIT REACHED. Sustained > {threshold_percent}%")
            self._trigger_event(grace_period=30)
        else:
            self.tick.emit(f"CPU Load: {current_cpu}% (Sustained overload: {self.cpu_overload_seconds}s)")

    def _check_quota(self):
        if not HAS_PSUTIL: return
        target_proc, limit_minutes = self.target
        limit_seconds = limit_minutes * 60
        found = False

        for p in psutil.process_iter(['name', 'create_time']):
            try:
                if p.info['name'] and p.info['name'].lower() == target_proc.lower():
                    found = True
                    uptime = time.time() - p.info['create_time']
                    if uptime > limit_seconds:
                        self.tick.emit(f"QUOTA EXCEEDED for {target_proc}. Executing action...")
                        self._trigger_event(instant=True)
                        return
                    else:
                        rem = limit_seconds - uptime
                        self.tick.emit(f"Quota {target_proc}: {int(rem/60)}m {int(rem%60)}s remaining")
                        return
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if not found:
            self.tick.emit(f"Quota Process '{target_proc}' is not currently running.")

    def _check_focus_kill(self):
        if not HAS_PSUTIL: return
        targets = [t.strip().lower() for t in self.target.split(',')]
        killed_any = False
        
        for p in psutil.process_iter(['name']):
            try:
                if p.info['name'] and p.info['name'].lower() in targets:
                    p.kill()
                    killed_any = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if killed_any:
            self.tick.emit(f"FOCUS MODE: Blocked targeted application!")
        else:
            self.tick.emit(f"Focus Mode Active. Blocking: {', '.join(targets)}")

    def _check_vpn(self):
        if not HAS_PSUTIL: return
        addrs = psutil.net_if_addrs()
        if self.target not in addrs:
            self.tick.emit(f"VPN/Network '{self.target}' disconnected! Protecting privacy...")
            self._trigger_event(instant=True)
        else:
            self.tick.emit(f"Monitoring VPN/Adapter: '{self.target}'... (Secured)")

    def _check_honeypot(self):
        if not os.path.exists(self.target):
            self.tick.emit("HONEYPOT FILE DELETED! Securing system...")
            self._trigger_event(instant=True)
        elif os.path.getmtime(self.target) != self.honeypot_mtime:
            self.tick.emit("HONEYPOT FILE MODIFIED! Ransomware trap triggered...")
            self._trigger_event(instant=True)
        else:
            self.tick.emit(f"Honeypot active. Watching: {os.path.basename(self.target)}")

    def stop(self):
        self.is_running = False

# ==========================================
# 2. Grace Period Warning Window
# ==========================================
class GraceWindow(QWidget):
    abort_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setFixedSize(400, 250)
        self.setStyleSheet("background-color: #d32f2f; color: white; border: 5px solid #b71c1c;")
        layout = QVBoxLayout(self)
        self.title = QLabel("ACTION IMPENDING")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("font-size: 24px; font-weight: bold; border: none;")
        layout.addWidget(self.title)
        self.countdown_label = QLabel("60")
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_label.setStyleSheet("font-size: 72px; font-weight: bold; border: none;")
        layout.addWidget(self.countdown_label)
        self.abort_btn = QPushButton("ABORT")
        self.abort_btn.setStyleSheet("QPushButton { background-color: white; color: #d32f2f; font-size: 20px; font-weight: bold; padding: 15px; border-radius: 5px; border: none;} QPushButton:hover { background-color: #f5f5f5; }")
        self.abort_btn.clicked.connect(self._on_abort)
        layout.addWidget(self.abort_btn)

    def update_time(self, seconds):
        self.countdown_label.setText(str(seconds))

    def _on_abort(self):
        self.abort_signal.emit()
        self.hide()

# ==========================================
# 3. Security Windows (Shields)
# ==========================================
class ScreenShieldWindow(QWidget):
    def __init__(self, pin):
        super().__init__()
        self.pin = pin
        self.entered_pin = ""
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.ToolTip)
        self.setGeometry(QApplication.primaryScreen().virtualGeometry())
        self.setStyleSheet("background-color: rgba(0, 0, 0, 40);")
        self.grabKeyboard()
        self.grabMouse()
        self.setCursor(Qt.CursorShape.ForbiddenCursor)
        layout = QVBoxLayout(self)
        self.status_box = QLabel("SHIELD ACTIVE\nType PIN to unlock")
        self.status_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_box.setStyleSheet("color: #ffffff; background-color: rgba(0, 0, 0, 150); font-size: 16px; font-weight: bold; padding: 15px; border-radius: 10px;")
        h_layout = QHBoxLayout(); h_layout.addStretch(); h_layout.addWidget(self.status_box); h_layout.addStretch()
        layout.addStretch(); layout.addLayout(h_layout); layout.addStretch()

    def keyPressEvent(self, event):
        key = event.text()
        if key:
            self.entered_pin += key
            self.entered_pin = self.entered_pin[-len(self.pin):]
            if self.entered_pin == self.pin:
                self.releaseKeyboard(); self.releaseMouse(); self.close()
        event.accept()

    def mousePressEvent(self, event): event.accept()
    def mouseDoubleClickEvent(self, event): event.accept()

class FakeUpdateWindow(QWidget):
    def __init__(self, pin):
        super().__init__()
        self.pin = pin
        self.entered_pin = ""
        self.percent = 0
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.ToolTip)
        self.setGeometry(QApplication.primaryScreen().virtualGeometry())
        self.setStyleSheet("background-color: #0078D7; color: white;")
        self.setCursor(Qt.CursorShape.BlankCursor)
        layout = QVBoxLayout(self)
        self.label = QLabel("Working on updates  0%\nDon't turn off your PC. This will take a while.")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("font-size: 32px; font-family: 'Segoe UI', Arial;")
        layout.addWidget(self.label)
        self.grabKeyboard()
        self.grabMouse()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_percent)
        self.timer.start(7500) 

    def update_percent(self):
        if self.percent < 99: self.percent += random.randint(1, 3); self.percent = min(self.percent, 99)
        self.label.setText(f"Working on updates  {self.percent}%\nDon't turn off your PC. This will take a while.")

    def keyPressEvent(self, event):
        key = event.text()
        if key:
            self.entered_pin += key
            self.entered_pin = self.entered_pin[-len(self.pin):]
            if self.entered_pin == self.pin:
                self.releaseKeyboard(); self.releaseMouse(); self.timer.stop(); self.close()
        event.accept()

    def mousePressEvent(self, event): event.accept()
    def mouseDoubleClickEvent(self, event): event.accept()

# ==========================================
# 4. Main Application Window
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PowerFlow - Advanced System Manager")
        self.setFixedSize(550, 600) 
        self.thread = None
        self.shield_window = None
        self.jiggler_thread = None
        self.siren_thread = None
        self.fake_update_window = None
        
        self.init_ui()
        self.init_system_tray()
        self.apply_theme(dark_mode=True)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        top_bar = QHBoxLayout()
        self.help_btn = QPushButton("Help")
        self.help_btn.clicked.connect(self.show_help_dialog)
        self.theme_btn = QPushButton("Toggle Light/Dark")
        self.theme_btn.clicked.connect(self.toggle_theme)
        top_bar.addStretch()
        top_bar.addWidget(self.help_btn)
        top_bar.addWidget(self.theme_btn)
        main_layout.addLayout(top_bar)

        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(True) # Required for many tabs
        main_layout.addWidget(self.tabs)

        # Tab 0: Timer
        self.tab_timer = QWidget()
        l_timer = QVBoxLayout(self.tab_timer)
        h0 = QHBoxLayout(); h0.addWidget(QLabel("<i>Countdown: Executes after set time.</i>")); 
        b0 = QPushButton("?"); b0.setFixedSize(25, 25); b0.clicked.connect(lambda: self.show_tab_help("Timer", "Countdown timer that triggers after the set minutes pass.", "Set to 60m before bed to shut down the PC after you fall asleep while watching a movie.")); h0.addWidget(b0)
        l_timer.addLayout(h0)
        l_timer.addWidget(QLabel("Shut down after (minutes):"))
        self.spin_minutes = QSpinBox(); self.spin_minutes.setRange(1, 1440); self.spin_minutes.setValue(60)
        l_timer.addWidget(self.spin_minutes); l_timer.addStretch()
        self.tabs.addTab(self.tab_timer, "Timer")

        # Tab 1: Exact Time
        self.tab_time = QWidget()
        l_time = QVBoxLayout(self.tab_time)
        h1 = QHBoxLayout(); h1.addWidget(QLabel("<i>Schedule: Executes at a precise time.</i>")); 
        b1 = QPushButton("?"); b1.setFixedSize(25, 25); b1.clicked.connect(lambda: self.show_tab_help("Exact Time", "Schedules the action for a specific clock time (24h format).", "Schedule a 3:00 AM restart every night to keep your system performing at its best.")); h1.addWidget(b1)
        l_time.addLayout(h1)
        l_time.addWidget(QLabel("Shut down exactly at:"))
        self.time_edit = QTimeEdit(); self.time_edit.setTime(QTime.currentTime().addSecs(3600)); self.time_edit.setDisplayFormat("HH:mm:ss")
        l_time.addWidget(self.time_edit); l_time.addStretch()
        self.tabs.addTab(self.tab_time, "Exact Time")

        # Tab 2: App Quota
        self.tab_quota = QWidget()
        l_quota = QVBoxLayout(self.tab_quota)
        if HAS_PSUTIL:
            h2 = QHBoxLayout(); h2.addWidget(QLabel("<i>Quota: Limits total app usage time.</i>")); 
            b2 = QPushButton("?"); b2.setFixedSize(25, 25); b2.clicked.connect(lambda: self.show_tab_help("App Quota", "Tracks the active uptime of a specific EXE and triggers if it stays open longer than the limit.", "Limit gaming apps like 'valorant.exe' to 120m per day to manage screen time.")); h2.addWidget(b2)
            l_quota.addLayout(h2)
            l_quota.addWidget(QLabel("Trigger action when app exceeds time limit:"))
            self.txt_quota_app = QComboBox(); self.txt_quota_app.setEditable(True); self.txt_quota_app.setPlaceholderText("Select an app or type EXE name...")
            l_quota.addWidget(self.txt_quota_app)
            btn_refresh_quota = QPushButton("Refresh Process List"); btn_refresh_quota.clicked.connect(self.refresh_processes)
            l_quota.addWidget(btn_refresh_quota)
            l_quota.addWidget(QLabel("Quota Limit (Minutes):"))
            self.spin_quota_mins = QSpinBox(); self.spin_quota_mins.setRange(1, 1440); self.spin_quota_mins.setValue(120)
            l_quota.addWidget(self.spin_quota_mins)
        else: l_quota.addWidget(QLabel("psutil library required."))
        l_quota.addStretch()
        self.tabs.addTab(self.tab_quota, "App Quota")

        # Tab 3: Focus Mode (App Killer)
        self.tab_focus = QWidget()
        l_focus = QVBoxLayout(self.tab_focus)
        if HAS_PSUTIL:
            h3 = QHBoxLayout(); h3.addWidget(QLabel("<i>Focus: Instantly kills forbidden apps.</i>")); 
            b3 = QPushButton("?"); b3.setFixedSize(25, 25); b3.clicked.connect(lambda: self.show_tab_help("Focus Mode", "A real-time killer that terminates forbidden apps as soon as they are launched.", "Block 'discord.exe' or 'steam.exe' while you're studying to ensure you stay productive.")); h3.addWidget(b3)
            l_focus.addLayout(h3)
            l_focus.addWidget(QLabel("Instantly closes forbidden apps when launched:"))
            self.txt_focus_kill = QComboBox(); self.txt_focus_kill.setEditable(True); self.txt_focus_kill.setPlaceholderText("Select app to block or type EXE names...")
            l_focus.addWidget(self.txt_focus_kill)
            btn_refresh_focus = QPushButton("Refresh Process List"); btn_refresh_focus.clicked.connect(self.refresh_processes)
            l_focus.addWidget(btn_refresh_focus)
        else: l_focus.addWidget(QLabel("psutil library required."))
        l_focus.addStretch()
        self.tabs.addTab(self.tab_focus, "Focus App Killer")

        # Tab 4: CPU Monitor
        self.tab_cpu = QWidget()
        l_cpu = QVBoxLayout(self.tab_cpu)
        if HAS_PSUTIL:
            h4 = QHBoxLayout(); h4.addWidget(QLabel("<i>Thermal Check: Triggers on CPU overload.</i>")); 
            b4 = QPushButton("?"); b4.setFixedSize(25, 25); b4.clicked.connect(lambda: self.show_tab_help("CPU Monitor", "Triggers if CPU usage remains above a threshold for a sustained period.", "Shut down if a video render stays at 100% CPU for over 4 hours to prevent overheating while away.")); h4.addWidget(b4)
            l_cpu.addLayout(h4)
            l_cpu.addWidget(QLabel("Thermal Protection (Sustained Load Monitor):"))
            self.spin_cpu_pct = QSpinBox(); self.spin_cpu_pct.setRange(1, 100); self.spin_cpu_pct.setValue(99); self.spin_cpu_pct.setSuffix("% Usage")
            self.spin_cpu_mins = QSpinBox(); self.spin_cpu_mins.setRange(1, 120); self.spin_cpu_mins.setValue(10); self.spin_cpu_mins.setSuffix(" Minutes")
            l_cpu.addWidget(self.spin_cpu_pct); l_cpu.addWidget(self.spin_cpu_mins)
        else: l_cpu.addWidget(QLabel("psutil library required."))
        l_cpu.addStretch()
        self.tabs.addTab(self.tab_cpu, "CPU Monitor")

        # Tab 5: Battery Savior
        self.tab_battery = QWidget()
        l_bat = QVBoxLayout(self.tab_battery)
        if HAS_PSUTIL:
            h5 = QHBoxLayout(); h5.addWidget(QLabel("<i>Power Protection: Triggers on low battery.</i>")); 
            b5 = QPushButton("?"); b5.setFixedSize(25, 25); b5.clicked.connect(lambda: self.show_tab_help("Battery Savior", "Prevents data loss. Triggers when unplugged and battery falls below your threshold.", "Automatically hibernate at 10% battery while at a cafe to save your open work.")); h5.addWidget(b5)
            l_bat.addLayout(h5)
            l_bat.addWidget(QLabel("Trigger if unplugged & drops below:"))
            self.spin_battery = QSpinBox(); self.spin_battery.setRange(1, 100); self.spin_battery.setValue(15); self.spin_battery.setSuffix("%")
            l_bat.addWidget(self.spin_battery)
        else: l_bat.addWidget(QLabel("psutil library required."))
        l_bat.addStretch()
        self.tabs.addTab(self.tab_battery, "Battery Savior")

        # Tab 6: VPN Shield
        self.tab_vpn = QWidget()
        l_vpn = QVBoxLayout(self.tab_vpn)
        if HAS_PSUTIL:
            h6 = QHBoxLayout(); h6.addWidget(QLabel("<i>Privacy: Triggers on VPN drop.</i>")); 
            b6 = QPushButton("?"); b6.setFixedSize(25, 25); b6.clicked.connect(lambda: self.show_tab_help("VPN Shield", "Privacy protection. Triggers immediately if your selected VPN connection drops.", "Immediately shut down if your VPN drops while downloading sensitive files to avoid IP leaks.")); h6.addWidget(b6)
            l_vpn.addLayout(h6)
            l_vpn.addWidget(QLabel("Privacy Shield (Trigger if VPN/Adapter drops):"))
            self.combo_vpn = QComboBox(); self.combo_vpn.addItems(list(psutil.net_if_addrs().keys()))
            l_vpn.addWidget(self.combo_vpn)
        else: l_vpn.addWidget(QLabel("psutil library required."))
        l_vpn.addStretch()
        self.tabs.addTab(self.tab_vpn, "VPN Shield")

        # Tab 7: Wi-Fi Monitor
        self.tab_wifi = QWidget()
        l_wifi = QVBoxLayout(self.tab_wifi)
        h7 = QHBoxLayout(); h7.addWidget(QLabel("<i>Security: Triggers on Wi-Fi drop.</i>")); 
        b7 = QPushButton("?"); b7.setFixedSize(25, 25); b7.clicked.connect(lambda: self.show_tab_help("Wi-Fi Monitor", "Security for public areas. Triggers if your laptop leaves your trusted network range.", "Arm it at a library; if a thief takes your laptop away, a siren blasts at 100% volume.")); h7.addWidget(b7)
        l_wifi.addLayout(h7)
        l_wifi.addWidget(QLabel("Monitor (Trusted Network Drop or Theft):"))
        self.combo_wifi = QComboBox(); self.combo_wifi.setEditable(True)
        if self.get_current_wifi(): self.combo_wifi.addItem(self.get_current_wifi())
        l_wifi.addWidget(self.combo_wifi)
        self.chk_wifi_siren = QCheckBox("Coffee Shop Mode: Max Volume & Siren Alarm")
        self.chk_wifi_siren.setToolTip("Leave unchecked for a silent 'Trusted Network' lock.")
        l_wifi.addWidget(self.chk_wifi_siren)
        l_wifi.addStretch()
        self.tabs.addTab(self.tab_wifi, "Wi-Fi Monitor")

        # Tab 8: Download Speed
        self.tab_dl = QWidget()
        l_dl = QVBoxLayout(self.tab_dl)
        if HAS_PSUTIL:
            h8 = QHBoxLayout(); h8.addWidget(QLabel("<i>Download Check: Triggers on traffic stop.</i>")); 
            b8 = QPushButton("?"); b8.setFixedSize(25, 25); b8.clicked.connect(lambda: self.show_tab_help("Download Monitor", "Triggers when network speed falls below a threshold (meaning task is finished).", "Start a big game download; once speed drops to 0 (finished), the PC shuts down automatically.")); h8.addWidget(b8)
            l_dl.addLayout(h8)
            l_dl.addWidget(QLabel("Trigger when KB/s drops below:"))
            self.spin_net = QSpinBox(); self.spin_net.setRange(1, 10000); self.spin_net.setValue(50)
            l_dl.addWidget(self.spin_net)
        else: l_dl.addWidget(QLabel("psutil library required."))
        l_dl.addStretch()
        self.tabs.addTab(self.tab_dl, "Download Monitor")

        # Tab 9: USB Kill Switch
        self.tab_usb = QWidget()
        l_usb = QVBoxLayout(self.tab_usb)
        if HAS_PSUTIL:
            h9 = QHBoxLayout(); h9.addWidget(QLabel("<i>Physical Safety: Triggers on USB pull.</i>")); 
            b9 = QPushButton("?"); b9.setFixedSize(25, 25); b9.clicked.connect(lambda: self.show_tab_help("USB Kill Switch", "Physical hardware security. Action triggers if your selected USB key is unplugged.", "Pull a secret USB key to lock the PC instantly whenever you leave your desk.")); h9.addWidget(b9)
            l_usb.addLayout(h9)
            l_usb.addWidget(QLabel("Trigger if unplugged:"))
            self.combo_usb = QComboBox(); self.combo_usb.addItems([p.mountpoint for p in psutil.disk_partitions()])
            l_usb.addWidget(self.combo_usb)
        else: l_usb.addWidget(QLabel("psutil library required."))
        l_usb.addStretch()
        self.tabs.addTab(self.tab_usb, "USB Kill Switch")

        # Tab 10: Intrusion Trap
        self.tab_intrude = QWidget()
        l_intrude = QVBoxLayout(self.tab_intrude)
        h10 = QHBoxLayout(); h10.addWidget(QLabel("<i>Security: Triggers if anyone touches your PC.</i>")); 
        b10 = QPushButton("?"); b10.setFixedSize(25, 25); b10.clicked.connect(lambda: self.show_tab_help("Intrusion Trap", "Silent security. Sets a trap that triggers if any movement/input is detected on this PC.", "Arm before going for lunch; if anyone touches your mouse or keyboard, the PC locks immediately.")); h10.addWidget(b10)
        l_intrude.addLayout(h10)
        l_intrude.addWidget(QLabel("Any touch to the mouse or keyboard triggers action:"))
        self.spin_trap_delay = QSpinBox(); self.spin_trap_delay.setRange(1, 60); self.spin_trap_delay.setValue(5); self.spin_trap_delay.setSuffix("s Grace Period")
        l_intrude.addWidget(self.spin_trap_delay)
        l_intrude.addStretch()
        self.tabs.addTab(self.tab_intrude, "Intrusion Trap")

        # Tab 11: Armed Jiggler Trap (NEW)
        self.tab_jiggle_trap = QWidget()
        l_j_trap = QVBoxLayout(self.tab_jiggle_trap)
        h11 = QHBoxLayout(); h11.addWidget(QLabel("<i>Decoy: Triggers if human takes control.</i>")); 
        b11 = QPushButton("?"); b11.setFixedSize(25, 25); b11.clicked.connect(lambda: self.show_tab_help("Armed Jiggler", "A decoy stay-awake trap. If a real person moves the mouse elsewhere, it triggers.", "Detect if a hacker takes remote control and moves the mouse against the pattern.")); h11.addWidget(b11)
        l_j_trap.addLayout(h11)
        l_j_trap.addWidget(QLabel("A decoy trap. Keeps PC awake by jiggling exactly 2 pixels.\nIf the mouse is forced away from its path by a user, it triggers!"))
        l_j_trap.addStretch()
        self.tabs.addTab(self.tab_jiggle_trap, "Armed Jiggler")

        # Tab 12: Ransomware Honeypot
        self.tab_honey = QWidget()
        l_honey = QVBoxLayout(self.tab_honey)
        h12 = QHBoxLayout(); h12.addWidget(QLabel("<i>Anti-Ransomware: Triggers on file change.</i>")); 
        b12 = QPushButton("?"); b12.setFixedSize(25, 25); b12.clicked.connect(lambda: self.show_tab_help("Ransomware Honeypot", "Ransomware protection. Triggers if a decoy 'Bank_Records.pdf' file is modified or deleted.", "If a virus tries to encrypt your dummy files, the PC shuts down to stop the spread.")); h12.addWidget(b12)
        l_honey.addLayout(h12)
        l_honey.addWidget(QLabel("Trigger if dummy file is modified/deleted:"))
        self.txt_honeypot = QLineEdit(); self.txt_honeypot.setPlaceholderText("Select a dummy file...")
        btn_browse_honey = QPushButton("Browse"); btn_browse_honey.clicked.connect(self.browse_honeypot)
        hl = QHBoxLayout(); hl.addWidget(self.txt_honeypot); hl.addWidget(btn_browse_honey)
        l_honey.addLayout(hl)
        l_honey.addStretch()
        self.tabs.addTab(self.tab_honey, "Ransomware Honeypot")

        # --- MANUAL & INTERACTIVE TABS ---

        # Tab 13: Screen Shield
        self.tab_shield = QWidget()
        l_shield = QVBoxLayout(self.tab_shield)
        l_shield.addWidget(QLabel("Transparent lock overlay. Enter PIN to lock/unlock:"))
        self.pin_shield = QLineEdit(); self.pin_shield.setEchoMode(QLineEdit.EchoMode.Password)
        l_shield.addWidget(self.pin_shield)
        self.btn_shield = QPushButton("Activate Transparent Shield")
        self.btn_shield.setStyleSheet("background-color: #1976D2; color: white; padding: 8px; font-weight: bold;")
        self.btn_shield.clicked.connect(self.activate_screen_shield)
        l_shield.addWidget(self.btn_shield); l_shield.addStretch()
        self.tabs.addTab(self.tab_shield, "Screen Shield")

        # Tab 14: Fake Update
        self.tab_update = QWidget()
        l_update = QVBoxLayout(self.tab_update)
        l_update.addWidget(QLabel("Blue screen decoy. Enter PIN to lock/unlock:"))
        self.pin_update = QLineEdit(); self.pin_update.setEchoMode(QLineEdit.EchoMode.Password)
        l_update.addWidget(self.pin_update)
        self.btn_fake_update = QPushButton("Activate Fake Update")
        self.btn_fake_update.setStyleSheet("background-color: #0078D7; color: white; padding: 8px; font-weight: bold;")
        self.btn_fake_update.clicked.connect(self.activate_fake_update)
        l_update.addWidget(self.btn_fake_update); l_update.addStretch()
        self.tabs.addTab(self.tab_update, "Fake Update")

        # Tab 15: Mouse Jiggler
        self.tab_jig = QWidget()
        l_jig = QVBoxLayout(self.tab_jig)
        l_jig.addWidget(QLabel("Standard utility. Prevents PC from automatically sleeping:"))
        self.btn_jiggler = QPushButton("Turn ON Mouse Jiggler (Awake Mode)")
        self.btn_jiggler.setStyleSheet("background-color: #FF9800; color: white; padding: 8px; font-weight: bold;")
        self.btn_jiggler.clicked.connect(self.toggle_jiggler)
        l_jig.addWidget(self.btn_jiggler); l_jig.addStretch()
        self.tabs.addTab(self.tab_jig, "Mouse Jiggler")

        # Tab 16: Panic Button
        self.tab_panic = QWidget()
        l_panic = QVBoxLayout(self.tab_panic)
        if HAS_KEYBOARD:
            l_panic.addWidget(QLabel("Global Boss Key (Mutes audio, hides windows, launches Fake Update):"))
            self.txt_panic_key = QLineEdit(); self.txt_panic_key.setText("ctrl+shift+space")
            self.btn_bind_panic = QPushButton("Bind Global Hotkey")
            self.btn_bind_panic.clicked.connect(self.bind_panic_button)
            pl = QHBoxLayout(); pl.addWidget(self.txt_panic_key); pl.addWidget(self.btn_bind_panic)
            l_panic.addLayout(pl)
            self.lbl_panic_status = QLabel("Panic Button: Not Bound")
            l_panic.addWidget(self.lbl_panic_status)
        else:
            l_panic.addWidget(QLabel("keyboard library required. (pip install keyboard)"))
        l_panic.addStretch()
        self.tabs.addTab(self.tab_panic, "Panic Button")

        # Action Configuration Group
        action_group = QGroupBox("Action Configuration (Triggered by monitoring tabs)")
        action_layout = QVBoxLayout()
        
        self.combo_action = QComboBox()
        self.combo_action.addItems(["Shutdown", "Restart", "Sleep", "Hibernate", "Lock", "Sign Out", "Close Target App Only (Kill)"])
        action_layout.addWidget(self.combo_action)

        self.check_force = QCheckBox("Force action / close apps instantly")
        self.check_force.setChecked(True)
        action_layout.addWidget(self.check_force)
        
        action_group.setLayout(action_layout)
        main_layout.addWidget(action_group)

        # Status Label
        self.lbl_status = QLabel("Status: Idle")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("font-weight: bold; margin: 10px 0;")
        main_layout.addWidget(self.lbl_status)

        # Control Buttons
        btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("START MONITORING")
        self.btn_start.setMinimumHeight(40)
        self.btn_start.clicked.connect(self.start_monitoring)
        
        self.btn_abort = QPushButton("ABORT / STOP")
        self.btn_abort.setMinimumHeight(40)
        self.btn_abort.setEnabled(False)
        self.btn_abort.clicked.connect(self.stop_monitoring)
        
        btn_layout.addWidget(self.btn_start); btn_layout.addWidget(self.btn_abort)
        main_layout.addLayout(btn_layout)

        self.grace_window = GraceWindow()
        self.grace_window.abort_signal.connect(self.stop_monitoring)
        self.refresh_processes()

    def get_current_wifi(self):
        try:
            output = subprocess.check_output("netsh wlan show interfaces", shell=True).decode()
            for line in output.split('\n'):
                if " SSID" in line and "BSSID" not in line: return line.split(":")[1].strip()
        except: pass
        return ""

    def browse_honeypot(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Dummy File for Ransomware Trap")
        if file: self.txt_honeypot.setText(file)

    def refresh_processes(self):
        if not HAS_PSUTIL: return
        procs = sorted(list(set([p.info['name'] for p in psutil.process_iter(['name']) if p.info['name']])), key=str.lower)
        curr_quota = self.txt_quota_app.currentText()
        curr_focus = self.txt_focus_kill.currentText()
        self.txt_quota_app.clear(); self.txt_quota_app.addItems(procs); 
        self.txt_focus_kill.clear(); self.txt_focus_kill.addItems(procs); 
        
        # If nothing was selected, reset to -1 so placeholder shows
        if not curr_quota: self.txt_quota_app.setCurrentIndex(-1)
        else: self.txt_quota_app.setCurrentText(curr_quota)
        
        if not curr_focus: self.txt_focus_kill.setCurrentIndex(-1)
        else: self.txt_focus_kill.setCurrentText(curr_focus)

    def show_help_dialog(self):
        text = """
        <h2 style='color: #007acc;'>PowerFlow Tool Documentation</h2>
        <p><b>Monitoring Tools:</b></p>
        <ul>
            <li><b>Timer:</b> Countdown to action.</li>
            <li><b>Exact Time:</b> Schedule action at a specific time.</li>
            <li><b>App Quota:</b> Limits total uptime for a specific application.</li>
            <li><b>Focus Mode:</b> Instantly closes forbidden apps as they open.</li>
            <li><b>CPU Monitor:</b> Triggers if CPU usage remains high for too long.</li>
            <li><b>Battery Savior:</b> Triggers when battery drops below % while unplugged.</li>
            <li><b>VPN Shield:</b> Secures system if your VPN connection drops.</li>
            <li><b>Wi-Fi Monitor:</b> Triggers if you leave your trusted network.</li>
            <li><b>Download Monitor:</b> Triggers when your internet traffic stops.</li>
            <li><b>USB Kill Switch:</b> Triggers if the selected USB drive is pulled.</li>
            <li><b>Intrusion Trap:</b> Triggers if any mouse/keyboard input is detected.</li>
            <li><b>Armed Jiggler:</b> A decoy trap that detects unauthorized mouse usage.</li>
            <li><b>Honeypot:</b> Triggers if a decoy file is modified or deleted.</li>
        </ul>
        <p><b>Interactive Security:</b></p>
        <ul>
            <li><b>Screen Shield:</b> Semi-transparent lock (Requires PIN).</li>
            <li><b>Fake Update:</b> Decoy Windows Update screen (Requires PIN).</li>
            <li><b>Panic Button:</b> Global hotkey to hide everything instantly.</li>
        </ul>
        """
        QMessageBox.information(self, "PowerFlow Help", text)

    def show_tab_help(self, title, info, scenario):
        text = f"<h3 style='color: #007acc;'>{title}</h3><p><b>How it works:</b><br>{info}</p><p><b>Real-World Scenario:</b><br><i>{scenario}</i></p>"
        QMessageBox.information(self, f"Help: {title}", text)

    def bind_panic_button(self):
        if not HAS_KEYBOARD: return
        hotkey = self.txt_panic_key.text()
        try:
            keyboard.unhook_all_hotkeys()
            keyboard.add_hotkey(hotkey, self.activate_panic_mode)
            self.lbl_panic_status.setText(f"Panic Button Bound: {hotkey}")
            self.lbl_panic_status.setStyleSheet("color: #4CAF50; font-weight:bold;")
            QMessageBox.information(self, "Success", f"Globally bound {hotkey}. Press it anytime to mute, hide windows, and launch the Fake Update screen.")
        except Exception as e:
            QMessageBox.warning(self, "Binding Error", str(e))

    def activate_panic_mode(self):
        if HAS_KEYBOARD:
            keyboard.send('volume mute')
            keyboard.send('win+d')
            time.sleep(0.5) 
            self.activate_fake_update(from_hotkey=True)

    def activate_screen_shield(self):
        pin = self.pin_shield.text()
        if not pin:
            QMessageBox.warning(self, "Security Error", "Please enter a PIN to unlock the shield before activating it.")
            return
        self.shield_window = ScreenShieldWindow(pin)
        self.shield_window.showFullScreen()
        self.pin_shield.clear()
        self.update_status("Status: Screen Shield Active")

    def activate_fake_update(self, from_hotkey=False):
        pin = self.pin_update.text() if not from_hotkey else getattr(self, 'last_pin', '0000')
        if not pin and not from_hotkey:
            QMessageBox.warning(self, "Security Error", "Please enter a PIN to unlock.")
            return
        if not from_hotkey: self.last_pin = pin 
        
        self.fake_update_window = FakeUpdateWindow(pin)
        self.fake_update_window.showFullScreen()
        self.pin_update.clear()
        self.update_status("Status: Fake Update Decoy Active")

    def toggle_jiggler(self):
        if self.jiggler_thread and self.jiggler_thread.isRunning():
            self.jiggler_thread.stop(); self.jiggler_thread.wait()
            self.btn_jiggler.setText("Turn ON Mouse Jiggler (Awake Mode)")
            self.btn_jiggler.setStyleSheet("background-color: #FF9800; color: white; padding: 8px; font-weight: bold;")
            self.update_status("Status: Mouse Jiggler Disabled")
        else:
            self.jiggler_thread = JigglerThread(); self.jiggler_thread.start()
            self.btn_jiggler.setText("Turn OFF Mouse Jiggler")
            self.btn_jiggler.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px; font-weight: bold;")
            self.update_status("Status: Mouse Jiggler Active")

    def start_monitoring(self):
        tab_idx = self.tabs.currentIndex()
        if tab_idx >= 13: 
            QMessageBox.information(self, "Info", "This tab contains an interactive tool. Use the dedicated button above to activate it.")
            return
            
        action = self.combo_action.currentText().lower()
        force = self.check_force.isChecked()
        extra = None

        if tab_idx == 0:
            mode = 'timer'; target = time.time() + (self.spin_minutes.value() * 60)
        elif tab_idx == 1:
            mode = 'time'; target = self.time_edit.time().toPyTime()
        elif tab_idx == 2:
            if not self.txt_quota_app.currentText(): return QMessageBox.warning(self,"Error","Enter a process for Quota.")
            mode = 'quota'; target = (self.txt_quota_app.currentText(), self.spin_quota_mins.value())
        elif tab_idx == 3:
            if not self.txt_focus_kill.currentText(): return QMessageBox.warning(self,"Error","Enter apps to block.")
            mode = 'focus_kill'; target = self.txt_focus_kill.currentText()
        elif tab_idx == 4:
            mode = 'cpu'; target = (self.spin_cpu_pct.value(), self.spin_cpu_mins.value())
        elif tab_idx == 5:
            mode = 'battery'; target = self.spin_battery.value()
        elif tab_idx == 6:
            mode = 'vpn'; target = self.combo_vpn.currentText()
        elif tab_idx == 7:
            mode = 'wifi'; target = self.combo_wifi.currentText()
            extra = self.chk_wifi_siren.isChecked()
        elif tab_idx == 8:
            mode = 'network'; target = self.spin_net.value()
        elif tab_idx == 9:
            mode = 'usb'; target = self.combo_usb.currentText()
        elif tab_idx == 10:
            mode = 'intrusion'; target = self.spin_trap_delay.value()
        elif tab_idx == 11:
            mode = 'jiggler_trap'; target = None
        elif tab_idx == 12:
            if not self.txt_honeypot.text(): return QMessageBox.warning(self,"Error","Select a dummy file.")
            mode = 'honeypot'; target = self.txt_honeypot.text()

        self.thread = MonitorThread(mode, target, action, force, extra)
        self.thread.tick.connect(self.update_status)
        self.thread.warning.connect(self.show_warning)
        self.thread.execute_action.connect(self.execute_power_action)
        self.thread.trigger_siren.connect(self.launch_siren)
        self.thread.start()

        self.btn_start.setEnabled(False); self.btn_abort.setEnabled(True); self.tabs.setEnabled(False)

    def stop_monitoring(self):
        if self.thread and self.thread.isRunning():
            self.thread.stop(); self.thread.wait()
        self.grace_window.hide()
        self.update_status("Status: Idle (Aborted)")
        self.btn_start.setEnabled(True); self.btn_abort.setEnabled(False); self.tabs.setEnabled(True)

    def launch_siren(self):
        self.siren_thread = SirenThread()
        self.siren_thread.start()

    def update_status(self, text):
        self.lbl_status.setText(text)
        if self.grace_window.isVisible() and "Remaining:" in text:
            try:
                h, m, s = map(int, text.split(": ")[1].split(':'))
                self.grace_window.update_time(h*3600 + m*60 + s)
            except: pass

    def show_warning(self, remaining):
        self.grace_window.update_time(remaining); self.grace_window.show()

    def execute_power_action(self):
        self.grace_window.hide()
        action = self.combo_action.currentText().lower()
        f_flag = "/f " if self.check_force.isChecked() else ""
        
        try:
            if "shutdown" in action: subprocess.run(f"shutdown /s {f_flag}/t 0", shell=True)
            elif "restart" in action: subprocess.run(f"shutdown /r {f_flag}/t 0", shell=True)
            elif "sign out" in action: subprocess.run(f"shutdown /l {f_flag}", shell=True)
            elif "hibernate" in action: subprocess.run("shutdown /h", shell=True)
            elif "sleep" in action: subprocess.run("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
            elif "lock" in action: subprocess.run("rundll32.exe user32.dll,LockWorkStation", shell=True)
            elif "kill" in action and hasattr(self.thread, 'target') and isinstance(self.thread.target, tuple):
                target_proc = self.thread.target[0]
                for p in psutil.process_iter(['name']):
                    if p.info['name'] and p.info['name'].lower() == target_proc.lower(): p.kill()
            
            self.update_status(f"Status: Executed {action.upper()}")
        except Exception as e:
            QMessageBox.critical(self, "Execution Error", f"Failed command:\n{e}")
        self.stop_monitoring()

    # ==========================================
    # System Tray & Theming
    # ==========================================
    def init_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
        s_act = QAction("Open", self); s_act.triggered.connect(self.show)
        q_act = QAction("Exit", self); q_act.triggered.connect(QApplication.instance().quit)
        m = QMenu(); m.addAction(s_act); m.addAction(q_act)
        self.tray_icon.setContextMenu(m); self.tray_icon.show()

    def changeEvent(self, event):
        if event.type() == event.Type.WindowStateChange and self.windowState() & Qt.WindowState.WindowMinimized:
            event.ignore(); self.hide()
            self.tray_icon.showMessage("PowerFlow", "Running in background.", QSystemTrayIcon.MessageIcon.Information, 2000)
        super().changeEvent(event)

    def toggle_theme(self):
        self.dark_mode = not getattr(self, 'dark_mode', True)
        self.apply_theme(self.dark_mode)

    def apply_theme(self, dark_mode):
        self.dark_mode = dark_mode
        if dark_mode:
            self.setStyleSheet("""
                QMainWindow, QWidget { background-color: #1e1e1e; color: #ffffff; }
                QTabWidget::pane { border: 1px solid #333; }
                QTabBar::tab { background: #2d2d2d; padding: 8px 15px; border: 1px solid #333; }
                QTabBar::tab:selected { background: #007acc; font-weight: bold; }
                QPushButton { background-color: #333; color: white; border: 1px solid #555; padding: 5px; border-radius: 3px; }
                QPushButton:hover { background-color: #444; }
                QSpinBox, QTimeEdit, QComboBox, QLineEdit { background-color: #333; color: white; border: 1px solid #555; padding: 5px; }
                QGroupBox { border: 1px solid #555; margin-top: 10px; font-weight: bold; padding-top: 15px; }
            """)
            self.btn_start.setStyleSheet("background-color: #2e7d32; font-weight: bold; font-size: 14px;")
            self.btn_abort.setStyleSheet("background-color: #c62828; font-weight: bold; font-size: 14px;")
        else:
            self.setStyleSheet("""
                QMainWindow, QWidget { background-color: #f0f0f0; color: #000000; }
                QTabWidget::pane { border: 1px solid #ccc; }
                QTabBar::tab { background: #e0e0e0; padding: 8px 15px; border: 1px solid #ccc; }
                QTabBar::tab:selected { background: #ffffff; font-weight: bold; }
                QPushButton { background-color: #e0e0e0; border: 1px solid #bbb; padding: 5px; border-radius: 3px; }
                QPushButton:hover { background-color: #d0d0d0; }
                QSpinBox, QTimeEdit, QComboBox, QLineEdit { background-color: #ffffff; border: 1px solid #ccc; padding: 5px; }
                QGroupBox { border: 1px solid #ccc; margin-top: 10px; font-weight: bold; padding-top: 15px; }
            """)
            self.btn_start.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; font-size: 14px;")
            self.btn_abort.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; font-size: 14px;")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False) 
    window = MainWindow()
    window.show()
    sys.exit(app.exec())