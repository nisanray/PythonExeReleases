import sys
import ctypes
import socket
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QTimeEdit, 
                             QSpinBox, QTabWidget, QGroupBox, QListWidget,
                             QMessageBox, QFrame, QCheckBox)
from PyQt6.QtCore import QTimer, QTime, Qt
from PyQt6.QtGui import QFont, QPalette, QColor, QIcon, QCursor
###

class LockScheduler(QMainWindow):
    def __init__(self):
        super().__init__()
        self.timers = []
        self.scheduled_locks = []
        self.init_ui()
        
        # Mouse monitoring
        self.mouse_monitor_timer = QTimer(self)
        self.mouse_monitor_timer.timeout.connect(self.check_mouse_movement)
        self.last_mouse_pos = QCursor.pos()
        self.is_mouse_monitoring = False
        
        # Timer for mouse lock activation delay
        self.mouse_activation_timer = QTimer(self)
        self.mouse_activation_timer.setSingleShot(True)
        self.mouse_activation_timer.timeout.connect(self.start_mouse_monitoring)

        # Internet monitoring
        self.internet_timer = QTimer(self)
        self.internet_timer.timeout.connect(self.check_internet_status)
        self.is_internet_monitoring = False
        self.failed_internet_checks = 0
        
    def init_ui(self):
        self.setWindowTitle("Lock Scheduler")
        self.setGeometry(500, 250, 420, 520)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QWidget {
                background-color: #f5f5f5;
                color: #333333;
                font-family: 'Segoe UI', Arial;
            }
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                margin-top: 8px;
                padding: 10px;
                font-weight: 600;
                font-size: 11px;
                color: #0078d4;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton#dangerBtn {
                background-color: #d13438;
            }
            QPushButton#dangerBtn:hover {
                background-color: #a4373a;
            }
            QTimeEdit, QSpinBox {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 6px;
                color: #333333;
                font-size: 11px;
            }
            QTimeEdit::up-button, QSpinBox::up-button {
                background-color: transparent;
                border-radius: 3px;
                width: 20px;
            }
            QTimeEdit::down-button, QSpinBox::down-button {
                background-color: transparent;
                border-radius: 3px;
                width: 20px;
            }
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 6px;
                color: #333333;
                font-size: 10px;
            }
            QListWidget::item {
                padding: 6px;
                border-radius: 3px;
                margin: 1px;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
            QLabel {
                font-size: 11px;
                color: #333333;
            }
            QTabWidget::pane {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                background-color: #ffffff;
            }
            QTabBar::tab {
                background-color: #f5f5f5;
                color: #666666;
                padding: 6px 14px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
                font-size: 10px;
                border: 1px solid #e0e0e0;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #0078d4;
                font-weight: 600;
                border-bottom: 2px solid #0078d4;
            }
        """)
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Header
        header = QLabel("Lock Scheduler")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 6px; color: #0078d4;")
        layout.addWidget(header)
        
        # Current time display
        self.time_label = QLabel()
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setStyleSheet("font-size: 12px; padding: 4px; color: #666666;")
        layout.addWidget(self.time_label)
        
        # Tab widget
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Tab 1: Specific Time
        tab1 = QWidget()
        tab1_layout = QVBoxLayout(tab1)
        tab1_layout.setSpacing(6)
        tab1_layout.setContentsMargins(8, 8, 8, 8)
        
        group1 = QGroupBox("Lock at Specific Time")
        group1_layout = QVBoxLayout()
        group1_layout.setSpacing(6)
        group1_layout.setContentsMargins(8, 8, 8, 8)
        
        time_row = QHBoxLayout()
        time_label = QLabel("Time:")
        time_label.setMinimumWidth(40)
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("hh:mm AP")
        self.time_edit.setTime(QTime.currentTime().addSecs(300))
        self.time_edit.setMaximumWidth(100)
        time_row.addWidget(time_label)
        time_row.addWidget(self.time_edit)
        time_row.addStretch()
        group1_layout.addLayout(time_row)
        
        self.check_int_tab1 = QCheckBox("Also lock if Internet is lost")
        self.check_int_tab1.setStyleSheet("font-size: 10px; color: #666666;")
        group1_layout.addWidget(self.check_int_tab1)

        btn1 = QPushButton("Schedule")
        btn1.clicked.connect(self.schedule_at_time)
        group1_layout.addWidget(btn1)
        
        group1.setLayout(group1_layout)
        tab1_layout.addWidget(group1)
        tab1_layout.addStretch()
        
        # Tab 2: Lock After Duration
        tab2 = QWidget()
        tab2_layout = QVBoxLayout(tab2)
        tab2_layout.setSpacing(6)
        tab2_layout.setContentsMargins(8, 8, 8, 8)
        
        group2 = QGroupBox("Lock After Duration")
        group2_layout = QVBoxLayout()
        group2_layout.setSpacing(6)
        group2_layout.setContentsMargins(8, 8, 8, 8)
        
        hours_row = QHBoxLayout()
        hours_row.addWidget(QLabel("H:"))
        self.hours_spin = QSpinBox()
        self.hours_spin.setRange(0, 23)
        self.hours_spin.setMaximumWidth(60)
        hours_row.addWidget(self.hours_spin)
        
        mins_row_label = QLabel("M:")
        mins_row_label.setMargin(0)
        hours_row.addWidget(mins_row_label)
        self.mins_spin = QSpinBox()
        self.mins_spin.setRange(0, 59)
        self.mins_spin.setValue(5)
        self.mins_spin.setMaximumWidth(60)
        hours_row.addWidget(self.mins_spin)
        
        secs_row_label = QLabel("S:")
        secs_row_label.setMargin(0)
        hours_row.addWidget(secs_row_label)
        self.secs_spin = QSpinBox()
        self.secs_spin.setRange(0, 59)
        self.secs_spin.setMaximumWidth(60)
        hours_row.addWidget(self.secs_spin)
        hours_row.addStretch()
        group2_layout.addLayout(hours_row)
        
        self.check_int_tab2 = QCheckBox("Also lock if Internet is lost")
        self.check_int_tab2.setStyleSheet("font-size: 10px; color: #666666;")
        group2_layout.addWidget(self.check_int_tab2)

        btn2 = QPushButton("Schedule")
        btn2.clicked.connect(self.schedule_after_duration)
        group2_layout.addWidget(btn2)
        
        group2.setLayout(group2_layout)
        tab2_layout.addWidget(group2)
        tab2_layout.addStretch()
        
        # Tab 3: Quick Lock
        tab3 = QWidget()
        tab3_layout = QVBoxLayout(tab3)
        tab3_layout.setSpacing(4)
        tab3_layout.setContentsMargins(8, 8, 8, 8)
        
        group3 = QGroupBox("Quick Actions")
        group3_layout = QVBoxLayout()
        group3_layout.setSpacing(4)
        group3_layout.setContentsMargins(8, 8, 8, 8)
        
        quick_btns = [
            ("1 Min", 60),
            ("5 Min", 300),
            ("15 Min", 900),
            ("30 Min", 1800),
            ("1 Hour", 3600)
        ]
        
        for text, secs in quick_btns:
            btn = QPushButton(text)
            btn.setMaximumHeight(28)
            btn.clicked.connect(lambda checked, s=secs: self.quick_lock(s))
            group3_layout.addWidget(btn)
        
        group3.setLayout(group3_layout)
        tab3_layout.addWidget(group3)
        
        immediate_btn = QPushButton("LOCK NOW")
        immediate_btn.setObjectName("dangerBtn")
        immediate_btn.setMaximumHeight(32)
        immediate_btn.setStyleSheet("""
            QPushButton#dangerBtn {
                background-color: #d13438;
                font-weight: bold;
            }
            QPushButton#dangerBtn:hover {
                background-color: #a4373a;
            }
        """)
        immediate_btn.clicked.connect(self.lock_now)
        tab3_layout.addWidget(immediate_btn)
        tab3_layout.addStretch()
        
        tabs.addTab(tab1, "Specific Time")
        tabs.addTab(tab2, "Duration")
        tabs.addTab(tab3, "Quick")
        
        # Tab 4: Mouse Lock
        tab4 = QWidget()
        tab4_layout = QVBoxLayout(tab4)
        tab4_layout.setSpacing(6)
        tab4_layout.setContentsMargins(8, 8, 8, 8)

        group4 = QGroupBox("Lock on Mouse Movement")
        group4_layout = QVBoxLayout()
        group4_layout.setSpacing(6)
        group4_layout.setContentsMargins(8, 8, 8, 8)

        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Activation Delay (sec):"))
        self.mouse_delay_spin = QSpinBox()
        self.mouse_delay_spin.setRange(0, 600)
        self.mouse_delay_spin.setValue(5)
        delay_layout.addWidget(self.mouse_delay_spin)
        group4_layout.addLayout(delay_layout)
 
        self.check_int_tab4 = QCheckBox("Also lock if Internet is lost")
        self.check_int_tab4.setStyleSheet("font-size: 10px; color: #666666;")
        group4_layout.addWidget(self.check_int_tab4)

        self.mouse_lock_status = QLabel("Status: Inactive")
        group4_layout.addWidget(self.mouse_lock_status)

        self.toggle_mouse_lock_btn = QPushButton("Activate Mouse Lock")
        self.toggle_mouse_lock_btn.setCheckable(True)
        self.toggle_mouse_lock_btn.clicked.connect(self.toggle_mouse_lock)
        group4_layout.addWidget(self.toggle_mouse_lock_btn)

        group4.setLayout(group4_layout)
        tab4_layout.addWidget(group4)
        tab4_layout.addStretch()
        
        tabs.addTab(tab4, "Mouse Lock")
        
        # Tab 5: Internet Lock
        tab5 = QWidget()
        tab5_layout = QVBoxLayout(tab5)
        tab5_layout.setSpacing(6)
        tab5_layout.setContentsMargins(8, 8, 8, 8)

        group5 = QGroupBox("Lock on Internet Loss")
        group5_layout = QVBoxLayout()
        group5_layout.setSpacing(10)
        group5_layout.setContentsMargins(8, 8, 8, 8)

        desc_label = QLabel("Locks the device immediately if internet connection is lost.\n"
                            "Interval: 1s | Grace: 2s")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666666; font-style: italic;")
        group5_layout.addWidget(desc_label)

        self.internet_lock_status = QLabel("Status: Inactive")
        self.internet_lock_status.setStyleSheet("font-weight: bold;")
        group5_layout.addWidget(self.internet_lock_status)

        self.internet_conn_label = QLabel("Connection: Checking...")
        group5_layout.addWidget(self.internet_conn_label)

        self.toggle_internet_lock_btn = QPushButton("Activate Internet Lock")
        self.toggle_internet_lock_btn.setCheckable(True)
        self.toggle_internet_lock_btn.clicked.connect(self.toggle_internet_lock)
        group5_layout.addWidget(self.toggle_internet_lock_btn)

        group5.setLayout(group5_layout)
        tab5_layout.addWidget(group5)
        tab5_layout.addStretch()

        tabs.addTab(tab5, "Internet Lock")
        
        # Scheduled locks list - Compact
        group_list = QGroupBox("Scheduled Locks")
        list_layout = QVBoxLayout()
        list_layout.setSpacing(6)
        list_layout.setContentsMargins(8, 8, 8, 8)
        
        self.lock_list = QListWidget()
        self.lock_list.setMaximumHeight(100)
        list_layout.addWidget(self.lock_list)
        
        clear_btn = QPushButton("Clear All")
        clear_btn.setObjectName("dangerBtn")
        clear_btn.setMaximumHeight(28)
        clear_btn.clicked.connect(self.clear_all)
        list_layout.addWidget(clear_btn)
        
        group_list.setLayout(list_layout)
        layout.addWidget(group_list)
        
        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_time_display)
        self.update_timer.start(1000)
        self.update_time_display()
        
    def update_time_display(self):
        now = datetime.now()
        self.time_label.setText(f"Current Time: {now.strftime('%I:%M:%S %p')}")
        
    def lock_device(self):
        try:
            ctypes.windll.user32.LockWorkStation()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to lock device: {str(e)}")
            
    def schedule_at_time(self):
        selected = self.time_edit.time()
        now = datetime.now()
        target = datetime(now.year, now.month, now.day, 
                         selected.hour(), selected.minute(), selected.second())
        
        if target <= now:
            target += timedelta(days=1)
            
        delta = (target - now).total_seconds()
        
        if delta < 0:
            QMessageBox.warning(self, "Invalid Time", "Selected time is in the past!")
            return
            
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(self.lock_device)
        timer.start(int(delta * 1000))
        
        if self.check_int_tab1.isChecked():
            self.toggle_internet_lock_btn.setChecked(True)
            self.toggle_internet_lock()

        self.timers.append(timer)
        lock_info = f"🕐 {target.strftime('%I:%M:%S %p')} - Specific Time"
        self.lock_list.addItem(lock_info)
        self.scheduled_locks.append((timer, lock_info))
        
        QMessageBox.information(self, "Scheduled", 
                               f"Device will lock at {target.strftime('%I:%M:%S %p')}")
        
    def schedule_after_duration(self):
        h = self.hours_spin.value()
        m = self.mins_spin.value()
        s = self.secs_spin.value()
        
        total_secs = h * 3600 + m * 60 + s
        
        if total_secs <= 0:
            QMessageBox.warning(self, "Invalid Duration", "Duration must be greater than 0!")
            return
            
        self.schedule_lock_after_seconds(total_secs)
        
    def quick_lock(self, secs):
        self.schedule_lock_after_seconds(secs)
        
    def schedule_lock_after_seconds(self, secs):
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(self.lock_device)
        timer.start(secs * 1000)
        
        # Check from tab 2 or Quick buttons
        should_int_lock = self.check_int_tab2.isChecked()
        if should_int_lock:
            self.toggle_internet_lock_btn.setChecked(True)
            self.toggle_internet_lock()

        lock_time = datetime.now() + timedelta(seconds=secs)
        
        self.timers.append(timer)
        
        if secs < 60:
            duration_str = f"{secs} seconds"
        elif secs < 3600:
            duration_str = f"{secs // 60} minutes"
        else:
            duration_str = f"{secs // 3600} hours {(secs % 3600) // 60} minutes"
            
        lock_info = f"⏱️ {lock_time.strftime('%I:%M:%S %p')} - After {duration_str}"
        self.lock_list.addItem(lock_info)
        self.scheduled_locks.append((timer, lock_info))
        
        QMessageBox.information(self, "Scheduled", 
                               f"Device will lock in {duration_str}\nAt: {lock_time.strftime('%I:%M:%S %p')}")
        
    def lock_now(self):
        reply = QMessageBox.question(self, "Confirm Lock", 
                                    "Lock device immediately?",
                                    QMessageBox.StandardButton.Yes | 
                                    QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.lock_device()
            
    def clear_all(self):
        for timer, _ in self.scheduled_locks:
            timer.stop()
        self.timers.clear()
        self.scheduled_locks.clear()
        self.lock_list.clear()
        QMessageBox.information(self, "Cleared", "All schedules cleared!")
        
    def toggle_mouse_lock(self):
        if self.toggle_mouse_lock_btn.isChecked():
            delay = self.mouse_delay_spin.value()
            if delay > 0:
                self.mouse_activation_timer.start(delay * 1000)
                self.mouse_lock_status.setText(f"Status: Activating in {delay} seconds...")
                self.toggle_mouse_lock_btn.setText("Cancel Activation")
                self.mouse_delay_spin.setEnabled(False)
            else:
                self.start_mouse_monitoring()
            
            if self.check_int_tab4.isChecked():
                self.toggle_internet_lock_btn.setChecked(True)
                self.toggle_internet_lock()
        else:
            self.mouse_activation_timer.stop()
            self.is_mouse_monitoring = False
            self.mouse_monitor_timer.stop()
            self.mouse_lock_status.setText("Status: Inactive")
            self.toggle_mouse_lock_btn.setText("Activate Mouse Lock")
            self.mouse_delay_spin.setEnabled(True)

    def start_mouse_monitoring(self):
        if not self.toggle_mouse_lock_btn.isChecked():
            return 
        self.is_mouse_monitoring = True
        self.last_mouse_pos = QCursor.pos()
        self.mouse_monitor_timer.start(100)  # Check every 100ms
        self.mouse_lock_status.setText("Status: Active - Monitoring...")
        self.toggle_mouse_lock_btn.setText("Deactivate Mouse Lock")
        self.mouse_delay_spin.setEnabled(False)

    def check_mouse_movement(self):
        if self.is_mouse_monitoring:
            current_pos = QCursor.pos()
            if current_pos != self.last_mouse_pos:
                self.lock_device()
                self.toggle_mouse_lock_btn.setChecked(False)
                self.toggle_mouse_lock() # Reset the button and status

    def is_internet_available(self):
        try:
            # Try to connect to Google DNS
            socket.create_connection(("8.8.8.8", 53), timeout=1)
            return True
        except (socket.timeout, socket.error):
            return False

    def toggle_internet_lock(self):
        if self.toggle_internet_lock_btn.isChecked():
            self.is_internet_monitoring = True
            self.failed_internet_checks = 0
            self.internet_timer.start(1000) # Check every 1s
            self.internet_lock_status.setText("Status: Active - Monitoring...")
            self.toggle_internet_lock_btn.setText("Deactivate Internet Lock")
        else:
            self.is_internet_monitoring = False
            self.internet_timer.stop()
            self.internet_lock_status.setText("Status: Inactive")
            self.toggle_internet_lock_btn.setText("Activate Internet Lock")
            self.internet_conn_label.setText("Connection: Unknown")

    def check_internet_status(self):
        if not self.is_internet_monitoring:
            return

        available = self.is_internet_available()
        
        if available:
            self.failed_internet_checks = 0
            self.internet_conn_label.setText("Connection: Online")
            self.internet_conn_label.setStyleSheet("color: green;")
        else:
            self.failed_internet_checks += 1
            self.internet_conn_label.setText(f"Connection: Offline ({self.failed_internet_checks}s)")
            self.internet_conn_label.setStyleSheet("color: red;")
            
            if self.failed_internet_checks >= 2: # 2 seconds grace
                self.lock_device()
                # Deactivate after successful lock as per user request
                self.toggle_internet_lock_btn.setChecked(False)
                self.toggle_internet_lock()
        
def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = LockScheduler()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()