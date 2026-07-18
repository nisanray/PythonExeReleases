import sys
import os
import shutil
import re
import json
import platform
import subprocess
import time
import traceback
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

_missing = []

try:
    import yt_dlp
except ImportError:
    _missing.append("yt-dlp")

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QLineEdit, QPushButton, QComboBox, QProgressBar,
        QTextEdit, QFileDialog, QMessageBox, QFrame, QSizePolicy,
        QScrollArea, QSpacerItem, QToolButton, QStatusBar,
        QListWidget, QListWidgetItem, QSystemTrayIcon, QMenu, QStyle,
        QStackedWidget, QCheckBox, QSlider, QSplitter, QAbstractItemView,
        QGraphicsDropShadowEffect
    )
    from PyQt6.QtCore import (
        QThread, pyqtSignal, Qt, QSize, QPropertyAnimation,
        QEasingCurve, QTimer, QPoint, QUrl, QSettings
    )
    from PyQt6.QtGui import (
        QFont, QIcon, QColor, QPalette, QPixmap, QFontDatabase, QPainter,
        QCursor, QDesktopServices
    )
except ImportError:
    _missing.append("PyQt6")

if _missing:
    print("=" * 60)
    print("ERROR: Missing required packages:")
    for pkg in _missing:
        print(f"  • {pkg}")
    print("\nInstall them with:")
    print(f"  pip install {' '.join(_missing)}")
    print("=" * 60)
    sys.exit(1)


def setup_logger():
    log_file = Path(__file__).resolve().parent / "mediatube_debug.log"
    logger = logging.getLogger("MediaTube")
    logger.setLevel(logging.DEBUG)
    
    if not logger.handlers:
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s | %(levelname)-7s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger, log_file

app_logger, _APP_LOG_FILE = setup_logger()

def global_exception_handler(exctype, value, tb):
    app_logger.error(f"Uncaught Exception: {exctype.__name__}: {value}")
    app_logger.error("".join(traceback.format_exception(exctype, value, tb)))
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = global_exception_handler


class URLValidator:
    SUPPORTED_PATTERNS = [
        r"https?://(www\.)?youtube\.com/",
        r"https?://youtu\.be/",
        r"https?://(www\.)?vimeo\.com/",
        r"https?://(www\.)?twitch\.tv/",
        r"https?://(www\.)?dailymotion\.com/",
        r"https?://(music\.)?youtube\.com/",
        r"https?://(www\.)?soundcloud\.com/",
    ]

    @staticmethod
    def validate(url: str) -> tuple[bool, str]:
        url = url.strip()
        if not url:
            return False, "URL cannot be empty."
        if not url.startswith(("http://", "https://")):
            return False, "URL must start with http:// or https://"
        if len(url) > 2048:
            return False, "URL is too long."
        matched = any(re.match(p, url) for p in URLValidator.SUPPORTED_PATTERNS)
        if not matched:
            return True, "⚠ URL may not be from a supported site. Attempting anyway."
        return True, ""


class FFmpegValidator:
    @staticmethod
    def find_ffmpeg(hint_path: str = "") -> tuple[bool, str]:
        candidates = []
        if hint_path:
            candidates.append(hint_path)
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            candidates.append(os.path.dirname(system_ffmpeg))
        for path in candidates:
            if shutil.which("ffmpeg", path=path):
                return True, path
        return False, (
            "ffmpeg not found. It is required to merge high-quality video + audio.\n\n"
            "Install options:\n"
            "  • macOS:   brew install ffmpeg\n"
            "  • Windows: https://ffmpeg.org/download.html\n"
            "  • Linux:   sudo apt install ffmpeg"
        )

    @staticmethod
    def get_ffmpeg_version(path: str) -> str:
        try:
            exe = shutil.which("ffmpeg", path=path) or shutil.which("ffmpeg") or "ffmpeg"
            result = subprocess.run(
                [exe, "-version"],
                capture_output=True, text=True, timeout=5
            )
            first_line = result.stdout.split("\n")[0]
            match = re.search(r"version\s+([\d.]+)", first_line)
            return match.group(1) if match else "unknown"
        except Exception:
            return "unknown"


class DownloadWorker(QThread):
    progress_signal  = pyqtSignal(dict)
    log_signal       = pyqtSignal(str, str)
    finished_signal  = pyqtSignal(bool, str)
    stats_signal     = pyqtSignal(dict)

    def __init__(self, url, quality, output_folder, ffmpeg_path="",
                 audio_only=False, embed_subs=False, prefer_av1=False, concurrent_fragments=4):
        super().__init__()
        self.url            = url
        self.quality        = quality
        self.output_folder  = output_folder
        self.ffmpeg_path    = ffmpeg_path
        self.audio_only     = audio_only
        self.embed_subs     = embed_subs
        self.prefer_av1     = prefer_av1
        self.concurrent_fragments = concurrent_fragments
        self.is_cancelled   = False
        self._start_time    = None
        self._downloaded_bytes = 0
        self._file_count    = 0
        self._total_files   = 0
        self._errors        = []

    def build_format_string(self, quality_str: str) -> str:
        quality_str = quality_str.lower().strip()
        if self.audio_only or "audio" in quality_str:
            return "bestaudio/best"
        
        codec_pref = "av01" if self.prefer_av1 else "avc1"
        if "best" in quality_str:
            return f"bestvideo[vcodec^={codec_pref}]+bestaudio/bestvideo+bestaudio/best"
        
        # Safely extract height for exact targeting (Fixed regex bug)
        match = re.search(r"(\d+)p", quality_str)
        if match:
            height = int(match.group(1))
        elif "4k" in quality_str:
            height = 2160
        else:
            height = 1080 # Fallback
            
        return (
            f"bestvideo[height<={height}][vcodec^={codec_pref}]+bestaudio/"
            f"bestvideo[height<={height}]+bestaudio/"
            f"best[height<={height}]/"
            f"bestvideo+bestaudio/best"
        )

    def run(self):
        self._start_time = time.time()
        try:
            Path(self.output_folder).mkdir(parents=True, exist_ok=True)
        except PermissionError:
            self.finished_signal.emit(False, f"Permission denied creating directory:\n{self.output_folder}")
            return
        except OSError as e:
            self.finished_signal.emit(False, f"Failed to create directory:\n{e}")
            return

        format_selector = self.build_format_string(self.quality)
        self.log_signal.emit(f"Quality target : {self.quality}", "info")
        self.log_signal.emit(f"Output folder  : {self.output_folder}", "info")
        self.log_signal.emit(f"Format string  : {format_selector}", "info")
        if self.audio_only:
            self.log_signal.emit("Mode: Audio-only extraction", "info")
        if self.prefer_av1:
            self.log_signal.emit("Codec preference: AV1", "info")

        outer_self = self

        class GUILogger:
            def debug(self, msg): pass
            def warning(self, msg):
                outer_self._errors.append(msg)
                outer_self.log_signal.emit(msg, "warn")
            def error(self, msg):
                outer_self._errors.append(msg)
                outer_self.log_signal.emit(msg, "error")

        def progress_hook(d):
            if self.is_cancelled:
                raise Exception("__CANCELLED__")
            clean = {}
            for k, v in d.items():
                clean[k] = re.sub(r"\x1b\[[0-9;]*m", "", v) if isinstance(v, str) else v
            self.progress_signal.emit(clean)
            
            elapsed    = time.time() - self._start_time
            downloaded = clean.get("downloaded_bytes", 0) or 0
            total      = clean.get("total_bytes", 0) or clean.get("total_bytes_estimate", 0) or 0
            speed      = clean.get("speed", 0) or 0
            eta_sec    = (total - downloaded) / speed if speed and total else None
            eta_str    = str(timedelta(seconds=int(eta_sec))) if eta_sec else "—"
            
            self.stats_signal.emit({
                "elapsed":    str(timedelta(seconds=int(elapsed))),
                "eta":        eta_str,
                "speed":      self._fmt_bytes(speed) + "/s" if speed else "—",
                "downloaded": self._fmt_bytes(downloaded),
                "total":      self._fmt_bytes(total) if total else "—",
                "file_count": self._file_count,
                "errors":     len(self._errors),
            })

        def postprocessor_hook(d):
            if d["status"] == "started":
                self.log_signal.emit(f"Post-processing (Merging/Extracting) [{d.get('postprocessor', '')}]…", "info")
            elif d["status"] == "finished":
                self.log_signal.emit("Post-processing complete.", "info")
                self._file_count += 1

        out_template = os.path.join(
            self.output_folder,
            "%(playlist_title|.)s",
            "%(playlist_index|)s%(playlist_index& - |)s%(title)s.%(ext)s"
        )
        ydl_opts: dict = {
            "format":              format_selector,
            "outtmpl":             out_template,
            "ignoreerrors":        True,
            "retries":             5,
            "fragment_retries":    5,
            "retry_sleep_functions": {"http": lambda n: 2 ** n},
            "merge_output_format": "mkv" if not self.audio_only else None,
            "logger":              GUILogger(),
            "progress_hooks":      [progress_hook],
            "postprocessor_hooks": [postprocessor_hook],
            "nocolor":             True,
            "concurrent_fragment_downloads": self.concurrent_fragments,
        }
        if self.audio_only:
            ydl_opts["postprocessors"] = [{
                "key":             "FFmpegExtractAudio",
                "preferredcodec":  "mp3",
                "preferredquality": "320",
            }]
        else:
            ydl_opts["postprocessors"] = [{
                "key":            "FFmpegVideoConvertor",
                "preferedformat": "mkv",
            }]
            
        if self.embed_subs:
            ydl_opts["writesubtitles"] = True
            ydl_opts["subtitleslangs"] = ["en"]
            ydl_opts["embedsubtitles"] = True

        ok, ffmpeg_path = FFmpegValidator.find_ffmpeg(self.ffmpeg_path)
        if ok:
            ydl_opts["ffmpeg_location"] = ffmpeg_path
        else:
            self.log_signal.emit("ffmpeg not found — merging may fail.", "warn")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self.log_signal.emit("\nFetching info and starting download…", "info")
                error_count = ydl.download([self.url])
                if error_count and not self.is_cancelled:
                    self.log_signal.emit(f"{error_count} video(s) could not be downloaded (skipped).", "warn")
            if not self.is_cancelled:
                elapsed = str(timedelta(seconds=int(time.time() - self._start_time)))
                msg = (
                    f"Completed {self._file_count} file(s) in {elapsed}."
                    + (f"  {len(self._errors)} warning(s)." if self._errors else "")
                )
                self.finished_signal.emit(True, msg)
        except Exception as exc:
            tb = traceback.format_exc()
            if "__CANCELLED__" in str(exc):
                self.finished_signal.emit(False, "Download cancelled by user.")
            elif "Sign in to confirm" in str(exc) or "bot" in str(exc).lower():
                self.finished_signal.emit(False, "YouTube is asking for sign-in (bot check).\nTry passing cookies or using a different network.")
            elif "Private video" in str(exc):
                self.finished_signal.emit(False, "This video/playlist is private.")
            elif "HTTP Error 429" in str(exc):
                self.finished_signal.emit(False, "Rate-limited (HTTP 429). Wait a few minutes then try again.")
            elif "urlopen error" in str(exc) or "ConnectionReset" in str(exc):
                self.finished_signal.emit(False, "Network error. Check your internet connection and try again.")
            else:
                self.log_signal.emit(tb, "error")
                self.finished_signal.emit(False, f"Unexpected error:\n{exc}")

    def cancel(self):
        self.is_cancelled = True
        self.log_signal.emit("Cancellation requested…", "warn")

    @staticmethod
    def _fmt_bytes(b) -> str:
        if not b:
            return "0 B"
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if abs(b) < 1024:
                return f"{b:.1f} {unit}"
            b /= 1024
        return f"{b:.1f} PB"


C_PRIMARY            = "#0058bc"
C_PRIMARY_CONTAINER  = "#0070eb"
C_ON_PRIMARY         = "#ffffff"
C_ON_PRIMARY_CONT    = "#fefcff"
C_SURFACE            = "#f9f9fb"
C_SURFACE_LOWEST     = "#ffffff"
C_SURFACE_LOW        = "#f3f3f5"
C_SURFACE_CONT       = "#eeeef0"
C_SURFACE_HIGH       = "#e8e8ea"
C_SURFACE_HIGHEST    = "#e2e2e4"
C_ON_SURFACE         = "#1a1c1d"
C_ON_SURFACE_VAR     = "#414755"
C_OUTLINE            = "#717786"
C_OUTLINE_VAR        = "#c1c6d7"
C_ERROR              = "#ba1a1a"
C_ERROR_CONT         = "#ffdad6"
C_SUCCESS            = "#34C759"
C_WARN               = "#FF9500"
C_SECONDARY          = "#5d5e63"
C_SECONDARY_CONT     = "#e0dfe4"
C_TERTIARY_CONT      = "#c64f00"
C_ON_TERTIARY_CONT   = "#fffbff"
C_BG                 = "#f5f5f7"

ICON = {
    "brand": "play_circle",
    "sidebar_downloader": "download",
    "sidebar_history": "history",
    "sidebar_settings": "settings",
    "sidebar_logs": "terminal",
    "topbar_account": "account_circle",
    "topbar_help": "help",
    "topbar_search": "search",
    "topbar_menu": "menu",
    "queue_link": "link",
    "queue_status_active": "downloading",
    "queue_status_done": "done_all",
    "queue_status_error": "error",
    "queue_status_ok": "check_circle",
    "queue_status_waiting": "schedule",
    "queue_cancel": "close",
    "queue_pause": "pause",
    "queue_clear": "clear_all",
    "history_status_done": "check_circle",
    "history_status_error": "error",
    "history_filter": "filter_list",
    "history_clear": "delete_sweep",
    "history_prev": "chevron_left",
    "history_next": "chevron_right",
    "folder": "folder",
    "folder_open": "folder_open",
    "copy": "content_copy",
    "settings_general": "tune",
    "settings_video": "movie",
    "settings_advanced": "memory",
    "settings_appearance": "palette",
    "settings_upgrade": "workspace_premium",
    "logs_terminal": "terminal",
    "logs_clear": "delete_sweep",
    "logs_copy": "content_copy",
    "refresh": "refresh",
    "audio_file": "audio_file",
    "star": "star",
}

ICON_DIR = Path(__file__).resolve().parent / "icons"
_ICON_FILE_CACHE: dict[str, Optional[Path]] = {}

def _icon_key(name: str) -> str:
    return ICON.get(name, name)

def _icon_file(name: str) -> Optional[Path]:
    key = _icon_key(name)
    if key in _ICON_FILE_CACHE:
        return _ICON_FILE_CACHE[key]
    if not ICON_DIR.exists():
        _ICON_FILE_CACHE[key] = None
        return None
    candidates = sorted(ICON_DIR.glob(f"{key}*.svg"))
    if not candidates:
        _ICON_FILE_CACHE[key] = None
        return None
    exact = [path for path in candidates if path.stem == key or path.name.startswith(f"{key}_")]
    chosen = sorted(exact or candidates, key=lambda path: (len(path.name), path.name))[0]
    _ICON_FILE_CACHE[key] = chosen
    return chosen

def _icon_pixmap(name: str, size: int, color: str) -> QPixmap:
    path = _icon_file(name)
    r_size = size * 2
    if path:
        pixmap = QIcon(str(path)).pixmap(r_size, r_size)
        if not pixmap.isNull():
            if color:
                tinted = QPixmap(pixmap.size())
                tinted.fill(Qt.GlobalColor.transparent)
                painter = QPainter(tinted)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                painter.drawPixmap(0, 0, pixmap)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(tinted.rect(), QColor(color))
                painter.end()
                tinted.setDevicePixelRatio(2.0)
                return tinted
            else:
                pixmap.setDevicePixelRatio(2.0)
                return pixmap

    fallback = QPixmap(size * 2, size * 2)
    fallback.fill(Qt.GlobalColor.transparent)
    fallback.setDevicePixelRatio(2.0)
    return fallback

def _set_svg_label(label: QLabel, name: str, size: int, color: str):
    label.setPixmap(_icon_pixmap(name, size, color))

def _set_svg_button(button: QPushButton, name: str, size: int, color: str):
    button.setText("")
    button.setIcon(QIcon(_icon_pixmap(name, size, color)))
    button.setIconSize(QSize(size, size))

def _inter(size=13, weight=QFont.Weight.Normal) -> QFont:
    f = QFont()
    for name in ["Inter", "Segoe UI", "Helvetica Neue", "Arial"]:
        f.setFamily(name)
        if f.exactMatch():
            break
    f.setPointSize(size)
    f.setWeight(weight)
    return f

def _divider_h() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    line.setStyleSheet(f"background:{C_OUTLINE_VAR}; border:none;")
    return line

def _divider_v() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.VLine)
    line.setFixedWidth(1)
    line.setStyleSheet(f"background:{C_OUTLINE_VAR}; border:none;")
    return line


INPUT_STYLE = f"""
    QLineEdit, QComboBox {{
        background: {C_SURFACE_LOWEST};
        border: 1px solid {C_OUTLINE_VAR};
        border-radius: 6px;
        padding: 4px 8px;
        font-size: 13px;
        color: {C_ON_SURFACE};
        min-height: 26px;
    }}
    QLineEdit:focus, QComboBox:focus {{
        border-color: {C_PRIMARY};
        background: {C_SURFACE_LOWEST};
        outline: none;
    }}
    QLineEdit:read-only {{
        color: {C_ON_SURFACE_VAR};
        background: {C_SURFACE_LOW};
    }}
    QComboBox::drop-down {{ border: none; width: 20px; }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {C_ON_SURFACE_VAR};
        margin-right: 6px;
    }}
"""

SELECT_STYLE = f"""
    QComboBox {{
        background: {C_SURFACE_LOW};
        border: 1px solid {C_OUTLINE_VAR};
        border-radius: 6px;
        padding: 4px 8px;
        font-size: 13px;
        color: {C_ON_SURFACE};
        min-height: 26px;
    }}
    QComboBox:focus {{ border-color: {C_PRIMARY}; }}
    QComboBox::drop-down {{ border: none; width: 20px; }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {C_ON_SURFACE_VAR};
        margin-right: 6px;
    }}
    QComboBox QAbstractItemView {{
        background: {C_SURFACE_LOWEST};
        border: 1px solid {C_OUTLINE_VAR};
        selection-background-color: {C_SURFACE_HIGH};
        selection-color: {C_ON_SURFACE};
        outline: none;
    }}
"""

BTN_PRIMARY = f"""
    QPushButton {{
        background: {C_PRIMARY};
        color: {C_ON_PRIMARY};
        border: none;
        border-radius: 6px;
        padding: 4px 14px;
        font-size: 12px;
        font-weight: 500;
        min-height: 26px;
    }}
    QPushButton:hover  {{ background: #0066d6; }}
    QPushButton:pressed {{ background: #004ea8; }}
    QPushButton:disabled {{ background: {C_OUTLINE_VAR}; color: {C_ON_SURFACE_VAR}; }}
"""

BTN_SECONDARY = f"""
    QPushButton {{
        background: {C_SURFACE_LOWEST};
        color: {C_ON_SURFACE};
        border: 1px solid {C_OUTLINE_VAR};
        border-radius: 6px;
        padding: 4px 12px;
        font-size: 12px;
        font-weight: 500;
        min-height: 26px;
    }}
    QPushButton:hover  {{ background: {C_SURFACE_HIGH}; }}
    QPushButton:pressed {{ background: {C_SURFACE_HIGHEST}; }}
    QPushButton:disabled {{ color: {C_ON_SURFACE_VAR}; }}
"""

BTN_DANGER = f"""
    QPushButton {{
        background: {C_SURFACE_LOWEST};
        color: {C_ERROR};
        border: 1px solid {C_OUTLINE_VAR};
        border-radius: 6px;
        padding: 4px 12px;
        font-size: 12px;
        font-weight: 500;
        min-height: 26px;
    }}
    QPushButton:hover  {{ background: {C_ERROR_CONT}; border-color: {C_ERROR}; }}
    QPushButton:pressed {{ background: #ffb4ab; }}
"""

BTN_ICON = f"""
    QPushButton {{
        background: transparent;
        color: {C_ON_SURFACE_VAR};
        border: none;
        border-radius: 4px;
        padding: 4px;
        font-size: 12px;
        min-width: 28px;
        min-height: 28px;
    }}
    QPushButton:hover  {{ background: {C_SURFACE_HIGH}; color: {C_ON_SURFACE}; }}
    QPushButton:pressed {{ background: {C_SURFACE_HIGHEST}; }}
"""

CHECKBOX_STYLE = f"""
    QCheckBox {{
        color: {C_ON_SURFACE};
        font-size: 13px;
        spacing: 6px;
    }}
    QCheckBox::indicator {{
        width: 16px; height: 16px;
        border: 1px solid {C_OUTLINE_VAR};
        border-radius: 4px;
        background: {C_SURFACE_LOW};
    }}
    QCheckBox::indicator:checked {{
        background: {C_PRIMARY};
        border-color: {C_PRIMARY};
    }}
    QCheckBox:hover {{ color: {C_PRIMARY}; }}
"""


class SideNavItem(QPushButton):
    def __init__(self, icon_name: str, label: str, parent=None):
        super().__init__(parent)
        self._icon_name = icon_name
        self._label = label
        self.setCheckable(True)
        self.setFixedHeight(44)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._icon_lbl = QLabel()
        self._icon_lbl.setFixedSize(24, 24)
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._text_lbl = QLabel(label)
        self._text_lbl.setFont(_inter(12, QFont.Weight.Medium))
        self._text_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(self._icon_lbl)
        layout.addWidget(self._text_lbl)
        layout.addStretch()

        self._update_style(False)
        self.toggled.connect(self._update_style)

    def _update_style(self, checked: bool):
        if checked:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {C_PRIMARY_CONTAINER};
                    color: {C_ON_PRIMARY_CONT};
                    border: none;
                    border-radius: 10px;
                    font-weight: 600;
                }}
            """)
            _set_svg_label(self._icon_lbl, self._icon_name, 20, C_ON_PRIMARY_CONT)
            self._icon_lbl.setStyleSheet("background: transparent; border: none;")
            self._text_lbl.setStyleSheet(f"color: {C_ON_PRIMARY_CONT}; background: transparent; border: none;")
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {C_ON_SURFACE_VAR};
                    border: none;
                    border-radius: 10px;
                }}
                QPushButton:hover {{
                    background: {C_SURFACE_HIGHEST};
                    color: {C_ON_SURFACE};
                }}
            """)
            _set_svg_label(self._icon_lbl, self._icon_name, 20, C_ON_SURFACE_VAR)
            self._icon_lbl.setStyleSheet("background: transparent; border: none;")
            self._text_lbl.setStyleSheet(f"color: {C_ON_SURFACE_VAR}; background: transparent; border: none;")


class QueueRow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet(f"""
            QWidget {{
                background: {C_SURFACE_LOWEST};
                border-bottom: 1px solid {C_OUTLINE_VAR};
            }}
            QWidget:hover {{ background: rgba(0,88,188,0.03); }}
        """)

        h = QHBoxLayout(self)
        h.setContentsMargins(16, 0, 16, 0)
        h.setSpacing(16)

        self.status_lbl = QLabel()
        self.status_lbl.setFixedWidth(32)
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet("background: transparent; border: none;")
        _set_svg_label(self.status_lbl, ICON["queue_status_waiting"], 18, C_OUTLINE_VAR)

        name_col = QVBoxLayout()
        name_col.setSpacing(2)
        self.filename_lbl = QLabel("Ready to download")
        self.filename_lbl.setFont(_inter(12, QFont.Weight.Medium))
        self.filename_lbl.setStyleSheet(f"color: {C_ON_SURFACE}; background: transparent; border: none;")
        self.meta_lbl = QLabel("Waiting…")
        self.meta_lbl.setFont(_inter(10))
        self.meta_lbl.setStyleSheet(f"color: {C_ON_SURFACE_VAR}; background: transparent; border: none;")
        name_col.addWidget(self.filename_lbl)
        name_col.addWidget(self.meta_lbl)

        prog_col = QVBoxLayout()
        prog_col.setSpacing(3)
        self.pct_lbl = QLabel("—")
        self.pct_lbl.setFont(_inter(12, QFont.Weight.Medium))
        self.pct_lbl.setStyleSheet(f"color: {C_ON_SURFACE}; background: transparent; border: none;")
        self.pct_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.mini_bar = QProgressBar()
        self.mini_bar.setFixedHeight(4)
        self.mini_bar.setTextVisible(False)
        self.mini_bar.setValue(0)
        self.mini_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {C_SURFACE_HIGHEST};
                border-radius: 2px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: {C_PRIMARY};
                border-radius: 2px;
            }}
        """)
        prog_col.addWidget(self.pct_lbl)
        prog_col.addWidget(self.mini_bar)

        self.speed_lbl = QLabel("—")
        self.speed_lbl.setFixedWidth(120)
        self.speed_lbl.setFont(_inter(11))
        self.speed_lbl.setStyleSheet(f"color: {C_ON_SURFACE}; background: transparent; border: none;")
        self.speed_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.action_btn = QPushButton()
        self.action_btn.setFixedSize(28, 28)
        self.action_btn.setStyleSheet(BTN_ICON)
        self.action_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        _set_svg_button(self.action_btn, ICON["queue_cancel"], 16, C_ON_SURFACE_VAR)

        prog_w = QWidget()
        prog_w.setFixedWidth(120)
        prog_w.setLayout(prog_col)
        prog_w.setStyleSheet("background: transparent; border: none;")

        h.addWidget(self.status_lbl)
        h.addLayout(name_col, stretch=1)
        h.addWidget(prog_w)
        h.addWidget(self.speed_lbl)
        h.addWidget(self.action_btn)

    def set_active(self, filename: str, pct: int, speed: str, eta: str, meta: str = ""):
        _set_svg_label(self.status_lbl, ICON["queue_status_active"], 18, C_PRIMARY)
        self.filename_lbl.setText(filename[:55] + "…" if len(filename) > 55 else filename)
        self.meta_lbl.setText(meta or "Downloading…")
        self.pct_lbl.setText(f"{pct}%")
        self.mini_bar.setValue(pct)
        self.speed_lbl.setText(f"{speed}\n{eta} rem")
        self.setStyleSheet(f"""
            QWidget {{
                background: rgba(0,88,188,0.03);
                border-bottom: 1px solid {C_OUTLINE_VAR};
            }}
        """)

    def set_done(self, filename: str, meta: str = ""):
        _set_svg_label(self.status_lbl, ICON["queue_status_done"], 18, C_SUCCESS)
        self.filename_lbl.setText(filename[:55] + "…" if len(filename) > 55 else filename)
        self.meta_lbl.setText(meta or "Completed")
        self.pct_lbl.setText("100%")
        self.mini_bar.setValue(100)
        self.mini_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {C_SURFACE_HIGHEST};
                border-radius: 2px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: {C_SUCCESS};
                border-radius: 2px;
            }}
        """)
        self.speed_lbl.setText("Done")
        _set_svg_button(self.action_btn, ICON["folder_open"], 16, C_ON_SURFACE_VAR)
        self.setStyleSheet(f"""
            QWidget {{
                background: {C_SURFACE_LOWEST};
                border-bottom: 1px solid {C_OUTLINE_VAR};
                opacity: 0.8;
            }}
            QWidget:hover {{ background: {C_SURFACE_LOW}; }}
        """)

    def set_error(self, filename: str, msg: str = ""):
        _set_svg_label(self.status_lbl, ICON["queue_status_error"], 18, C_ERROR)
        self.filename_lbl.setText(filename[:55] + "…" if len(filename) > 55 else filename)
        self.meta_lbl.setText(msg or "Error")
        self.pct_lbl.setText("—")
        self.mini_bar.setValue(0)
        self.speed_lbl.setText("—")


class HistoryRow(QWidget):
    open_folder_requested = pyqtSignal(str)
    reuse_requested       = pyqtSignal(dict)

    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.setFixedHeight(52)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setStyleSheet(f"""
            QWidget {{
                background: {C_SURFACE_LOWEST};
                border-bottom: 1px solid rgba(193,198,215,0.3);
            }}
            QWidget:hover {{ background: rgba(0,88,188,0.04); }}
        """)

        h = QHBoxLayout(self)
        h.setContentsMargins(16, 0, 16, 0)
        h.setSpacing(16)

        status_lbl = QLabel()
        status_lbl.setFixedWidth(40)
        status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_lbl.setStyleSheet("background: transparent; border: none;")
        _set_svg_label(status_lbl, ICON["history_status_done"], 18, C_SUCCESS)

        name_col = QVBoxLayout()
        name_col.setSpacing(2)
        url = entry.get("url", "")
        url_type = entry.get("url_type", "other")
        quality = entry.get("quality", "")
        ts = entry.get("timestamp", "")
        folder = entry.get("folder", "")
        title_text = entry.get("title", "") or url

        try:
            host = urlparse(url).netloc.replace("www.", "") or url[:40]
        except Exception:
            host = url[:40]
        short_path = url.split("v=")[-1][:12] if "v=" in url else ""
        subtitle = f"{host}/{short_path}" if short_path else host

        domain_colors = {
            "youtube": ("#FF0000", "Y", "YouTube"),
            "vimeo": ("#1AB7EA", "V", "Vimeo"),
            "twitch": ("#9146FF", "T", "Twitch"),
            "dailymotion": ("#0066DC", "D", "Dailymotion"),
            "soundcloud": ("#FF5500", "S", "Soundcloud"),
            "other": (C_SURFACE_HIGH, "🔗", "Link")
        }
        bg_color, letter, tooltip = domain_colors.get(url_type, domain_colors["other"])
        txt_color = "#FFFFFF" if url_type != "other" else C_ON_SURFACE_VAR

        thumb = QLabel(letter)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setFont(_inter(16, QFont.Weight.Bold))
        thumb.setToolTip(tooltip)
        thumb.setFixedSize(48, 32)
        thumb.setStyleSheet(f"""
            background: {bg_color};
            color: {txt_color};
            border-radius: 6px;
            border: 1px solid {C_OUTLINE_VAR if url_type == 'other' else bg_color};
        """)

        title_lbl = QLabel(title_text[:65] + "…" if len(title_text) > 65 else title_text)
        title_lbl.setFont(_inter(12, QFont.Weight.Medium))
        title_lbl.setStyleSheet(f"color: {C_ON_SURFACE}; background: transparent; border: none;")
        
        sub_lbl = QLabel(subtitle)
        sub_lbl.setFont(_inter(10))
        sub_lbl.setStyleSheet(f"color: {C_ON_SURFACE_VAR}; background: transparent; border: none;")
        
        name_col.addWidget(title_lbl)
        name_col.addWidget(sub_lbl)

        is_audio = "mp3" in quality.lower() or "audio" in quality.lower()
        badge_bg  = C_TERTIARY_CONT    if is_audio else C_PRIMARY_CONTAINER
        badge_fg  = C_ON_TERTIARY_CONT if is_audio else C_ON_PRIMARY_CONT
        badge = QLabel(quality)
        badge.setFont(_inter(10, QFont.Weight.Medium))
        badge.setStyleSheet(f"""
            background: {badge_bg};
            color: {badge_fg};
            border-radius: 4px;
            padding: 2px 0px;
        """)
        badge.setFixedSize(96, 24)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        format_w = QWidget()
        format_w.setFixedWidth(110)
        flay = QVBoxLayout(format_w)
        flay.setContentsMargins(0, 0, 0, 0)
        flay.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        flay.addWidget(badge)
        format_w.setStyleSheet("background: transparent; border: none;")

        date_lbl = QLabel(ts[:16] if ts else "")
        date_lbl.setFont(_inter(11))
        date_lbl.setStyleSheet(f"color: {C_ON_SURFACE_VAR}; background: transparent; border: none;")
        date_lbl.setFixedWidth(150)

        act_w = QWidget()
        act_w.setFixedWidth(80)
        act_lay = QHBoxLayout(act_w)
        act_lay.setContentsMargins(0, 0, 0, 0)
        act_lay.setSpacing(6)
        act_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        act_w.setStyleSheet("background: transparent; border: none;")

        copy_btn = QPushButton()
        copy_btn.setFixedSize(32, 32)
        copy_btn.setStyleSheet(BTN_ICON)
        copy_btn.setToolTip("Copy URL")
        _set_svg_button(copy_btn, ICON["copy"], 16, C_ON_SURFACE_VAR)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(url))

        open_btn = QPushButton()
        open_btn.setFixedSize(32, 32)
        open_btn.setStyleSheet(BTN_ICON)
        open_btn.setToolTip("Open Folder")
        _set_svg_button(open_btn, ICON["folder_open"], 16, C_ON_SURFACE_VAR)
        open_btn.clicked.connect(lambda: self.open_folder_requested.emit(folder))
        
        act_lay.addWidget(copy_btn)
        act_lay.addWidget(open_btn)

        thumb_name_h = QHBoxLayout()
        thumb_name_h.setSpacing(12)
        thumb_name_h.addWidget(thumb)
        thumb_name_h.addLayout(name_col, stretch=1)

        h.addWidget(status_lbl)
        h.addLayout(thumb_name_h, stretch=1)
        h.addWidget(format_w)
        h.addWidget(date_lbl)
        h.addWidget(act_w)

        self.mouseDoubleClickEvent = lambda e: self.reuse_requested.emit(entry)


class GlassCard(QWidget):
    def __init__(self, icon: str, title: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QWidget#GlassCard {{
                background: rgba(255,255,255,0.7);
                border: 1px solid {C_OUTLINE_VAR};
                border-radius: 12px;
            }}
        """)
        self.setObjectName("GlassCard")

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(8)
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(24, 24)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _set_svg_label(icon_lbl, icon, 22, C_PRIMARY)
        title_lbl = QLabel(title)
        title_lbl.setFont(_inter(18, QFont.Weight.DemiBold))
        title_lbl.setStyleSheet(f"color: {C_ON_SURFACE}; background: transparent; border: none;")
        header.addWidget(icon_lbl)
        header.addWidget(title_lbl)
        header.addStretch()

        self.content_v = QVBoxLayout()
        self.content_v.setSpacing(14)

        div = _divider_h()
        div.setStyleSheet(f"background: rgba(193,198,215,0.3); border: none;")

        v.addLayout(header)
        v.addWidget(div)
        v.addLayout(self.content_v)

    def add_widget(self, w: QWidget):
        self.content_v.addWidget(w)

    def add_layout(self, lay):
        self.content_v.addLayout(lay)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MediaTube Pro")
        self.setMinimumSize(960, 680)
        self.resize(1100, 720)
        self.worker: Optional[DownloadWorker] = None
        self._url_valid = False
        self._settings = QSettings("MediaTube", "MediaTubePro")
        self._quality_by_url_type: dict[str, str] = {}
        self._download_history: list[dict] = []
        self._last_url_type_applied = ""
        self._tray_icon: Optional[QSystemTrayIcon] = None
        self._tray_available = False
        self._current_url_for_download = ""
        self._current_filename = ""
        
        app_logger.info("MediaTube Pro starting...")

        self._apply_palette()
        self._init_ui()
        self._setup_tray()
        self._load_settings()
        self._check_ffmpeg_quietly()

    def _apply_palette(self):
        pal = QPalette()
        pal.setColor(QPalette.ColorRole.Window,     QColor(C_BG))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(C_ON_SURFACE))
        pal.setColor(QPalette.ColorRole.Base,       QColor(C_SURFACE_LOWEST))
        pal.setColor(QPalette.ColorRole.Text,       QColor(C_ON_SURFACE))
        pal.setColor(QPalette.ColorRole.Button,     QColor(C_SURFACE))
        pal.setColor(QPalette.ColorRole.ButtonText, QColor(C_ON_SURFACE))
        self.setPalette(pal)
        self.setStyleSheet(f"""
            QMainWindow {{ background: {C_BG}; }}
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{
                background: {C_SURFACE_LOW};
                width: 8px; border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {C_OUTLINE_VAR};
                border-radius: 4px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QToolTip {{
                background: #1e1e1e;
                color: #d4d4d4;
                border: none;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
            }}
        """)

    def _init_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        main_v = QVBoxLayout(root)
        main_v.setContentsMargins(0, 0, 0, 0)
        main_v.setSpacing(0)

        main_v.addWidget(self._build_topbar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())
        body.addWidget(_divider_v())

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_queue_panel())
        self._stack.addWidget(self._build_history_panel())
        self._stack.addWidget(self._build_settings_panel())
        self._stack.addWidget(self._build_logs_panel())
        self._stack.setCurrentIndex(0)
        body.addWidget(self._stack, stretch=1)

        body_w = QWidget()
        body_w.setLayout(body)
        body_w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_v.addWidget(body_w, stretch=1)

        main_v.addWidget(self._build_footer())

    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(56)
        bar.setStyleSheet(f"""
            QWidget {{
                background: rgba(249,249,251,0.92);
                border-bottom: 1px solid {C_OUTLINE_VAR};
            }}
        """)
        h = QHBoxLayout(bar)
        h.setContentsMargins(24, 0, 24, 0)
        h.setSpacing(12)

        brand_box = QWidget()
        brand_box.setStyleSheet("background: transparent; border: none;")
        brand_h = QHBoxLayout(brand_box)
        brand_h.setContentsMargins(0, 0, 0, 0)
        brand_h.setSpacing(12)

        brand_badge = QLabel()
        brand_badge.setFixedSize(36, 36)
        brand_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_badge.setStyleSheet(f"background: {C_PRIMARY_CONTAINER}; border-radius: 10px; border: none;")
        _set_svg_label(brand_badge, ICON["brand"], 22, C_ON_PRIMARY_CONT)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        brand_title = QLabel("MediaTube")
        brand_title.setFont(_inter(18, QFont.Weight.Black))
        brand_title.setStyleSheet(f"color: {C_ON_SURFACE}; background: transparent; border: none;")
        brand_sub = QLabel("v1.1.1")
        brand_sub.setFont(_inter(11))
        brand_sub.setStyleSheet(f"color: {C_ON_SURFACE_VAR}; background: transparent; border: none;")
        brand_text.addWidget(brand_title)
        brand_text.addWidget(brand_sub)

        brand_h.addWidget(brand_badge)
        brand_h.addLayout(brand_text)
        h.addWidget(brand_box)
        h.addStretch()

        self._topbar_ffmpeg = QLabel("ffmpeg checking…")
        self._topbar_ffmpeg.setFont(_inter(10, QFont.Weight.Medium))
        self._topbar_ffmpeg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._topbar_ffmpeg.setStyleSheet(f"""
            QLabel {{
                color: {C_ON_SURFACE_VAR};
                background: {C_SURFACE_LOWEST};
                border: 1px solid {C_OUTLINE_VAR};
                border-radius: 14px;
                padding: 4px 10px;
            }}
        """)

        search_wrap = QWidget()
        search_wrap.setFixedHeight(32)
        search_wrap.setStyleSheet(f"""
            QWidget {{
                background: {C_SURFACE_LOWEST};
                border: 1px solid {C_OUTLINE_VAR};
                border-radius: 16px;
            }}
        """)
        search_h = QHBoxLayout(search_wrap)
        search_h.setContentsMargins(10, 0, 12, 0)
        search_h.setSpacing(8)
        
        search_icon = QLabel()
        search_icon.setFixedSize(16, 16)
        search_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        search_icon.setStyleSheet("background: transparent; border: none;")
        _set_svg_label(search_icon, ICON["topbar_search"], 14, C_ON_SURFACE_VAR)
        
        self._topbar_search = QLineEdit()
        self._topbar_search.setPlaceholderText("Search downloads…")
        self._topbar_search.setFont(_inter(12))
        self._topbar_search.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                border: none;
                color: {C_ON_SURFACE};
                min-width: 220px;
            }}
            QLineEdit:focus {{ outline: none; }}
        """)
        search_h.addWidget(search_icon)
        search_h.addWidget(self._topbar_search)

        icon_style = f"""
            QPushButton {{
                background: {C_SURFACE_LOWEST};
                color: {C_ON_SURFACE_VAR};
                border: none;
                border-radius: 16px;
                min-width: 32px;
                max-width: 32px;
                min-height: 32px;
                max-height: 32px;
            }}
            QPushButton:hover {{ background: {C_SURFACE_HIGH}; color: {C_ON_SURFACE}; }}
        """
        self._topbar_account = QPushButton()
        self._topbar_account.setStyleSheet(icon_style)
        _set_svg_button(self._topbar_account, ICON["topbar_account"], 20, C_ON_SURFACE_VAR)
        self._topbar_help = QPushButton()
        self._topbar_help.setStyleSheet(icon_style)
        _set_svg_button(self._topbar_help, ICON["topbar_help"], 20, C_ON_SURFACE_VAR)

        h.addWidget(self._topbar_ffmpeg)
        h.addWidget(search_wrap)
        h.addWidget(self._topbar_account)
        h.addWidget(self._topbar_help)

        return bar

    def _build_sidebar(self) -> QWidget:
        side = QWidget()
        side.setFixedWidth(240)
        side.setStyleSheet(f"background: {C_SURFACE_CONT};")
        v = QVBoxLayout(side)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(10)

        brand_box = QWidget()
        brand_box.setStyleSheet("background: transparent; border: none;")
        brand_h = QHBoxLayout(brand_box)
        brand_h.setContentsMargins(0, 0, 0, 0)
        brand_h.setSpacing(12)

        badge = QLabel()
        badge.setFixedSize(40, 40)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(f"background: {C_PRIMARY_CONTAINER}; border-radius: 12px; border: none;")
        _set_svg_label(badge, ICON["brand"], 24, C_ON_PRIMARY_CONT)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        brand_lbl = QLabel("MediaTube")
        brand_lbl.setFont(_inter(17, QFont.Weight.Bold))
        brand_lbl.setStyleSheet(f"color: {C_ON_SURFACE}; background: transparent; border: none;")
        brand_sub = QLabel("V1.1.1")
        brand_sub.setFont(_inter(11))
        brand_sub.setStyleSheet(f"color: {C_ON_SURFACE_VAR}; background: transparent; border: none;")
        brand_text.addWidget(brand_lbl)
        brand_text.addWidget(brand_sub)

        brand_h.addWidget(badge)
        brand_h.addLayout(brand_text)
        v.addWidget(brand_box)

        self._nav_queue    = SideNavItem(ICON["sidebar_downloader"], "Downloader")
        self._nav_history  = SideNavItem(ICON["sidebar_history"], "History")
        self._nav_settings = SideNavItem(ICON["sidebar_settings"], "Settings")
        self._nav_logs     = SideNavItem(ICON["sidebar_logs"], "Logs")

        nav_items = [
            (self._nav_queue,    0),
            (self._nav_history,  1),
            (self._nav_settings, 2),
            (self._nav_logs,     3),
        ]
        for btn, idx in nav_items:
            btn.setChecked(idx == 0)
            btn.clicked.connect(lambda _, i=idx, b=btn: self._switch_tab(i))
            v.addWidget(btn)

        v.addStretch()

        pro_btn = QPushButton("⬆  Upgrade Pro")
        pro_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C_SURFACE_LOWEST};
                color: {C_PRIMARY};
                border: 1px solid {C_OUTLINE_VAR};
                border-radius: 10px;
                padding: 10px 12px;
                font-size: 12px;
                font-weight: 600;
                text-align: left;
            }}
            QPushButton:hover {{ background: {C_SURFACE_HIGH}; }}
        """)
        v.addWidget(pro_btn)
        return side

    def _switch_tab(self, index: int):
        self._stack.setCurrentIndex(index)
        nav_btns = [self._nav_queue, self._nav_history, self._nav_settings, self._nav_logs]
        for i, btn in enumerate(nav_btns):
            btn.setChecked(i == index)

    def _build_queue_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: {C_BG};")
        h = QHBoxLayout(panel)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        center = QWidget()
        center.setStyleSheet(f"background: {C_BG};")
        center_v = QVBoxLayout(center)
        center_v.setContentsMargins(24, 24, 24, 24)
        center_v.setSpacing(16)

        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        hdr_title = QLabel("Download Queue")
        hdr_title.setFont(_inter(18, QFont.Weight.DemiBold))
        hdr_title.setStyleSheet(f"color: {C_ON_SURFACE}; background: transparent;")
        hdr.addWidget(hdr_title)
        hdr.addStretch()

        pause_btn = QPushButton("Pause All")
        pause_btn.setStyleSheet(BTN_SECONDARY)
        pause_btn.setEnabled(False)
        _set_svg_button(pause_btn, ICON["queue_pause"], 16, C_ON_SURFACE_VAR)

        clear_finished_btn = QPushButton("Clear Finished")
        clear_finished_btn.setStyleSheet(BTN_SECONDARY)
        clear_finished_btn.clicked.connect(self._clear_finished_queue)
        _set_svg_button(clear_finished_btn, ICON["queue_clear"], 16, C_ON_SURFACE_VAR)
        
        hdr.addWidget(pause_btn)
        hdr.addWidget(clear_finished_btn)
        center_v.addLayout(hdr)

        url_card = QWidget()
        url_card.setStyleSheet(f"""
            QWidget {{
                background: {C_SURFACE_LOWEST};
                border: 1px solid {C_OUTLINE_VAR};
                border-radius: 8px;
            }}
        """)
        url_h = QHBoxLayout(url_card)
        url_h.setContentsMargins(12, 6, 8, 6)
        url_h.setSpacing(8)

        link_lbl = QLabel()
        link_lbl.setFixedSize(18, 18)
        link_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        link_lbl.setStyleSheet("background: transparent; border: none;")
        _set_svg_label(link_lbl, ICON["queue_link"], 16, C_ON_SURFACE_VAR)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste URL here…")
        self.url_input.setFont(_inter(13))
        self.url_input.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                border: none;
                color: {C_ON_SURFACE};
                font-size: 13px;
            }}
            QLineEdit:focus {{ border: none; outline: none; }}
        """)
        self.url_input.textChanged.connect(self._on_url_changed)

        self._url_indicator = QLabel()
        self._url_indicator.setFixedSize(18, 18)
        self._url_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._url_indicator.setStyleSheet("background: transparent; border: none;")
        _set_svg_label(self._url_indicator, ICON["queue_status_ok"], 16, C_OUTLINE_VAR)

        self._add_btn = QPushButton("Add to Queue")
        self._add_btn.setStyleSheet(BTN_PRIMARY)
        self._add_btn.clicked.connect(self._start_download)
        self._add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        url_h.addWidget(link_lbl)
        url_h.addWidget(self.url_input, stretch=1)
        url_h.addWidget(self._url_indicator)
        url_h.addWidget(self._add_btn)
        center_v.addWidget(url_card)

        self._url_hint = QLabel("")
        self._url_hint.setFont(_inter(10))
        self._url_hint.setStyleSheet(f"color: {C_WARN}; background: transparent;")
        center_v.addWidget(self._url_hint)

        queue_card = QWidget()
        queue_card.setStyleSheet(f"""
            QWidget {{
                background: {C_SURFACE_LOWEST};
                border: 1px solid {C_OUTLINE_VAR};
                border-radius: 8px;
            }}
        """)
        queue_v = QVBoxLayout(queue_card)
        queue_v.setContentsMargins(0, 0, 0, 0)
        queue_v.setSpacing(0)

        table_hdr = QWidget()
        table_hdr.setObjectName("QueueTableHeader")
        table_hdr.setFixedHeight(36)
        table_hdr.setStyleSheet(f"""
            QWidget#QueueTableHeader {{
                background: {C_SURFACE_LOW};
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                border-bottom: 1px solid {C_OUTLINE_VAR};
            }}
        """)
        th = QHBoxLayout(table_hdr)
        th.setContentsMargins(16, 0, 16, 0)
        th.setSpacing(16)

        for text, width in [("STATUS", 32), ("FILENAME", 0), ("PROGRESS", 120), ("SPEED", 120), ("ACTION", 80)]:
            lbl = QLabel(text)
            lbl.setFont(_inter(10, QFont.Weight.Medium))
            lbl.setStyleSheet(f"color: {C_ON_SURFACE_VAR}; background: transparent; border: none; letter-spacing: 0.08em;")
            if width:
                lbl.setFixedWidth(width)
            if text in ("PROGRESS", "SPEED"):
                lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if text == "ACTION":
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            th.addWidget(lbl, 0 if width else 1)

        queue_v.addWidget(table_hdr)

        self._queue_scroll = QScrollArea()
        self._queue_scroll.setWidgetResizable(True)
        self._queue_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._queue_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._queue_scroll.setStyleSheet("background: transparent; border: none;")

        self._queue_inner = QWidget()
        self._queue_inner.setStyleSheet("background: transparent;")
        self._queue_inner_v = QVBoxLayout(self._queue_inner)
        self._queue_inner_v.setContentsMargins(0, 0, 0, 0)
        self._queue_inner_v.setSpacing(0)
        self._queue_inner_v.addStretch()

        self._queue_scroll.setWidget(self._queue_inner)
        queue_v.addWidget(self._queue_scroll)

        self._active_row = QueueRow()
        self._active_row.action_btn.clicked.connect(self._cancel_download)
        self._active_row.setVisible(False)
        self._queue_inner_v.insertWidget(0, self._active_row)

        self._queue_empty_w = QWidget()
        qew_lay = QVBoxLayout(self._queue_empty_w)
        qew_lay.setContentsMargins(0, 40, 0, 40)
        qew_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qe_icon = QLabel()
        qe_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _set_svg_label(qe_icon, ICON["sidebar_downloader"], 48, C_OUTLINE_VAR)
        qe_text = QLabel("No downloads yet.\nPaste a URL above and click 'Add to Queue'.")
        qe_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qe_text.setFont(_inter(13))
        qe_text.setStyleSheet(f"color: {C_ON_SURFACE_VAR}; padding-top: 12px; background: transparent;")
        qew_lay.addWidget(qe_icon)
        qew_lay.addWidget(qe_text)
        
        self._queue_inner_v.insertWidget(0, self._queue_empty_w)
        center_v.addWidget(queue_card, stretch=1)

        prog_details = QHBoxLayout()
        prog_details.setSpacing(12)
        self._prog_title = QLabel("Ready")
        self._prog_title.setFont(_inter(12, QFont.Weight.Medium))
        self._prog_title.setStyleSheet(f"color: {C_ON_SURFACE}; background: transparent;")
        self._prog_pct = QLabel("")
        self._prog_pct.setFont(_inter(12, QFont.Weight.Medium))
        self._prog_pct.setStyleSheet(f"color: {C_PRIMARY}; background: transparent;")

        prog_details.addWidget(self._prog_title)
        prog_details.addStretch()
        prog_details.addWidget(self._prog_pct)
        center_v.addLayout(prog_details)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {C_SURFACE_HIGHEST};
                border-radius: 3px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: {C_PRIMARY};
                border-radius: 3px;
            }}
        """)
        center_v.addWidget(self.progress_bar)

        cancel_row = QHBoxLayout()
        cancel_row.addStretch()
        self.cancel_btn = QPushButton("Cancel Download")
        self.cancel_btn.setStyleSheet(BTN_DANGER)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_download)
        cancel_row.addWidget(self.cancel_btn)
        center_v.addLayout(cancel_row)

        h.addWidget(center, stretch=1)
        h.addWidget(_divider_v())

        right = QWidget()
        right.setFixedWidth(272)
        right.setStyleSheet(f"background: {C_SURFACE_LOWEST};")
        right_v = QVBoxLayout(right)
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.setSpacing(0)

        right_hdr = QWidget()
        right_hdr.setFixedHeight(44)
        right_hdr.setStyleSheet(f"""
            background: rgba(243,243,245,0.5);
            border-bottom: 1px solid {C_OUTLINE_VAR};
        """)
        right_hdr_h = QHBoxLayout(right_hdr)
        right_hdr_h.setContentsMargins(16, 0, 16, 0)
        rh_lbl = QLabel("DEFAULT SETTINGS")
        rh_lbl.setFont(_inter(10, QFont.Weight.DemiBold))
        rh_lbl.setStyleSheet(f"color: {C_ON_SURFACE_VAR}; background: transparent; border: none; letter-spacing: 0.08em;")
        right_hdr_h.addWidget(rh_lbl)
        right_v.addWidget(right_hdr)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll.setStyleSheet("background: transparent; border: none;")

        right_inner = QWidget()
        right_inner.setStyleSheet("background: transparent;")
        ri_v = QVBoxLayout(right_inner)
        ri_v.setContentsMargins(16, 16, 16, 16)
        ri_v.setSpacing(20)

        q_grp = QVBoxLayout()
        q_grp.setSpacing(6)
        q_lbl = QLabel("Preferred Quality")
        q_lbl.setFont(_inter(11, QFont.Weight.Medium))
        q_lbl.setStyleSheet(f"color: {C_ON_SURFACE_VAR};")
        self.quality_combo = QComboBox()
        self.quality_combo.addItems([
            "Best Available", "4K (2160p)", "1440p", "1080p",
            "720p", "480p", "360p", "Audio Only (MP3)"
        ])
        self.quality_combo.setFont(_inter(13))
        self.quality_combo.setStyleSheet(SELECT_STYLE)
        self.quality_combo.currentTextChanged.connect(self._remember_quality_for_current_url_type)
        q_grp.addWidget(q_lbl)
        q_grp.addWidget(self.quality_combo)
        ri_v.addLayout(q_grp)

        save_grp = QVBoxLayout()
        save_grp.setSpacing(6)
        save_lbl = QLabel("Save Location")
        save_lbl.setFont(_inter(11, QFont.Weight.Medium))
        save_lbl.setStyleSheet(f"color: {C_ON_SURFACE_VAR};")
        save_row = QHBoxLayout()
        save_row.setSpacing(6)
        default_dl = os.path.join(Path.home(), "Downloads", "MediaTube")
        self.folder_input = QLineEdit(default_dl)
        self.folder_input.setFont(_inter(12))
        self.folder_input.setStyleSheet(INPUT_STYLE)
        self.folder_input.setPlaceholderText("Download folder")
        browse_folder_btn = QPushButton()
        browse_folder_btn.setFixedSize(32, 32)
        browse_folder_btn.setStyleSheet(BTN_ICON)
        browse_folder_btn.setToolTip("Choose Folder")
        _set_svg_button(browse_folder_btn, ICON["folder_open"], 16, C_ON_SURFACE_VAR)
        browse_folder_btn.clicked.connect(self._browse_folder)
        save_row.addWidget(self.folder_input, stretch=1)
        save_row.addWidget(browse_folder_btn)
        save_grp.addWidget(save_lbl)
        save_grp.addLayout(save_row)
        ri_v.addLayout(save_grp)

        ri_v.addWidget(_divider_h())

        chk_grp = QVBoxLayout()
        chk_grp.setSpacing(12)
        self.audio_only_chk = QCheckBox("Force Audio Only")
        self.embed_subs_chk = QCheckBox("Embed Subtitles")
        self.prefer_av1_chk = QCheckBox("Prefer AV1 Codec")
        self.open_after_chk = QCheckBox("Open folder when done")
        for chk in [self.audio_only_chk, self.embed_subs_chk,
                    self.prefer_av1_chk, self.open_after_chk]:
            chk.setFont(_inter(13))
            chk.setStyleSheet(CHECKBOX_STYLE)
            chk_grp.addWidget(chk)
        self.embed_subs_chk.setChecked(True)
        ri_v.addLayout(chk_grp)

        ri_v.addWidget(_divider_h())

        ff_grp = QVBoxLayout()
        ff_grp.setSpacing(6)
        ff_lbl = QLabel("FFmpeg Path")
        ff_lbl.setFont(_inter(11, QFont.Weight.Medium))
        ff_lbl.setStyleSheet(f"color: {C_ON_SURFACE_VAR};")
        ff_row = QHBoxLayout()
        ff_row.setSpacing(6)
        default_ffmpeg = self._detect_default_ffmpeg()
        self.ffmpeg_input = QLineEdit(default_ffmpeg)
        self.ffmpeg_input.setFont(_inter(12))
        self.ffmpeg_input.setStyleSheet(INPUT_STYLE)
        self.ffmpeg_input.setPlaceholderText("Path to ffmpeg bin")
        browse_ff_btn = QPushButton()
        browse_ff_btn.setFixedSize(32, 32)
        browse_ff_btn.setStyleSheet(BTN_ICON)
        _set_svg_button(browse_ff_btn, ICON["folder_open"], 16, C_ON_SURFACE_VAR)
        browse_ff_btn.clicked.connect(self._browse_ffmpeg)
        ff_row.addWidget(self.ffmpeg_input, stretch=1)
        ff_row.addWidget(browse_ff_btn)
        self._ffmpeg_status = QLabel("Checking…")
        self._ffmpeg_status.setFont(_inter(10))
        self._ffmpeg_status.setStyleSheet(f"color: {C_ON_SURFACE_VAR};")
        ff_grp.addWidget(ff_lbl)
        ff_grp.addLayout(ff_row)
        ff_grp.addWidget(self._ffmpeg_status)
        ri_v.addLayout(ff_grp)

        ri_v.addStretch()

        reveal_btn = QPushButton("📂  Show Download Folder")
        reveal_btn.setStyleSheet(BTN_SECONDARY)
        reveal_btn.clicked.connect(self._reveal_folder)
        ri_v.addWidget(reveal_btn)

        right_scroll.setWidget(right_inner)
        right_v.addWidget(right_scroll, stretch=1)
        h.addWidget(right)
        return panel

    def _build_history_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: {C_BG};")
        v = QVBoxLayout(panel)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(16)

        phdr = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        h1 = QLabel("Download History")
        h1.setFont(_inter(24, QFont.Weight.DemiBold))
        h1.setStyleSheet(f"color: {C_ON_SURFACE}; background: transparent;")
        sub = QLabel("Manage and review your completed downloads.")
        sub.setFont(_inter(13))
        sub.setStyleSheet(f"color: {C_ON_SURFACE_VAR}; background: transparent;")
        title_col.addWidget(h1)
        title_col.addWidget(sub)

        phdr_btns = QHBoxLayout()
        phdr_btns.setSpacing(8)
        filter_btn = QPushButton("Filter")
        filter_btn.setStyleSheet(BTN_SECONDARY)
        _set_svg_button(filter_btn, ICON["history_filter"], 16, C_ON_SURFACE_VAR)
        self._clear_hist_btn = QPushButton("Clear All")
        self._clear_hist_btn.setStyleSheet(BTN_DANGER)
        self._clear_hist_btn.clicked.connect(self._clear_history)
        _set_svg_button(self._clear_hist_btn, ICON["history_clear"], 16, C_ON_SURFACE_VAR)
        phdr_btns.addWidget(filter_btn)
        phdr_btns.addWidget(self._clear_hist_btn)

        phdr.addLayout(title_col)
        phdr.addStretch()
        phdr.addLayout(phdr_btns)
        v.addLayout(phdr)

        hist_card = QWidget()
        hist_card.setObjectName("GlassCard")
        hist_card.setStyleSheet(f"""
            QWidget#GlassCard {{
                background: rgba(255,255,255,0.7);
                border: 1px solid {C_OUTLINE_VAR};
                border-radius: 8px;
            }}
        """)
        hist_v = QVBoxLayout(hist_card)
        hist_v.setContentsMargins(0, 0, 0, 0)
        hist_v.setSpacing(0)

        th = QWidget()
        th.setObjectName("HistoryTableHeader")
        th.setFixedHeight(36)
        th.setStyleSheet(f"""
            QWidget#HistoryTableHeader {{
                background: {C_SURFACE_LOW};
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                border-bottom: 1px solid {C_OUTLINE_VAR};
            }}
        """)
        th_h = QHBoxLayout(th)
        th_h.setContentsMargins(16, 0, 16, 0)
        th_h.setSpacing(16)

        for text, width in [("STATUS", 40), ("FILENAME / TITLE", 0), ("FORMAT", 110),
                             ("DATE DOWNLOADED", 150), ("ACTION", 80)]:
            lbl = QLabel(text)
            lbl.setFont(_inter(10, QFont.Weight.Medium))
            lbl.setStyleSheet(f"color: {C_ON_SURFACE_VAR}; background: transparent; border: none; letter-spacing: 0.08em;")
            if width:
                lbl.setFixedWidth(width)
            if text == "ACTION":
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            th_h.addWidget(lbl, 0 if width else 1)
        hist_v.addWidget(th)

        self._hist_scroll = QScrollArea()
        self._hist_scroll.setWidgetResizable(True)
        self._hist_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._hist_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._hist_scroll.setStyleSheet("background: transparent; border: none;")

        self._hist_inner = QWidget()
        self._hist_inner.setStyleSheet("background: transparent;")
        self._hist_inner_v = QVBoxLayout(self._hist_inner)
        self._hist_inner_v.setContentsMargins(0, 0, 0, 0)
        self._hist_inner_v.setSpacing(0)

        self._hist_empty_w = QWidget()
        hew_lay = QVBoxLayout(self._hist_empty_w)
        hew_lay.setContentsMargins(0, 60, 0, 60)
        hew_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        he_icon = QLabel()
        he_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _set_svg_label(he_icon, ICON["sidebar_history"], 48, C_OUTLINE_VAR)
        he_text = QLabel("No download history yet.")
        he_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        he_text.setFont(_inter(13))
        he_text.setStyleSheet(f"color: {C_ON_SURFACE_VAR}; padding-top: 12px; background: transparent;")
        hew_lay.addWidget(he_icon)
        hew_lay.addWidget(he_text)

        self._hist_inner_v.addWidget(self._hist_empty_w)
        self._hist_inner_v.addStretch()

        self._hist_scroll.setWidget(self._hist_inner)
        hist_v.addWidget(self._hist_scroll)
        v.addWidget(hist_card, stretch=1)

        self._hist_count_lbl = QLabel("Showing 0 downloads")
        self._hist_count_lbl.setFont(_inter(11))
        self._hist_count_lbl.setStyleSheet(f"color: {C_ON_SURFACE_VAR}; background: transparent;")
        v.addWidget(self._hist_count_lbl)

        return panel

    def _build_settings_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: {C_BG};")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"background: {C_BG}; border: none;")

        inner = QWidget()
        inner.setStyleSheet(f"background: {C_BG};")
        v = QVBoxLayout(inner)
        v.setContentsMargins(24, 24, 24, 80)
        v.setSpacing(16)

        phdr = QVBoxLayout()
        phdr.setSpacing(4)
        h2 = QLabel("Preferences")
        h2.setFont(_inter(24, QFont.Weight.DemiBold))
        h2.setStyleSheet(f"color: {C_ON_SURFACE}; background: transparent;")
        sub = QLabel("Manage your download behavior and app settings.")
        sub.setFont(_inter(13))
        sub.setStyleSheet(f"color: {C_ON_SURFACE_VAR}; background: transparent;")
        phdr.addWidget(h2)
        phdr.addWidget(sub)
        v.addLayout(phdr)

        grid = QHBoxLayout()
        grid.setSpacing(20)
        col_left  = QVBoxLayout()
        col_left.setSpacing(20)
        col_right = QVBoxLayout()
        col_right.setSpacing(20)

        general = GlassCard(ICON["settings_general"], "General")
        save_lbl = QLabel("Default Save Location")
        save_lbl.setFont(_inter(12, QFont.Weight.Medium))
        save_lbl.setStyleSheet(f"color: {C_ON_SURFACE};")
        save_row2 = QHBoxLayout()
        save_row2.setSpacing(8)
        self._settings_folder = QLineEdit()
        self._settings_folder.setFont(_inter(13))
        self._settings_folder.setStyleSheet(INPUT_STYLE)
        self._settings_folder.setReadOnly(True)
        s_browse = QPushButton("Browse…")
        s_browse.setStyleSheet(BTN_SECONDARY)
        s_browse.clicked.connect(self._settings_browse_folder)
        save_row2.addWidget(self._settings_folder, stretch=1)
        save_row2.addWidget(s_browse)

        notif_row = QHBoxLayout()
        notif_col = QVBoxLayout()
        notif_col.setSpacing(2)
        notif_lbl = QLabel("Notifications")
        notif_lbl.setFont(_inter(13, QFont.Weight.Medium))
        notif_lbl.setStyleSheet(f"color: {C_ON_SURFACE};")
        notif_sub = QLabel("Show alerts when done")
        notif_sub.setFont(_inter(11))
        notif_sub.setStyleSheet(f"color: {C_ON_SURFACE_VAR};")
        notif_col.addWidget(notif_lbl)
        notif_col.addWidget(notif_sub)
        self._notif_chk = QCheckBox("")
        self._notif_chk.setChecked(True)
        self._notif_chk.setStyleSheet(CHECKBOX_STYLE)
        notif_row.addLayout(notif_col)
        notif_row.addStretch()
        notif_row.addWidget(self._notif_chk)

        open_row = QHBoxLayout()
        open_col = QVBoxLayout()
        open_col.setSpacing(2)
        open_lbl = QLabel("Open Folder After Download")
        open_lbl.setFont(_inter(13, QFont.Weight.Medium))
        open_lbl.setStyleSheet(f"color: {C_ON_SURFACE};")
        open_sub = QLabel("Reveals the file in Explorer/Finder")
        open_sub.setFont(_inter(11))
        open_sub.setStyleSheet(f"color: {C_ON_SURFACE_VAR};")
        open_col.addWidget(open_lbl)
        open_col.addWidget(open_sub)
        self._settings_open_after = QCheckBox("")
        self._settings_open_after.setChecked(True)
        self._settings_open_after.setStyleSheet(CHECKBOX_STYLE)
        open_row.addLayout(open_col)
        open_row.addStretch()
        open_row.addWidget(self._settings_open_after)

        save_grp2 = QVBoxLayout()
        save_grp2.setSpacing(6)
        save_grp2.addWidget(save_lbl)
        save_grp2.addLayout(save_row2)

        general.add_layout(save_grp2)
        general.add_layout(notif_row)
        general.add_layout(open_row)
        col_left.addWidget(general)

        va = GlassCard(ICON["settings_video"], "Video & Audio")
        def _setting_row(label: str, combo_items: list) -> tuple:
            row = QHBoxLayout()
            row.setSpacing(16)
            lbl = QLabel(label)
            lbl.setFont(_inter(12, QFont.Weight.Medium))
            lbl.setStyleSheet(f"color: {C_ON_SURFACE};")
            lbl.setFixedWidth(70)
            cb = QComboBox()
            cb.addItems(combo_items)
            cb.setFont(_inter(13))
            cb.setStyleSheet(SELECT_STYLE)
            row.addWidget(lbl)
            row.addWidget(cb, stretch=1)
            return row, cb

        quality_row, self._s_quality = _setting_row("Quality", [
            "Best Available (4K/8K)", "1080p Premium", "720p Standard",
            "480p", "360p", "Audio Only"
        ])
        format_row, self._s_format = _setting_row("Format", [
            "MKV (Advanced)", "MP4 (Most Compatible)", "WebM"
        ])
        codec_row, self._s_codec = _setting_row("Codec", [
            "H.264 (Default)", "H.265 / HEVC", "AV1"
        ])
        self._s_quality.currentIndexChanged.connect(self._sync_settings_to_queue)
        self._s_codec.currentIndexChanged.connect(self._sync_settings_to_queue)

        va.add_layout(quality_row)
        va.add_layout(format_row)
        va.add_layout(codec_row)
        col_right.addWidget(va)

        adv = GlassCard(ICON["settings_advanced"], "Advanced")
        ff_lbl2 = QLabel("Custom FFmpeg Path")
        ff_lbl2.setFont(_inter(12, QFont.Weight.Medium))
        ff_lbl2.setStyleSheet(f"color: {C_ON_SURFACE};")
        ff_row2 = QHBoxLayout()
        ff_row2.setSpacing(8)
        self._s_ffmpeg = QLineEdit()
        self._s_ffmpeg.setFont(_inter(13))
        self._s_ffmpeg.setStyleSheet(INPUT_STYLE)
        self._s_ffmpeg.setPlaceholderText("/usr/local/bin/ffmpeg")
        ff_browse2 = QPushButton("Browse…")
        ff_browse2.setStyleSheet(BTN_SECONDARY)
        ff_browse2.clicked.connect(self._settings_browse_ffmpeg)
        ff_row2.addWidget(self._s_ffmpeg, stretch=1)
        ff_row2.addWidget(ff_browse2)
        ff_hint = QLabel("Leave blank to use bundled version")
        ff_hint.setFont(_inter(11))
        ff_hint.setStyleSheet(f"color: {C_ON_SURFACE_VAR};")

        ff_grp2 = QVBoxLayout()
        ff_grp2.setSpacing(6)
        ff_grp2.addWidget(ff_lbl2)
        ff_grp2.addLayout(ff_row2)
        ff_grp2.addWidget(ff_hint)

        conc_lbl = QLabel("Concurrent Downloads")
        conc_lbl.setFont(_inter(12, QFont.Weight.Medium))
        conc_lbl.setStyleSheet(f"color: {C_ON_SURFACE};")
        conc_row = QHBoxLayout()
        conc_row.setSpacing(10)
        self._conc_slider = QSlider(Qt.Orientation.Horizontal)
        self._conc_slider.setRange(1, 10)
        self._conc_slider.setValue(4)
        self._conc_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 4px;
                background: {C_OUTLINE_VAR};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {C_SURFACE_LOWEST};
                border: 1px solid {C_OUTLINE_VAR};
                width: 16px; height: 16px;
                border-radius: 8px;
                margin: -6px 0;
            }}
            QSlider::sub-page:horizontal {{
                background: {C_PRIMARY};
                border-radius: 2px;
            }}
        """)
        self._conc_val = QLabel("4")
        self._conc_val.setFont(_inter(12, QFont.Weight.Medium))
        self._conc_val.setStyleSheet(f"color: {C_PRIMARY};")
        self._conc_val.setFixedWidth(24)
        self._conc_slider.valueChanged.connect(lambda v: self._conc_val.setText(str(v)))
        conc_row.addWidget(self._conc_slider, stretch=1)
        conc_row.addWidget(self._conc_val)
        
        conc_hints = QHBoxLayout()
        l1 = QLabel("1 (Slower)")
        l2 = QLabel("10 (Faster)")
        for lx in [l1, l2]:
            lx.setFont(_inter(10))
            lx.setStyleSheet(f"color: {C_ON_SURFACE_VAR};")
        conc_hints.addWidget(l1)
        conc_hints.addStretch()
        conc_hints.addWidget(l2)

        conc_grp = QVBoxLayout()
        conc_grp.setSpacing(6)
        conc_grp.addWidget(conc_lbl)
        conc_grp.addLayout(conc_row)
        conc_grp.addLayout(conc_hints)

        adv.add_layout(ff_grp2)
        adv.add_layout(conc_grp)
        col_left.addWidget(adv)

        appear = GlassCard(ICON["settings_appearance"], "Appearance & App")
        theme_row, self._s_theme = _setting_row("Theme", [
            "System Default", "Light (Aqua)", "Dark (Graphite)"
        ])
        lang_row, self._s_lang = _setting_row("Language", [
            "English (US)", "Spanish", "French", "German", "Japanese"
        ])

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        reset_btn = QPushButton("Reset Defaults")
        reset_btn.setStyleSheet(BTN_DANGER)
        reset_btn.clicked.connect(self._reset_defaults)
        bottom_row.addWidget(reset_btn)

        appear.add_layout(theme_row)
        appear.add_layout(lang_row)
        appear.add_layout(bottom_row)
        col_right.addWidget(appear)

        col_left.addStretch()
        col_right.addStretch()

        grid.addLayout(col_left, stretch=1)
        grid.addLayout(col_right, stretch=1)
        v.addLayout(grid)

        scroll.setWidget(inner)

        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return panel

    def _build_logs_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: {C_BG};")
        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        log_hdr = QWidget()
        log_hdr.setFixedHeight(52)
        log_hdr.setStyleSheet(f"""
            background: rgba(249,249,251,0.5);
            border-bottom: 1px solid rgba(193,198,215,0.5);
        """)
        log_hdr_h = QHBoxLayout(log_hdr)
        log_hdr_h.setContentsMargins(24, 0, 24, 0)

        log_title_col = QVBoxLayout()
        log_title_col.setSpacing(0)
        lt = QLabel("System Logs")
        lt.setFont(_inter(18, QFont.Weight.DemiBold))
        lt.setStyleSheet(f"color: {C_ON_SURFACE}; background: transparent; border: none;")
        ls = QLabel("Real-time diagnostic output")
        ls.setFont(_inter(11))
        ls.setStyleSheet(f"color: {C_ON_SURFACE_VAR}; background: transparent; border: none;")
        log_title_col.addWidget(lt)
        log_title_col.addWidget(ls)

        copy_btn = QPushButton("📋  Copy")
        copy_btn.setStyleSheet(BTN_SECONDARY)
        copy_btn.clicked.connect(self._copy_logs)

        clear_log_btn = QPushButton("🗑  Clear")
        clear_log_btn.setStyleSheet(BTN_DANGER)
        clear_log_btn.clicked.connect(lambda: self.log_text.clear())

        log_hdr_h.addLayout(log_title_col)
        log_hdr_h.addStretch()
        log_hdr_h.addWidget(copy_btn)
        log_hdr_h.addWidget(clear_log_btn)
        v.addWidget(log_hdr)

        term_wrap = QWidget()
        term_wrap.setStyleSheet(f"background: {C_BG};")
        tw_v = QVBoxLayout(term_wrap)
        tw_v.setContentsMargins(24, 20, 24, 20)

        term_outer = QWidget()
        term_outer.setStyleSheet("""
            QWidget {
                background: #1e1e1e;
                border-radius: 8px;
                border: 1px solid #333;
            }
        """)
        to_v = QVBoxLayout(term_outer)
        to_v.setContentsMargins(0, 0, 0, 0)
        to_v.setSpacing(0)

        term_bar = QWidget()
        term_bar.setFixedHeight(32)
        term_bar.setStyleSheet("""
            background: #2d2d2d;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            border-bottom: 1px solid #111;
        """)
        tb_h = QHBoxLayout(term_bar)
        tb_h.setContentsMargins(12, 0, 12, 0)
        tb_h.setSpacing(6)

        for color, border in [("#ff5f56", "#e0443e"), ("#ffbd2e", "#dea123"), ("#27c93f", "#1aab29")]:
            dot = QLabel()
            dot.setFixedSize(12, 12)
            dot.setStyleSheet(f"background: {color}; border-radius: 6px; border: 1px solid {border};")
            tb_h.addWidget(dot)

        tb_h.addStretch()
        filename_lbl = QLabel("mediatube_core.log")
        filename_lbl.setStyleSheet("color: #888; font-size: 11px; font-family: 'JetBrains Mono', 'Courier New', monospace; background: transparent; border: none;")
        tb_h.addWidget(filename_lbl)
        tb_h.addStretch()

        live_dot = QLabel()
        live_dot.setFixedSize(8, 8)
        live_dot.setStyleSheet("background: #27c93f; border-radius: 4px; border: none;")
        live_lbl = QLabel("LIVE")
        live_lbl.setStyleSheet("color: #27c93f; font-size: 10px; font-family: 'JetBrains Mono', 'Courier New', monospace; background: transparent; border: none;")
        tb_h.addWidget(live_dot)
        tb_h.addWidget(live_lbl)

        to_v.addWidget(term_bar)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        _mono = QFont()
        for _mf in ["JetBrains Mono", "Cascadia Code", "Consolas", "Menlo", "Courier New"]:
            _mono.setFamily(_mf)
            if _mono.exactMatch():
                break
        _mono.setPointSize(12)
        self.log_text.setFont(_mono)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background: #1e1e1e;
                color: #d4d4d4;
                border: none;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
                padding: 12px 16px;
                selection-background-color: #264f78;
            }
            QScrollBar:vertical {
                background: rgba(0,0,0,0.2);
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.2);
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        to_v.addWidget(self.log_text)
        tw_v.addWidget(term_outer)
        v.addWidget(term_wrap, stretch=1)
        return panel

    def _build_footer(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(24)
        bar.setStyleSheet(f"""
            QWidget {{
                background: {C_SURFACE_LOW};
                border-top: 1px solid {C_OUTLINE_VAR};
            }}
        """)
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 0, 12, 0)
        h.setSpacing(8)

        self._status_dot = QLabel()
        self._status_dot.setFixedSize(8, 8)
        self._status_dot.setStyleSheet(f"background: {C_SUCCESS}; border-radius: 4px; border: none;")

        self._status_lbl = QLabel("Ready to download")
        self._status_lbl.setFont(_inter(11))
        self._status_lbl.setStyleSheet(f"color: {C_SECONDARY}; background: transparent; border: none;")

        h.addWidget(self._status_dot)
        h.addWidget(self._status_lbl)
        h.addStretch()

        sys_status = QLabel("System Status")
        sys_status.setFont(_inter(11))
        sys_status.setStyleSheet(f"color: {C_ON_SURFACE_VAR}; background: transparent; border: none;")
        sys_status.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        api_docs = QLabel("API Docs")
        api_docs.setFont(_inter(11))
        api_docs.setStyleSheet(f"color: {C_ON_SURFACE_VAR}; background: transparent; border: none;")
        api_docs.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        sep = QLabel("•")
        sep.setFont(_inter(11))
        sep.setStyleSheet(f"color: {C_ON_SURFACE_VAR}; background: transparent; border: none;")

        h.addWidget(sys_status)
        h.addWidget(sep)
        h.addWidget(api_docs)
        return bar

    def _detect_default_ffmpeg(self) -> str:
        if sys.platform == "win32":
            return r"C:\ffmpeg\bin"
        if sys.platform == "darwin":
            for p in ("/opt/homebrew/bin", "/usr/local/bin"):
                if os.path.exists(os.path.join(p, "ffmpeg")):
                    return p
        return ""

    def _check_ffmpeg_quietly(self):
        hint = self.ffmpeg_input.text().strip()
        ok, result = FFmpegValidator.find_ffmpeg(hint)
        if ok:
            ver = FFmpegValidator.get_ffmpeg_version(result)
            self._ffmpeg_status.setText(f"✓ ffmpeg {ver} found")
            self._ffmpeg_status.setStyleSheet(f"color: {C_SUCCESS}; font-size: 10px;")
            self._topbar_ffmpeg.setText(f"ffmpeg {ver} ✓")
            self._topbar_ffmpeg.setStyleSheet(f"color: {C_SUCCESS}; background: transparent; border: none;")
        else:
            self._ffmpeg_status.setText("⚠ ffmpeg not found — merging will fail")
            self._ffmpeg_status.setStyleSheet(f"color: {C_WARN}; font-size: 10px;")
            self._topbar_ffmpeg.setText("ffmpeg not found ⚠")
            self._topbar_ffmpeg.setStyleSheet(f"color: {C_WARN}; background: transparent; border: none;")

    def _on_url_changed(self, text: str):
        if not text.strip():
            self._url_indicator.clear()
            self._url_hint.setText("")
            self._url_valid = False
            return
        ok, msg = URLValidator.validate(text)
        self._url_valid = ok
        if ok:
            color = C_SUCCESS if not msg else C_WARN
            _set_svg_label(self._url_indicator, ICON["queue_status_ok"], 16, color)
            self._url_hint.setText(msg)
            self._url_hint.setStyleSheet(f"color: {C_WARN}; font-size: 11px; background: transparent;")
        else:
            _set_svg_label(self._url_indicator, ICON["queue_status_error"], 16, C_ERROR)
            self._url_hint.setText(f"✗ {msg}")
            self._url_hint.setStyleSheet(f"color: {C_ERROR}; font-size: 11px; background: transparent;")
        self._apply_saved_quality_for_url(text)

    def _url_type_for(self, url: str) -> str:
        text = url.strip().lower()
        if not text:
            return ""
        try:
            host = urlparse(text).netloc.lower()
        except Exception:
            host = ""
        if "youtube.com" in host or "youtu.be" in host:
            return "youtube"
        if "vimeo.com" in host:
            return "vimeo"
        if "twitch.tv" in host:
            return "twitch"
        if "dailymotion.com" in host:
            return "dailymotion"
        if "soundcloud.com" in host:
            return "soundcloud"
        return "other"

    def _apply_saved_quality_for_url(self, url: str):
        url_type = self._url_type_for(url)
        if not url_type or url_type == self._last_url_type_applied:
            return
        quality = self._quality_by_url_type.get(url_type)
        if quality:
            index = self.quality_combo.findText(quality)
            if index >= 0:
                self.quality_combo.setCurrentIndex(index)
        self._last_url_type_applied = url_type

    def _remember_quality_for_current_url_type(self, quality: str):
        url_type = self._url_type_for(self.url_input.text())
        if not url_type:
            return
        self._quality_by_url_type[url_type] = quality

    def _browse_ffmpeg(self):
        d = QFileDialog.getExistingDirectory(self, "Select FFmpeg bin Directory")
        if d:
            self.ffmpeg_input.setText(d)
            if hasattr(self, "_s_ffmpeg"):
                self._s_ffmpeg.setText(d)
            self._check_ffmpeg_quietly()
            self._save_settings()

    def _browse_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if d:
            self.folder_input.setText(d)
            if hasattr(self, "_settings_folder"):
                self._settings_folder.setText(d)
            self._save_settings()

    def _settings_browse_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if d:
            self._settings_folder.setText(d)
            self.folder_input.setText(d)
            self._save_settings()

    def _settings_browse_ffmpeg(self):
        d = QFileDialog.getExistingDirectory(self, "Select FFmpeg bin Directory")
        if d:
            self._s_ffmpeg.setText(d)
            self.ffmpeg_input.setText(d)
            self._check_ffmpeg_quietly()
            self._save_settings()

    def _reveal_folder(self):
        folder = self.folder_input.text().strip()
        if folder and os.path.exists(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        else:
            QMessageBox.warning(self, "Folder Not Found",
                                "The download folder doesn't exist yet.\nStart a download first.")

    def _refresh_history_list(self):
        if not hasattr(self, "_hist_inner_v"):
            return

        while self._hist_inner_v.count() > 0:
            item = self._hist_inner_v.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._download_history:
            self._hist_empty_w = QWidget()
            hew_lay = QVBoxLayout(self._hist_empty_w)
            hew_lay.setContentsMargins(0, 60, 0, 60)
            hew_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            he_icon = QLabel()
            he_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            _set_svg_label(he_icon, ICON["sidebar_history"], 48, C_OUTLINE_VAR)
            he_text = QLabel("No download history yet.")
            he_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            he_text.setFont(_inter(13))
            he_text.setStyleSheet(f"color: {C_ON_SURFACE_VAR}; padding-top: 12px; background: transparent;")
            hew_lay.addWidget(he_icon)
            hew_lay.addWidget(he_text)
            
            self._hist_inner_v.addWidget(self._hist_empty_w)
            self._hist_inner_v.addStretch()
            if hasattr(self, "_hist_count_lbl"):
                self._hist_count_lbl.setText("Showing 0 downloads")
            return

        for entry in self._download_history[:20]:
            row = HistoryRow(entry)
            row.open_folder_requested.connect(self._open_folder_path)
            row.reuse_requested.connect(self._use_history_entry)
            self._hist_inner_v.addWidget(row)

        self._hist_inner_v.addStretch()
        n = len(self._download_history)
        if hasattr(self, "_hist_count_lbl"):
            self._hist_count_lbl.setText(f"Showing {min(n, 20)} of {n} downloads")

    def _open_folder_path(self, folder: str):
        if folder and os.path.exists(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _use_history_entry(self, entry: dict):
        url = entry.get("url", "")
        folder = entry.get("folder", "")
        quality = entry.get("quality", "")
        if url:
            self.url_input.setText(url)
            self._on_url_changed(url)
        if folder:
            self.folder_input.setText(folder)
        if quality:
            index = self.quality_combo.findText(quality)
            if index >= 0:
                self.quality_combo.setCurrentIndex(index)
        self._switch_tab(0)

    def _append_history_entry(self, title: str, url: str, folder: str, quality: str):
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "title":     title,
            "url":       url,
            "url_type":  self._url_type_for(url),
            "folder":    folder,
            "quality":   quality,
        }
        self._download_history.insert(0, entry)
        self._download_history = self._download_history[:20]
        self._refresh_history_list()

    def _clear_history(self):
        self._download_history = []
        self._refresh_history_list()
        self._save_settings()

    def _clear_finished_queue(self):
        if self.worker is None or not self.worker.isRunning():
            self._active_row.setVisible(False)
            self._queue_empty_w.setVisible(True)

    def _log(self, message: str, level: str = "info"):
        if not message.strip():
            return
        ts = datetime.now().strftime("%H:%M:%S.%f")[:12]
        
        if level == "error":
            app_logger.error(message)
        elif level == "warn":
            app_logger.warning(message)
        else:
            app_logger.info(message)
            
        level_colors = {
            "info":    ("#569cd6", "#4ec9b0", "#d4d4d4"),
            "warn":    ("#569cd6", "#ce9178", "#d4d4d4"),
            "error":   ("#569cd6", "#f44747", "#f44747"),
            "success": ("#569cd6", "#4ec9b0", "#4ec9b0"),
        }
        ts_col, lv_col, msg_col = level_colors.get(level, level_colors["info"])
        level_tags = {"info": "INFO ", "warn": "WARN ", "error": "ERR  ", "success": "OK   "}
        lv_tag = level_tags.get(level, "INFO ")
        bold = "bold" if level == "error" else "normal"

        self.log_text.append(
            f'<span style="color:{ts_col}; font-family: Consolas,monospace; white-space:pre;">{ts}</span>'
            f'<span style="color:{lv_col}; font-family: Consolas,monospace; font-weight:{bold}; white-space:pre;"> [{lv_tag}]</span>'
            f' <span style="color:{msg_col}; font-family: Consolas,monospace;">{message}</span>'
        )
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _copy_logs(self):
        QApplication.clipboard().setText(self.log_text.toPlainText())

    def _update_progress(self, d: dict):
        status = d.get("status", "")
        if status == "downloading":
            pct_str  = d.get("_percent_str", "0%").strip()
            filename = os.path.basename(d.get("filename", "") or "")
            
            # Reset UI from Merging -> Downloading state for playlists
            if self._active_row.meta_lbl.text() == "Merging…":
                self._prog_title.setText("Downloading…")
                self._active_row.meta_lbl.setText("Downloading…")
                
            try:
                pct = float(pct_str.replace("%", ""))
                self.progress_bar.setValue(int(pct))
                self._prog_pct.setText(f"{pct:.0f}%")
                self._active_row.pct_lbl.setText(f"{pct:.0f}%")
                self._active_row.mini_bar.setValue(int(pct))
            except ValueError:
                pass
            if filename:
                self._current_filename = filename
                short = filename[:45] + "…" if len(filename) > 45 else filename
                self._prog_title.setText(short)
        elif status == "finished":
            self.progress_bar.setValue(100)
            self._prog_pct.setText("100%")
            self._prog_title.setText("Merging…")
            self._active_row.pct_lbl.setText("100%")
            self._active_row.mini_bar.setValue(100)
            self._active_row.meta_lbl.setText("Merging…")

    def _update_stats(self, stats: dict):
        speed  = stats.get("speed", "—")
        eta    = stats.get("eta", "—")
        dl     = stats.get("downloaded", "—")
        total  = stats.get("total", "—")
        elapsed = stats.get("elapsed", "—")
        self._active_row.speed_lbl.setText(f"{speed}\n{eta} rem")
        self._status_lbl.setText(f"Elapsed: {elapsed}  •  ETA: {eta}  •  {dl} / {total}")

    def _start_download(self):
        self._save_settings()
        url = self.url_input.text().strip()
        if not url:
            self.url_input.setFocus()
            return

        ok, msg = URLValidator.validate(url)
        if not ok:
            QMessageBox.warning(self, "Invalid URL", msg)
            return

        ffmpeg_path = self.ffmpeg_input.text().strip()
        ff_ok, ff_result = FFmpegValidator.find_ffmpeg(ffmpeg_path)
        if not ff_ok and not self.audio_only_chk.isChecked():
            reply = QMessageBox.question(
                self, "ffmpeg Missing",
                "ffmpeg was not found and is required to merge video+audio.\n\n"
                "Continue anyway? (download may be video-only or fail)\n\n"
                f"{ff_result}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        output_folder = self.folder_input.text().strip()
        if not output_folder:
            QMessageBox.warning(self, "No Output Folder", "Please choose a download folder.")
            return
        try:
            Path(output_folder).mkdir(parents=True, exist_ok=True)
            test_file = Path(output_folder) / ".write_test"
            test_file.touch()
            test_file.unlink()
        except PermissionError:
            QMessageBox.critical(self, "Permission Denied",
                                 f"Cannot write to:\n{output_folder}\nChoose a different folder.")
            return
        except OSError as e:
            QMessageBox.critical(self, "Folder Error", str(e))
            return

        self._add_btn.setEnabled(False)
        self._add_btn.setText("Downloading…")
        self.cancel_btn.setEnabled(True)
        self.url_input.setEnabled(False)
        self.progress_bar.setValue(0)
        self._prog_pct.setText("0%")
        self._prog_title.setText("Starting…")
        self._prog_title.setStyleSheet(f"color: {C_ON_SURFACE}; background: transparent;")
        self.log_text.clear()
        
        app_logger.info(f"Starting Download: {url}")

        self._queue_empty_w.setVisible(False)
        self._active_row.setVisible(True)
        self._active_row.filename_lbl.setText(url[:55] + "…" if len(url) > 55 else url)
        self._active_row.meta_lbl.setText("Starting…")
        self._active_row.pct_lbl.setText("0%")
        self._active_row.mini_bar.setValue(0)
        self._active_row.speed_lbl.setText("—")
        self._active_row.status_lbl.setStyleSheet("background: transparent; border: none;")
        self._active_row.status_lbl.setText("")
        _set_svg_label(self._active_row.status_lbl, ICON["queue_status_active"], 18, C_PRIMARY)

        quality = self.quality_combo.currentText()
        self._current_url_for_download = url
        self._current_filename = ""
        self._log(f"URL: {url}", "info")

        concurrent = self._conc_slider.value() if hasattr(self, "_conc_slider") else 4

        self.worker = DownloadWorker(
            url, quality, output_folder, ffmpeg_path,
            audio_only=self.audio_only_chk.isChecked(),
            embed_subs=self.embed_subs_chk.isChecked(),
            prefer_av1=self.prefer_av1_chk.isChecked(),
            concurrent_fragments=concurrent
        )
        self.worker.progress_signal.connect(self._update_progress)
        self.worker.log_signal.connect(self._log)
        self.worker.stats_signal.connect(self._update_stats)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.start()

        self._status_lbl.setText("Downloading…")
        self._status_dot.setStyleSheet(f"background: {C_PRIMARY}; border-radius: 4px; border: none;")

    def _cancel_download(self):
        if self.worker and self.worker.isRunning():
            self.cancel_btn.setEnabled(False)
            self.worker.cancel()
            self._prog_title.setText("Cancelling…")
            self._status_lbl.setText("Waiting for current chunk to finish…")
            app_logger.warning("Download cancel requested by user.")

    def _on_finished(self, success: bool, message: str):
        self._add_btn.setEnabled(True)
        self._add_btn.setText("Add to Queue")
        self.cancel_btn.setEnabled(False)
        self.url_input.setEnabled(True)

        if success:
            self.progress_bar.setValue(100)
            self.progress_bar.setStyleSheet(f"""
                QProgressBar {{
                    background: {C_SURFACE_HIGHEST};
                    border-radius: 3px;
                    border: none;
                }}
                QProgressBar::chunk {{
                    background: {C_SUCCESS};
                    border-radius: 3px;
                }}
            """)
            self._prog_title.setText("Done ✓")
            self._prog_pct.setText("100%")
            self._prog_title.setStyleSheet(f"color: {C_SUCCESS}; background: transparent;")
            self._log(message, "success")
            self._status_lbl.setText("Completed ✓")
            self._status_dot.setStyleSheet(f"background: {C_SUCCESS}; border-radius: 4px; border: none;")

            fname = self._current_filename or self._current_url_for_download
            self._active_row.set_done(fname, "Completed ✓")

            self._append_history_entry(
                fname,
                self._current_url_for_download,
                self.folder_input.text().strip(),
                self.quality_combo.currentText(),
            )
            self._save_settings()
            
            app_logger.info(f"Download Completed: {fname}")

            if hasattr(self, "_notif_chk") and self._notif_chk.isChecked():
                QMessageBox.information(self, "Download Complete", message)

            if self.open_after_chk.isChecked():
                folder = self.folder_input.text().strip()
                if folder and os.path.exists(folder):
                    QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

            if self._tray_available and self._tray_icon and hasattr(self, "_notif_chk") and self._notif_chk.isChecked():
                self._tray_icon.showMessage("Download complete", message,
                                            QSystemTrayIcon.MessageIcon.Information, 4000)

            QTimer.singleShot(4000, lambda: self.progress_bar.setStyleSheet(f"""
                QProgressBar {{
                    background: {C_SURFACE_HIGHEST};
                    border-radius: 3px;
                    border: none;
                }}
                QProgressBar::chunk {{
                    background: {C_PRIMARY};
                    border-radius: 3px;
                }}
            """))
        else:
            self.progress_bar.setValue(0)
            self._prog_pct.setText("")
            self._prog_title.setText("Stopped")
            self._prog_title.setStyleSheet(f"color: {C_ERROR}; background: transparent;")
            self._log(message, "error")
            self._status_lbl.setText("Stopped")
            self._status_dot.setStyleSheet(f"background: {C_ERROR}; border-radius: 4px; border: none;")

            fname = self._current_filename or self._current_url_for_download
            self._active_row.set_error(fname, message[:60])
            
            app_logger.error(f"Download Failed: {message}")

            if "Cancelled" not in message:
                QMessageBox.critical(self, "Download Error", message)

        QTimer.singleShot(4000, lambda: self._prog_title.setStyleSheet(
            f"color: {C_ON_SURFACE}; background: transparent;"
        ))
        QTimer.singleShot(4000, lambda: self._status_dot.setStyleSheet(
            f"background: {C_SUCCESS}; border-radius: 4px; border: none;"
        ))

    def _sync_settings_to_queue(self):
        q_text = self._s_quality.currentText() if hasattr(self, "_s_quality") else ""
        codec  = self._s_codec.currentText() if hasattr(self, "_s_codec") else ""
        mapping = {
            "Best Available (4K/8K)": "Best Available",
            "1080p Premium":          "1080p",
            "720p Standard":          "720p",
            "480p":                   "480p",
            "360p":                   "360p",
            "Audio Only":             "Audio Only (MP3)",
        }
        mapped = mapping.get(q_text)
        if mapped:
            idx = self.quality_combo.findText(mapped)
            if idx >= 0:
                self.quality_combo.setCurrentIndex(idx)
        if "AV1" in codec and hasattr(self, "prefer_av1_chk"):
            self.prefer_av1_chk.setChecked(True)

    def _reset_defaults(self):
        self.folder_input.setText(os.path.join(Path.home(), "Downloads", "MediaTube"))
        self.ffmpeg_input.setText(self._detect_default_ffmpeg())
        self.quality_combo.setCurrentIndex(0)
        self.audio_only_chk.setChecked(False)
        self.embed_subs_chk.setChecked(True)
        self.prefer_av1_chk.setChecked(False)
        self.open_after_chk.setChecked(True)
        if hasattr(self, "_notif_chk"):
            self._notif_chk.setChecked(True)
        if hasattr(self, "_conc_slider"):
            self._conc_slider.setValue(4)
        self._save_settings()

    def _load_settings(self):
        folder   = self._settings.value("download_folder", "", type=str)
        ffmpeg   = self._settings.value("ffmpeg_path", "", type=str)
        quality  = self._settings.value("quality", "Best Available", type=str)
        ao       = self._settings.value("audio_only", False, type=bool)
        subs     = self._settings.value("embed_subs", True, type=bool)
        av1      = self._settings.value("prefer_av1", False, type=bool)
        open_af  = self._settings.value("open_after_download", True, type=bool)
        notif    = self._settings.value("notifications", True, type=bool)
        conc     = self._settings.value("concurrent_fragments", 4, type=int)
        dl_hist  = self._read_json_setting("download_history", [])
        q_map    = self._read_json_setting("quality_by_url_type", {})

        if folder:
            self.folder_input.setText(folder)
            if hasattr(self, "_settings_folder"):
                self._settings_folder.setText(folder)
        if ffmpeg:
            self.ffmpeg_input.setText(ffmpeg)
            if hasattr(self, "_s_ffmpeg"):
                self._s_ffmpeg.setText(ffmpeg)
        idx = self.quality_combo.findText(quality)
        if idx >= 0:
            self.quality_combo.setCurrentIndex(idx)
        self.audio_only_chk.setChecked(ao)
        self.embed_subs_chk.setChecked(subs)
        self.prefer_av1_chk.setChecked(av1)
        self.open_after_chk.setChecked(open_af)
        
        if hasattr(self, "_notif_chk"):
            self._notif_chk.setChecked(notif)
            
        if hasattr(self, "_conc_slider"):
            self._conc_slider.setValue(conc)
            
        self._quality_by_url_type = q_map if isinstance(q_map, dict) else {}
        self._download_history = dl_hist if isinstance(dl_hist, list) else []
        self._refresh_history_list()

    def _save_settings(self):
        self._settings.setValue("window_geometry", self.saveGeometry())
        self._settings.setValue("window_state",    self.saveState())
        self._settings.setValue("download_folder", self.folder_input.text().strip())
        self._settings.setValue("ffmpeg_path",     self.ffmpeg_input.text().strip())
        self._settings.setValue("quality",         self.quality_combo.currentText())
        self._settings.setValue("audio_only",      self.audio_only_chk.isChecked())
        self._settings.setValue("embed_subs",      self.embed_subs_chk.isChecked())
        self._settings.setValue("prefer_av1",      self.prefer_av1_chk.isChecked())
        self._settings.setValue("open_after_download", self.open_after_chk.isChecked())
        
        if hasattr(self, "_notif_chk"):
            self._settings.setValue("notifications", self._notif_chk.isChecked())
            
        if hasattr(self, "_conc_slider"):
            self._settings.setValue("concurrent_fragments", self._conc_slider.value())
            
        self._settings.setValue("download_history", json.dumps(self._download_history[:20]))
        self._settings.setValue("quality_by_url_type", json.dumps(self._quality_by_url_type))

    def _read_json_setting(self, key: str, default):
        raw = self._settings.value(key, json.dumps(default))
        if isinstance(raw, (list, dict)):
            return raw
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return default
        return default

    def showEvent(self, event):
        super().showEvent(event)
        geometry = self._settings.value("window_geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        state = self._settings.value("window_state")
        if state is not None:
            self.restoreState(state)
        if hasattr(self, "_settings_folder"):
            self._settings_folder.setText(self.folder_input.text())
        if hasattr(self, "_s_ffmpeg"):
            self._s_ffmpeg.setText(self.ffmpeg_input.text())

    def closeEvent(self, event):
        self._save_settings()
        if self._tray_available and self._tray_icon and self._tray_icon.isVisible():
            event.ignore()
            self.hide()
            self._tray_icon.showMessage("MediaTube Pro", "App is running in the background. Right-click the tray icon to completely exit.",
                                        QSystemTrayIcon.MessageIcon.Information, 4000)
        else:
            app_logger.info("MediaTube Pro shutting down...")
            QApplication.quit()

    def _setup_tray(self):
        self._tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        if not self._tray_available:
            return
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.setWindowIcon(icon)
        self._tray_icon = QSystemTrayIcon(icon, self)
        tray_menu = QMenu(self)
        restore_action = tray_menu.addAction("Restore")
        restore_action.triggered.connect(self._restore_from_tray)
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.instance().quit)
        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()
        # Keep process alive if they close the window when tray is available
        QApplication.instance().setQuitOnLastWindowClosed(False)

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self._restore_from_tray()

    def _restore_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())