from __future__ import annotations

import sys
import time
from typing import Tuple

import psutil
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QFont, QColor, QPainter, QPaintEvent, QPixmap
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QHBoxLayout, QVBoxLayout, QPushButton


def human_speed(bytes_per_sec: float) -> str:
    """Convert bytes/sec to human-readable string."""
    units = ["B/s", "KB/s", "MB/s", "GB/s"]
    v = float(bytes_per_sec)
    i = 0
    while v >= 1024 and i < len(units) - 1:
        v /= 1024.0
        i += 1
    return f"{v:5.1f} {units[i]}"


class NetOverlay(QWidget):
    def __init__(self, refresh_ms: int = 500):
        super().__init__()
        self.refresh_ms = refresh_ms
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, False)
        self.setWindowTitle("Net Overlay")

        self.drag_pos: QPoint | None = None

        # UI
        self.download_label = QLabel("↓ 0.0 B/s")
        self.upload_label = QLabel("↑ 0.0 B/s")
        self.title_label = QLabel("Internet Speed")

        # Styling
        font_big = QFont("Segoe UI", 10, QFont.Weight.Bold)
        font_small = QFont("Segoe UI", 9)

        self.title_label.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        self.download_label.setFont(font_big)
        self.upload_label.setFont(font_big)

        self.download_label.setStyleSheet("color: #00d4ff;")
        self.upload_label.setStyleSheet("color: #ff8c00;")
        self.title_label.setStyleSheet("color: #ffffff; opacity: 0.9;")

        # Buttons (pin/close)
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.setStyleSheet(
            "QPushButton{color:#fff; background:transparent; border:0;} QPushButton::hover{color:#ff6b6b;}"
        )
        self.close_btn.clicked.connect(self.close)

        header_layout = QHBoxLayout()
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.close_btn)
        header_layout.setContentsMargins(8, 4, 8, 0)

        body_layout = QHBoxLayout()
        body_layout.addWidget(self.download_label)
        body_layout.addSpacing(12)
        body_layout.addWidget(self.upload_label)
        body_layout.setContentsMargins(8, 2, 8, 8)

        main_layout = QVBoxLayout()
        main_layout.addLayout(header_layout)
        main_layout.addLayout(body_layout)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(main_layout)

        self.resize(180, 64)

        # Tracking counters
        self._last_counters = psutil.net_io_counters()
        self._last_time = time.time()

        # Timer for updates
        self.timer = QTimer(self)
        self.timer.setInterval(self.refresh_ms)
        self.timer.timeout.connect(self.update_speeds)
        self.timer.start()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # draw rounded translucent background
        rect = self.rect().adjusted(0, 0, -1, -1)
        bg = QColor(18, 18, 20, 200)
        painter.setBrush(bg)
        painter.setPen(QColor(255, 255, 255, 15))
        painter.drawRoundedRect(rect, 10, 10)

    def update_speeds(self) -> None:
        now = time.time()
        counters = psutil.net_io_counters()
        dt = max(now - self._last_time, 1e-6)
        sent = (counters.bytes_sent - self._last_counters.bytes_sent) / dt
        recv = (counters.bytes_recv - self._last_counters.bytes_recv) / dt

        self.download_label.setText(f"↓ {human_speed(recv)}")
        self.upload_label.setText(f"↑ {human_speed(sent)}")

        self._last_counters = counters
        self._last_time = now

    # Draggable behavior
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_pos = None
        event.accept()


def main():
    app = QApplication(sys.argv)
    overlay = NetOverlay(refresh_ms=500)
    # Place overlay near top-right corner
    screen = app.primaryScreen().availableGeometry()
    overlay.move(screen.right() - overlay.width() - 20, screen.top() + 20)
    overlay.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
