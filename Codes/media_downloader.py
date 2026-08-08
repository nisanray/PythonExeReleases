#!/usr/bin/env python3
"""
Media Downloader Pro
=====================
A polished, macOS-styled desktop downloader built on yt-dlp + PyQt6.

Works with YouTube and any of the 1800+ sites yt-dlp supports. Features a
queue-based download manager with concurrency control, per-item progress,
playlist item selection, subtitle/thumbnail/metadata embedding, format
customization, proxy/rate-limit/cookie support, persistent settings and
history, a system tray icon, light/dark macOS-style themes, and layered
error handling with human-readable diagnostics.

Requires: PyQt6, yt-dlp, ffmpeg (for merging/converting).
    pip install PyQt6 yt-dlp
"""

import os
import sys
import re
import json
import time
import shutil
import traceback
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yt_dlp

from PyQt6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLineEdit, QPushButton, QLabel, QProgressBar, QFileDialog, QTextEdit,
    QRadioButton, QButtonGroup, QMessageBox, QComboBox, QSpinBox, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QTabWidget,
    QGroupBox, QFormLayout, QSplitter, QToolButton, QMenu, QSystemTrayIcon,
    QStyle, QStatusBar, QFrame, QSizePolicy, QDialog, QDialogButtonBox,
    QPlainTextEdit, QScrollArea, QListWidget, QListWidgetItem
)
from PyQt6.QtGui import (
    QFont, QIcon, QAction, QColor, QPalette, QDragEnterEvent, QDropEvent,
    QFontDatabase, QPixmap
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QObject, QRunnable, QThreadPool, QSettings,
    QTimer, QSize, QMimeData
)

APP_ORG = "LocalTools"
APP_NAME = "MediaDownloaderPro"
APP_DISPLAY_NAME = "Media Downloader Pro"
APP_VERSION = "1.0.0"

HISTORY_FILE = Path.home() / ".media_downloader_pro" / "history.json"
LOG_FILE = Path.home() / ".media_downloader_pro" / "app.log"

# ----------------------------------------------------------------------------
# macOS-inspired style sheets (light + dark). PyQt6 has no native "vibrancy",
# so this approximates the macOS Big Sur / Sonoma look with QSS: rounded
# corners, soft shadows via borders, SF-Pro-like font fallbacks, translucent
# grouping, and macOS system accent blue.
# ----------------------------------------------------------------------------

MAC_FONT_FALLBACKS = [
    "SF Pro Text", "SF Pro Display", "Helvetica Neue", "Segoe UI", "Inter",
    "Cantarell", "Ubuntu", "Noto Sans", "Arial", "sans-serif"
]
MAC_FONT_STACK = ", ".join(f'"{f}"' if " " in f else f for f in MAC_FONT_FALLBACKS)

LIGHT_QSS = f"""
* {{
    font-family: {MAC_FONT_STACK};
    outline: none;
}}
QWidget {{
    background-color: #ECECEC;
    color: #1D1D1F;
    font-size: 13px;
}}
QMainWindow {{
    background-color: #ECECEC;
}}
QMenuBar {{
    background-color: #F5F5F7;
    border-bottom: 1px solid #D6D6D8;
    padding: 2px 4px;
}}
QMenuBar::item {{
    padding: 4px 10px;
    border-radius: 5px;
    background: transparent;
}}
QMenuBar::item:selected {{
    background-color: #E2E2E4;
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}
QGroupBox {{
    background-color: #FFFFFF;
    border: 1px solid #D9D9DC;
    border-radius: 10px;
    margin-top: 14px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #3A3A3C;
}}
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox {{
    background-color: #FFFFFF;
    border: 1px solid #D0D0D3;
    border-radius: 7px;
    padding: 6px 8px;
    selection-background-color: #0A84FF;
    selection-color: white;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {{
    border: 1px solid #0A84FF;
}}
QLineEdit:disabled, QComboBox:disabled {{
    color: #A0A0A5;
    background-color: #F2F2F4;
}}
QPushButton {{
    background-color: #FFFFFF;
    border: 1px solid #D0D0D3;
    border-radius: 7px;
    padding: 6px 14px;
    color: #1D1D1F;
}}
QPushButton:hover {{
    background-color: #F5F5F7;
}}
QPushButton:pressed {{
    background-color: #E8E8EA;
}}
QPushButton:disabled {{
    color: #B0B0B5;
    background-color: #F2F2F4;
    border: 1px solid #E2E2E4;
}}
QPushButton#PrimaryButton {{
    background-color: #0A84FF;
    color: white;
    border: 1px solid #0A84FF;
    font-weight: 600;
}}
QPushButton#PrimaryButton:hover {{
    background-color: #1A8CFF;
}}
QPushButton#PrimaryButton:pressed {{
    background-color: #006FE0;
}}
QPushButton#PrimaryButton:disabled {{
    background-color: #B9DBFF;
    border: 1px solid #B9DBFF;
    color: #F0F6FF;
}}
QPushButton#DangerButton {{
    background-color: #FF3B30;
    color: white;
    border: 1px solid #FF3B30;
    font-weight: 600;
}}
QPushButton#DangerButton:hover {{
    background-color: #FF5147;
}}
QPushButton#DangerButton:disabled {{
    background-color: #FFC2BD;
    border: 1px solid #FFC2BD;
    color: #FFF3F2;
}}
QTableWidget {{
    background-color: #FFFFFF;
    border: 1px solid #D9D9DC;
    border-radius: 10px;
    gridline-color: #EDEDEF;
    selection-background-color: #D6E9FF;
    selection-color: #1D1D1F;
}}
QHeaderView::section {{
    background-color: #F5F5F7;
    color: #6E6E73;
    padding: 6px;
    border: none;
    border-bottom: 1px solid #D9D9DC;
    font-weight: 600;
}}
QProgressBar {{
    background-color: #E5E5E7;
    border: none;
    border-radius: 6px;
    height: 10px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: #0A84FF;
    border-radius: 6px;
}}
QTabWidget::pane {{
    border: 1px solid #D9D9DC;
    border-radius: 10px;
    background: #FFFFFF;
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    padding: 7px 16px;
    margin-right: 2px;
    color: #6E6E73;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: #0A84FF;
    border-bottom: 2px solid #0A84FF;
    font-weight: 600;
}}
QStatusBar {{
    background-color: #F5F5F7;
    border-top: 1px solid #D6D6D8;
    color: #6E6E73;
}}
QCheckBox, QRadioButton {{
    spacing: 8px;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 11px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #C7C7CC;
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: #A8A8AE;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QToolTip {{
    background-color: #3A3A3C;
    color: white;
    border: none;
    padding: 4px 8px;
    border-radius: 4px;
}}
QMenu {{
    background-color: #FBFBFD;
    border: 1px solid #D9D9DC;
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 22px;
    border-radius: 5px;
}}
QMenu::item:selected {{
    background-color: #0A84FF;
    color: white;
}}
"""

DARK_QSS = f"""
* {{
    font-family: {MAC_FONT_STACK};
    outline: none;
}}
QWidget {{
    background-color: #1E1E1E;
    color: #F2F2F2;
    font-size: 13px;
}}
QMainWindow {{
    background-color: #1E1E1E;
}}
QMenuBar {{
    background-color: #262626;
    border-bottom: 1px solid #363636;
    padding: 2px 4px;
}}
QMenuBar::item {{
    padding: 4px 10px;
    border-radius: 5px;
    background: transparent;
}}
QMenuBar::item:selected {{
    background-color: #343436;
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}
QGroupBox {{
    background-color: #2A2A2C;
    border: 1px solid #3A3A3C;
    border-radius: 10px;
    margin-top: 14px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
    color: #E5E5E7;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #C7C7CC;
}}
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox {{
    background-color: #1C1C1E;
    border: 1px solid #3A3A3C;
    border-radius: 7px;
    padding: 6px 8px;
    color: #F2F2F2;
    selection-background-color: #0A84FF;
    selection-color: white;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {{
    border: 1px solid #0A84FF;
}}
QLineEdit:disabled, QComboBox:disabled {{
    color: #6E6E73;
    background-color: #232325;
}}
QPushButton {{
    background-color: #2C2C2E;
    border: 1px solid #3A3A3C;
    border-radius: 7px;
    padding: 6px 14px;
    color: #F2F2F2;
}}
QPushButton:hover {{
    background-color: #343436;
}}
QPushButton:pressed {{
    background-color: #202022;
}}
QPushButton:disabled {{
    color: #6E6E73;
    background-color: #232325;
    border: 1px solid #2C2C2E;
}}
QPushButton#PrimaryButton {{
    background-color: #0A84FF;
    color: white;
    border: 1px solid #0A84FF;
    font-weight: 600;
}}
QPushButton#PrimaryButton:hover {{
    background-color: #2E9BFF;
}}
QPushButton#PrimaryButton:pressed {{
    background-color: #006FE0;
}}
QPushButton#PrimaryButton:disabled {{
    background-color: #1B4D80;
    border: 1px solid #1B4D80;
    color: #7FAFDD;
}}
QPushButton#DangerButton {{
    background-color: #FF453A;
    color: white;
    border: 1px solid #FF453A;
    font-weight: 600;
}}
QPushButton#DangerButton:hover {{
    background-color: #FF6259;
}}
QPushButton#DangerButton:disabled {{
    background-color: #7A2B26;
    border: 1px solid #7A2B26;
    color: #C99490;
}}
QTableWidget {{
    background-color: #1C1C1E;
    border: 1px solid #3A3A3C;
    border-radius: 10px;
    gridline-color: #2C2C2E;
    color: #F2F2F2;
    selection-background-color: #0A3D66;
    selection-color: #FFFFFF;
}}
QHeaderView::section {{
    background-color: #262626;
    color: #9A9A9E;
    padding: 6px;
    border: none;
    border-bottom: 1px solid #3A3A3C;
    font-weight: 600;
}}
QProgressBar {{
    background-color: #3A3A3C;
    border: none;
    border-radius: 6px;
    height: 10px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: #0A84FF;
    border-radius: 6px;
}}
QTabWidget::pane {{
    border: 1px solid #3A3A3C;
    border-radius: 10px;
    background: #1C1C1E;
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    padding: 7px 16px;
    margin-right: 2px;
    color: #9A9A9E;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: #2E9BFF;
    border-bottom: 2px solid #2E9BFF;
    font-weight: 600;
}}
QStatusBar {{
    background-color: #262626;
    border-top: 1px solid #363636;
    color: #9A9A9E;
}}
QCheckBox, QRadioButton {{
    spacing: 8px;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 11px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #48484A;
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: #5A5A5C;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QToolTip {{
    background-color: #3A3A3C;
    color: white;
    border: none;
    padding: 4px 8px;
    border-radius: 4px;
}}
QMenu {{
    background-color: #2A2A2C;
    border: 1px solid #3A3A3C;
    border-radius: 8px;
    padding: 4px;
    color: #F2F2F2;
}}
QMenu::item {{
    padding: 6px 22px;
    border-radius: 5px;
}}
QMenu::item:selected {{
    background-color: #0A84FF;
    color: white;
}}
"""

# ----------------------------------------------------------------------------
# Data model
# ----------------------------------------------------------------------------

STATUS_QUEUED = "Queued"
STATUS_FETCHING = "Fetching info"
STATUS_DOWNLOADING = "Downloading"
STATUS_PAUSED = "Paused"
STATUS_COMPLETED = "Completed"
STATUS_ERROR = "Error"
STATUS_CANCELLED = "Cancelled"

STATUS_COLORS_LIGHT = {
    STATUS_QUEUED: "#8E8E93",
    STATUS_FETCHING: "#FF9F0A",
    STATUS_DOWNLOADING: "#0A84FF",
    STATUS_PAUSED: "#FF9F0A",
    STATUS_COMPLETED: "#30D158",
    STATUS_ERROR: "#FF3B30",
    STATUS_CANCELLED: "#8E8E93",
}


@dataclass
class DownloadOptions:
    """Snapshot of user-selected download options, captured per queue item
    so mid-queue changes to the global form don't retroactively affect
    items already queued."""
    destination: str
    quality_key: str = "1080p"
    media_type: str = "video"           # "video" | "audio"
    audio_format: str = "mp3"           # mp3 | m4a | wav | flac | opus
    audio_bitrate: str = "192"
    container: str = "mp4"              # mp4 | mkv | webm
    filename_template: str = "%(title)s.%(ext)s"
    download_subs: bool = False
    sub_langs: str = "en"
    embed_subs: bool = False
    embed_thumbnail: bool = False
    embed_metadata: bool = True
    playlist_items: str = ""            # e.g. "1,3,5-8"; empty = all
    playlist_mode: str = "auto"         # "auto" | "single" | "full" | "select"
    playlist_reverse: bool = False
    playlist_end: int = 0                # 0 = unset; "limit to first N items"
    use_download_archive: bool = False
    rate_limit: str = ""                # e.g. "2M"; empty = unlimited
    proxy: str = ""
    cookies_from_browser: str = ""      # "", "chrome", "firefox", ...
    retries: int = 10
    custom_format: str = ""             # raw yt-dlp -f string; overrides quality_key
    sponsorblock_remove: bool = False
    write_thumbnail_file: bool = False
    write_info_json: bool = False
    embed_chapters: bool = False
    concurrent_fragments: int = 1
    date_after: str = ""                # yt-dlp "dateafter" filter, e.g. 20240101
    date_before: str = ""               # yt-dlp "datebefore" filter
    match_filter: str = ""              # raw yt-dlp --match-filter expression
    min_filesize: str = ""              # e.g. "10M"
    max_filesize: str = ""              # e.g. "2G"


@dataclass
class QueueItem:
    url: str
    options: DownloadOptions
    title: str = ""
    status: str = STATUS_QUEUED
    percent: float = 0.0
    speed: str = ""
    eta: str = ""
    filesize: str = ""
    error_message: str = ""
    row: int = -1
    uid: int = field(default_factory=lambda: int(time.time() * 1_000_000) % 10_000_000)


# ----------------------------------------------------------------------------
# Error classification — turns yt-dlp / OS exceptions into short, human
# readable diagnostics plus a suggested fix, instead of a raw traceback.
# ----------------------------------------------------------------------------

def classify_error(exc: Exception) -> tuple[str, str]:
    """Returns (short_message, suggestion)."""
    text = str(exc)
    low = text.lower()

    if isinstance(exc, yt_dlp.utils.DownloadCancelled):
        return "Cancelled by user", ""

    if "ffmpeg" in low and ("not found" in low or "no such file" in low):
        return ("FFmpeg is missing or not on PATH",
                "Install FFmpeg and make sure it's on your system PATH, "
                "or set a custom FFmpeg path in Preferences.")

    if "http error 429" in low or "429" in low and "too many" in low:
        return ("Rate limited by the server (HTTP 429)",
                "Wait a bit and retry, or set a rate limit / use a proxy in Advanced options.")

    if "http error 403" in low or "forbidden" in low:
        return ("Access forbidden (HTTP 403)",
                "The source may require sign-in cookies. Try setting "
                "'Cookies from browser' in Advanced options.")

    if "http error 404" in low or "not found" in low and "video unavailable" not in low:
        return ("Content not found (HTTP 404)",
                "Double check the URL — the video/playlist may have been removed or the link is wrong.")

    if "private video" in low:
        return ("This video is private",
                "You need to be logged in with an account that has access. Try 'Cookies from browser'.")

    if "sign in" in low or "login required" in low or "age" in low and "restrict" in low:
        return ("Sign-in or age verification required",
                "Set 'Cookies from browser' in Advanced options so yt-dlp can use your logged-in session.")

    if "video unavailable" in low:
        return ("Video unavailable",
                "It may be deleted, region-locked, or blocked in your country. A proxy/VPN may help with region locks.")

    if "unsupported url" in low or "no extractor" in low:
        return ("This URL/site isn't supported",
                "Double-check the link. yt-dlp supports 1800+ sites, but this one isn't recognized.")

    if "unable to download webpage" in low or "urlopen error" in low or "connection" in low or "timed out" in low or "timeout" in low:
        return ("Network error while contacting the server",
                "Check your internet connection and try again. A proxy may help if the site is blocked for you.")

    if "no space left" in low or "disk quota" in low:
        return ("Not enough disk space",
                "Free up space on the destination drive or choose a different folder.")

    if "permission denied" in low:
        return ("Permission denied writing to the destination folder",
                "Choose a folder you have write access to, or fix folder permissions.")

    if "requested format not available" in low:
        return ("The chosen quality/format isn't available for this video",
                "Try a lower quality, 'Best available', or enter a custom format string in Advanced options.")

    if "postprocessing" in low:
        return ("Post-processing (conversion/merge) failed",
                "Verify FFmpeg is installed and up to date; try a different container/format.")

    # Fallback — trim to something readable
    short = text.strip().splitlines()[0] if text.strip() else "Unknown error"
    if len(short) > 160:
        short = short[:157] + "..."
    return (short, "Check the log panel for full details.")


# ----------------------------------------------------------------------------
# Worker plumbing — QRunnable + a QObject signal bridge (QRunnable itself
# cannot emit signals), run inside a QThreadPool so we get real, capped
# concurrency instead of one QThread per download.
# ----------------------------------------------------------------------------

class WorkerSignals(QObject):
    progress = pyqtSignal(int, float, str, str, str)   # uid, percent, speed, eta, filesize
    status = pyqtSignal(int, str)                       # uid, status text
    log = pyqtSignal(str)
    title_fetched = pyqtSignal(int, str, bool, int)      # uid, title, is_playlist, entry_count
    playlist_entries = pyqtSignal(int, str, list)        # uid, playlist_title, [{"title":..., "id":...}]
    finished = pyqtSignal(int)                           # uid
    error = pyqtSignal(int, str, str)                    # uid, short_message, suggestion


class DownloadRunnable(QRunnable):
    """One queued download, executed on the shared QThreadPool."""

    def __init__(self, item: QueueItem, ffmpeg_path: str = ""):
        super().__init__()
        self.item = item
        self.ffmpeg_path = ffmpeg_path
        self.signals = WorkerSignals()
        self._cancel_flag = {"cancel": False}
        self.setAutoDelete(True)

    def cancel(self):
        self._cancel_flag["cancel"] = True

    # -- format string construction -----------------------------------
    def _build_format(self, opt: DownloadOptions) -> str:
        if opt.custom_format.strip():
            return opt.custom_format.strip()
        if opt.media_type == "audio":
            return "bestaudio/best"
        height_map = {
            "2160p": 2160, "1440p": 1440, "1080p": 1080,
            "720p": 720, "480p": 480, "360p": 360,
        }
        if opt.quality_key == "best":
            return "bestvideo+bestaudio/best"
        if opt.quality_key == "worst":
            return "worstvideo+worstaudio/worst"
        h = height_map.get(opt.quality_key)
        if h:
            return f"bestvideo[height<={h}]+bestaudio/best[height<={h}]"
        return "bestvideo+bestaudio/best"

    def _build_postprocessors(self, opt: DownloadOptions) -> list:
        pps = []
        if opt.media_type == "audio":
            pps.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": opt.audio_format,
                "preferredquality": opt.audio_bitrate,
            })
        else:
            pps.append({"key": "FFmpegVideoConvertor", "preferedformat": opt.container})

        if opt.embed_thumbnail:
            pps.append({"key": "EmbedThumbnail"})
        if opt.embed_metadata or opt.embed_chapters:
            pps.append({
                "key": "FFmpegMetadata",
                "add_metadata": opt.embed_metadata,
                "add_chapters": opt.embed_chapters,
            })
        if opt.embed_subs and opt.download_subs:
            pps.append({"key": "FFmpegEmbedSubtitle"})
        if opt.sponsorblock_remove:
            pps.append({"key": "SponsorBlock", "categories": ["sponsor"]})
            pps.append({"key": "ModifyChapters", "remove_sponsor_segments": ["sponsor"]})
        return pps

    @staticmethod
    def _parse_size_to_bytes(s: str) -> Optional[str]:
        """Pass through a size string (e.g. '10M', '2G') for yt-dlp's
        filesize filter syntax — it accepts these directly, no conversion
        needed, but we validate the shape so a typo doesn't get silently
        ignored."""
        s = s.strip()
        if not s:
            return None
        if not re.match(r"^\d+(\.\d+)?[KMGkmg]?$", s):
            return None
        return s

    def _progress_hook(self, d):
        if self._cancel_flag["cancel"]:
            raise yt_dlp.utils.DownloadCancelled("Download stopped by user")

        status = d.get("status")
        uid = self.item.uid
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            done = d.get("downloaded_bytes") or 0
            percent = (done / total * 100.0) if total else 0.0
            speed = d.get("_speed_str", "") or (d.get("speed") and f"{d['speed']/1024:.0f} KB/s") or ""
            eta_val = d.get("eta")
            eta = f"{eta_val}s" if isinstance(eta_val, int) else ""
            size_str = d.get("_total_bytes_str", "") or ""
            self.signals.progress.emit(uid, percent, str(speed), eta, str(size_str))
        elif status == "finished":
            self.signals.progress.emit(uid, 100.0, "", "", "")
            self.signals.log.emit(f"Downloaded, now post-processing: {os.path.basename(d.get('filename', ''))}")

    def run(self):
        opt = self.item.options
        uid = self.item.uid
        try:
            self.signals.status.emit(uid, STATUS_DOWNLOADING)

            outtmpl = os.path.join(opt.destination, opt.filename_template)
            has_selected_items = bool(opt.playlist_items.strip())

            ydl_opts = {
                "outtmpl": outtmpl,
                "format": self._build_format(opt),
                "progress_hooks": [self._progress_hook],
                "postprocessors": self._build_postprocessors(opt),
                "ignoreerrors": has_selected_items or opt.playlist_mode in ("full", "select"),
                "retries": opt.retries,
                "fragment_retries": opt.retries,
                "continuedl": True,
                "noprogress": False,
                "merge_output_format": opt.container if opt.media_type == "video" else None,
                "writesubtitles": opt.download_subs,
                "writeautomaticsub": opt.download_subs,
                "subtitleslangs": [l.strip() for l in opt.sub_langs.split(",") if l.strip()] or ["en"],
                "writethumbnail": opt.write_thumbnail_file or opt.embed_thumbnail,
                "writeinfojson": opt.write_info_json,
                "quiet": True,
                "no_warnings": True,
                "logger": _YdlLogger(self.signals),
            }

            # -- playlist handling -----------------------------------
            if opt.playlist_mode == "single":
                ydl_opts["noplaylist"] = True
            elif opt.playlist_mode in ("full", "select"):
                ydl_opts["noplaylist"] = False
            # "auto" leaves yt-dlp's own default (downloads the playlist if
            # the URL points to one, single video otherwise).

            if has_selected_items:
                ydl_opts["playlist_items"] = opt.playlist_items.strip()
            elif opt.playlist_end and opt.playlist_end > 0:
                ydl_opts["playlistend"] = opt.playlist_end

            if opt.playlist_reverse:
                ydl_opts["playlistreverse"] = True

            if opt.use_download_archive:
                archive_path = os.path.join(opt.destination, ".download_archive.txt")
                ydl_opts["download_archive"] = archive_path

            # -- filters -----------------------------------------------
            if opt.date_after.strip():
                ydl_opts["dateafter"] = opt.date_after.strip()
            if opt.date_before.strip():
                ydl_opts["datebefore"] = opt.date_before.strip()

            min_size = self._parse_size_to_bytes(opt.min_filesize)
            if min_size:
                ydl_opts["min_filesize"] = min_size
            max_size = self._parse_size_to_bytes(opt.max_filesize)
            if max_size:
                ydl_opts["max_filesize"] = max_size

            if opt.match_filter.strip():
                try:
                    ydl_opts["match_filter"] = yt_dlp.utils.match_filter_func(opt.match_filter.strip())
                except Exception as exc:  # noqa: BLE001 - bad filter shouldn't kill the download
                    self.signals.log.emit(f"WARNING: ignoring invalid match filter ({exc})")

            # -- performance / network ----------------------------------
            if opt.concurrent_fragments and opt.concurrent_fragments > 1:
                ydl_opts["concurrent_fragment_downloads"] = opt.concurrent_fragments

            if opt.rate_limit.strip():
                ydl_opts["ratelimit"] = self._parse_rate(opt.rate_limit.strip())

            if opt.proxy.strip():
                ydl_opts["proxy"] = opt.proxy.strip()

            if opt.cookies_from_browser.strip():
                ydl_opts["cookiesfrombrowser"] = (opt.cookies_from_browser.strip(),)

            if self.ffmpeg_path.strip():
                ydl_opts["ffmpeg_location"] = self.ffmpeg_path.strip()

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.item.url])

            if self._cancel_flag["cancel"]:
                self.signals.status.emit(uid, STATUS_CANCELLED)
            else:
                self.signals.status.emit(uid, STATUS_COMPLETED)
                self.signals.finished.emit(uid)

        except yt_dlp.utils.DownloadCancelled:
            self.signals.status.emit(uid, STATUS_CANCELLED)
        except Exception as exc:  # noqa: BLE001 - want to surface any failure gracefully
            short, suggestion = classify_error(exc)
            self.signals.log.emit(f"ERROR [{self.item.url}]: {exc}\n{traceback.format_exc()}")
            self.signals.status.emit(uid, STATUS_ERROR)
            self.signals.error.emit(uid, short, suggestion)

    @staticmethod
    def _parse_rate(s: str) -> float:
        s = s.strip().upper()
        mult = 1
        if s.endswith("K"):
            mult, s = 1024, s[:-1]
        elif s.endswith("M"):
            mult, s = 1024 * 1024, s[:-1]
        try:
            return float(s) * mult
        except ValueError:
            return 0


class _YdlLogger:
    """Routes yt-dlp's internal logger into our log signal instead of stdout."""

    def __init__(self, signals: WorkerSignals):
        self.signals = signals

    def debug(self, msg):
        if msg.startswith("[debug] "):
            return
        self.signals.log.emit(msg)

    def info(self, msg):
        self.signals.log.emit(msg)

    def warning(self, msg):
        self.signals.log.emit(f"WARNING: {msg}")

    def error(self, msg):
        self.signals.log.emit(f"ERROR: {msg}")


class InfoFetchRunnable(QRunnable):
    """Probes a URL with extract_flat to determine title / playlist-ness
    without downloading anything, so the UI can show useful info fast.
    When emit_entries is True, also emits the full per-item title list so
    the UI can offer a checkbox picker (used by 'Preview Playlist Items')."""

    def __init__(self, uid: int, url: str, cookies_from_browser: str = "", proxy: str = "",
                 emit_entries: bool = False):
        super().__init__()
        self.uid = uid
        self.url = url
        self.cookies_from_browser = cookies_from_browser
        self.proxy = proxy
        self.emit_entries = emit_entries
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    def run(self):
        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": "in_playlist",
                "skip_download": True,
            }
            if self.cookies_from_browser.strip():
                ydl_opts["cookiesfrombrowser"] = (self.cookies_from_browser.strip(),)
            if self.proxy.strip():
                ydl_opts["proxy"] = self.proxy.strip()

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)

            if info is None:
                raise ValueError("No information returned for this URL")

            is_playlist = info.get("_type") == "playlist" or "entries" in info
            entries = list(info.get("entries") or []) if is_playlist else []
            title = info.get("title") or (entries[0].get("title") if entries else self.url)
            self.signals.title_fetched.emit(self.uid, title, is_playlist, len(entries))

            if self.emit_entries and is_playlist:
                simplified = [
                    {"title": e.get("title") or e.get("id") or f"Item {i + 1}", "id": e.get("id", "")}
                    for i, e in enumerate(entries)
                ]
                self.signals.playlist_entries.emit(self.uid, title, simplified)

        except Exception as exc:  # noqa: BLE001
            short, suggestion = classify_error(exc)
            self.signals.error.emit(self.uid, short, suggestion)


# ----------------------------------------------------------------------------
# Preferences dialog
# ----------------------------------------------------------------------------

class PreferencesDialog(QDialog):
    def __init__(self, settings: QSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(440)
        self.setModal(True)

        layout = QVBoxLayout(self)

        form_box = QGroupBox("General")
        form = QFormLayout()

        self.default_folder_edit = QLineEdit(self.settings.value("default_folder", str(Path.home() / "Downloads")))
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.default_folder_edit)
        folder_row.addWidget(browse_btn)
        form.addRow("Default download folder:", folder_row)

        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 8)
        self.concurrency_spin.setValue(int(self.settings.value("max_concurrent", 2)))
        form.addRow("Max simultaneous downloads:", self.concurrency_spin)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        self.theme_combo.setCurrentText(self.settings.value("theme", "Light"))
        form.addRow("Appearance:", self.theme_combo)

        self.ffmpeg_edit = QLineEdit(self.settings.value("ffmpeg_path", ""))
        self.ffmpeg_edit.setPlaceholderText("Leave blank to use FFmpeg from system PATH")
        ffmpeg_browse = QPushButton("Browse…")
        ffmpeg_browse.clicked.connect(self._browse_ffmpeg)
        ffmpeg_row = QHBoxLayout()
        ffmpeg_row.addWidget(self.ffmpeg_edit)
        ffmpeg_row.addWidget(ffmpeg_browse)
        form.addRow("Custom FFmpeg path:", ffmpeg_row)

        form_box.setLayout(form)
        layout.addWidget(form_box)

        behavior_box = QGroupBox("Behavior")
        behavior_form = QFormLayout()

        self.notify_check = QCheckBox("Show a notification when a download finishes")
        self.notify_check.setChecked(self.settings.value("notify_on_finish", "true") == "true")
        behavior_form.addRow(self.notify_check)

        self.tray_check = QCheckBox("Minimize to system tray instead of closing")
        self.tray_check.setChecked(self.settings.value("minimize_to_tray", "true") == "true")
        behavior_form.addRow(self.tray_check)

        self.autostart_check = QCheckBox("Automatically start downloads when added to queue")
        self.autostart_check.setChecked(self.settings.value("auto_start", "false") == "true")
        behavior_form.addRow(self.autostart_check)

        behavior_box.setLayout(behavior_form)
        layout.addWidget(behavior_box)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Default Folder", self.default_folder_edit.text())
        if folder:
            self.default_folder_edit.setText(folder)

    def _browse_ffmpeg(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select FFmpeg Executable")
        if path:
            self.ffmpeg_edit.setText(path)

    def save(self):
        self.settings.setValue("default_folder", self.default_folder_edit.text())
        self.settings.setValue("max_concurrent", self.concurrency_spin.value())
        self.settings.setValue("theme", self.theme_combo.currentText())
        self.settings.setValue("ffmpeg_path", self.ffmpeg_edit.text())
        self.settings.setValue("notify_on_finish", "true" if self.notify_check.isChecked() else "false")
        self.settings.setValue("minimize_to_tray", "true" if self.tray_check.isChecked() else "false")
        self.settings.setValue("auto_start", "true" if self.autostart_check.isChecked() else "false")


# ----------------------------------------------------------------------------
# Playlist preview / selective-item picker
# ----------------------------------------------------------------------------

class PlaylistPreviewDialog(QDialog):
    """Lets the user tick exactly which videos in a playlist to queue,
    instead of an all-or-nothing download."""

    def __init__(self, playlist_title: str, entries: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f'Playlist: "{playlist_title}"')
        self.setMinimumSize(520, 480)
        self.setModal(True)
        self.entries = entries

        layout = QVBoxLayout(self)

        info_label = QLabel(f"{len(entries)} item(s) found. Choose which to queue:")
        info_label.setStyleSheet("color: #8E8E93;")
        layout.addWidget(info_label)

        self.list_widget = QListWidget()
        for i, entry in enumerate(entries, start=1):
            item = QListWidgetItem(f"{i}. {entry.get('title', 'Untitled')}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget, stretch=1)

        btn_row = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self._set_all(Qt.CheckState.Checked))
        btn_row.addWidget(select_all_btn)

        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(lambda: self._set_all(Qt.CheckState.Unchecked))
        btn_row.addWidget(select_none_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _set_all(self, state: Qt.CheckState):
        for row in range(self.list_widget.count()):
            self.list_widget.item(row).setCheckState(state)

    def selected_playlist_items_string(self) -> str:
        """Returns a yt-dlp playlist_items string like '1,3,5-8' — collapses
        consecutive selected indices into ranges for a compact result."""
        selected = [
            i + 1 for i in range(self.list_widget.count())
            if self.list_widget.item(i).checkState() == Qt.CheckState.Checked
        ]
        if not selected:
            return ""
        if len(selected) == len(self.entries):
            return ""  # everything selected == no filter needed

        ranges = []
        start = prev = selected[0]
        for n in selected[1:]:
            if n == prev + 1:
                prev = n
                continue
            ranges.append(f"{start}-{prev}" if start != prev else str(start))
            start = prev = n
        ranges.append(f"{start}-{prev}" if start != prev else str(start))
        return ",".join(ranges)


# ----------------------------------------------------------------------------
# History store (simple JSON-backed persistence)
# ----------------------------------------------------------------------------

class HistoryStore:
    def __init__(self, path: Path = HISTORY_FILE):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._entries = []
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self._entries = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self._entries = []

    def save(self):
        try:
            self.path.write_text(json.dumps(self._entries, indent=2), encoding="utf-8")
        except OSError:
            pass  # history is a convenience feature; never crash the app over it

    def add(self, title: str, url: str, destination: str, status: str):
        self._entries.insert(0, {
            "title": title,
            "url": url,
            "destination": destination,
            "status": status,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        self._entries = self._entries[:500]
        self.save()

    def clear(self):
        self._entries = []
        self.save()

    def all(self):
        return list(self._entries)


# ----------------------------------------------------------------------------
# Main window
# ----------------------------------------------------------------------------

QUALITY_ITEMS = [
    ("Best available", "best"),
    ("2160p (4K)", "2160p"),
    ("1440p (2K)", "1440p"),
    ("1080p (Full HD)", "1080p"),
    ("720p (HD)", "720p"),
    ("480p", "480p"),
    ("360p", "360p"),
    ("Worst available (smallest file)", "worst"),
]

COLUMN_TITLE, COLUMN_STATUS, COLUMN_PROGRESS, COLUMN_SPEED, COLUMN_ETA, COLUMN_SIZE = range(6)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings(APP_ORG, APP_NAME)
        self.history = HistoryStore()
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(int(self.settings.value("max_concurrent", 2)))

        self.queue_items: dict[int, QueueItem] = {}
        self.runnables: dict[int, DownloadRunnable] = {}
        self.row_by_uid: dict[int, int] = {}

        self.setWindowTitle(APP_DISPLAY_NAME)
        self.setMinimumSize(760, 480)
        self._size_to_fit_screen()
        self.setAcceptDrops(True)

        self._build_ui()
        self._build_menu()
        self._build_tray()
        self._apply_theme(self.settings.value("theme", "Light"))
        self._check_ffmpeg(startup=True)

        self.statusBar().showMessage("Ready")

    def _size_to_fit_screen(self):
        """Size the window to comfortably fit within whatever screen is
        actually available instead of a fixed pixel size that can overflow
        smaller laptop screens."""
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None

        if available is not None:
            # Aim for a 16:9-ish window, capped by the available screen so
            # it never runs into the dock/taskbar or gets clipped.
            target_w = min(1200, int(available.width() * 0.85))
            target_h = min(int(target_w * 9 / 16) + 160, int(available.height() * 0.92))
            self.resize(target_w, target_h)
            frame = self.frameGeometry()
            frame.moveCenter(available.center())
            self.move(frame.topLeft())
        else:
            self.resize(1000, 680)

    # -- UI construction -------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(10)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, stretch=1)

        downloads_scroll = QScrollArea()
        downloads_scroll.setWidgetResizable(True)
        downloads_scroll.setFrameShape(QFrame.Shape.NoFrame)
        downloads_scroll.setWidget(self._build_downloads_tab())
        self.tabs.addTab(downloads_scroll, "Downloads")
        self.tabs.addTab(self._build_history_tab(), "History")

        self.setStatusBar(QStatusBar())


    def _build_downloads_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        # URL input row
        url_group = QGroupBox("Add to queue")
        url_layout = QVBoxLayout()
        row1 = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste a video or playlist URL (YouTube and 1800+ other sites)…")
        self.url_input.returnPressed.connect(self.on_add_to_queue)
        row1.addWidget(self.url_input, stretch=1)

        paste_btn = QPushButton("Paste")
        paste_btn.clicked.connect(self._paste_url)
        row1.addWidget(paste_btn)

        fetch_btn = QPushButton("Fetch Info")
        fetch_btn.setToolTip("Probe the URL to confirm the title and whether it's a playlist, without downloading")
        fetch_btn.clicked.connect(self._fetch_info_only)
        row1.addWidget(fetch_btn)

        add_btn = QPushButton("Add to Queue")
        add_btn.setObjectName("PrimaryButton")
        add_btn.clicked.connect(self.on_add_to_queue)
        row1.addWidget(add_btn)
        url_layout.addLayout(row1)

        hint = QLabel("Tip: you can also drag & drop links here, or paste multiple URLs (one per line).")
        hint.setStyleSheet("color: #8E8E93; font-size: 11px;")
        url_layout.addWidget(hint)

        url_group.setLayout(url_layout)
        layout.addWidget(url_group)

        # Options
        options_row = QHBoxLayout()
        options_row.addWidget(self._build_basic_options_group(), stretch=1)
        options_row.addWidget(self._build_advanced_options_group(), stretch=1)
        layout.addLayout(options_row)

        # Queue table
        queue_group = QGroupBox("Queue")
        queue_layout = QVBoxLayout()

        self.queue_table = QTableWidget(0, 6)
        self.queue_table.setHorizontalHeaderLabels(["Title", "Status", "Progress", "Speed", "ETA", "Size"])
        self.queue_table.horizontalHeader().setSectionResizeMode(COLUMN_TITLE, QHeaderView.ResizeMode.Stretch)
        for c in (COLUMN_STATUS, COLUMN_SPEED, COLUMN_ETA, COLUMN_SIZE):
            self.queue_table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.queue_table.horizontalHeader().setSectionResizeMode(COLUMN_PROGRESS, QHeaderView.ResizeMode.Fixed)
        self.queue_table.setColumnWidth(COLUMN_PROGRESS, 160)
        self.queue_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.queue_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.queue_table.verticalHeader().setVisible(False)
        self.queue_table.setMinimumHeight(220)
        queue_layout.addWidget(self.queue_table)

        controls_row = QHBoxLayout()
        self.start_btn = QPushButton("Start Queue")
        self.start_btn.setObjectName("PrimaryButton")
        self.start_btn.clicked.connect(self.on_start_queue)
        controls_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop All")
        self.stop_btn.setObjectName("DangerButton")
        self.stop_btn.clicked.connect(self.on_stop_all)
        self.stop_btn.setEnabled(False)
        controls_row.addWidget(self.stop_btn)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self.on_remove_selected)
        controls_row.addWidget(remove_btn)

        clear_btn = QPushButton("Clear Completed")
        clear_btn.clicked.connect(self.on_clear_completed)
        controls_row.addWidget(clear_btn)

        controls_row.addStretch()

        self.log_toggle_btn = QPushButton("Show Log ▾")
        self.log_toggle_btn.clicked.connect(self._toggle_log)
        controls_row.addWidget(self.log_toggle_btn)

        queue_layout.addLayout(controls_row)
        queue_group.setLayout(queue_layout)
        layout.addWidget(queue_group, stretch=1)

        # Log panel (hidden by default)
        self.log_panel = QPlainTextEdit()
        self.log_panel.setReadOnly(True)
        self.log_panel.setMaximumHeight(160)
        self.log_panel.setVisible(False)
        self.log_panel.setPlaceholderText("Detailed log output will appear here…")
        layout.addWidget(self.log_panel)

        return page

    def _build_basic_options_group(self) -> QGroupBox:
        box = QGroupBox("Options")
        form = QFormLayout()
        form.setSpacing(8)

        type_row = QHBoxLayout()
        self.type_group = QButtonGroup(self)
        self.video_radio = QRadioButton("Video")
        self.audio_radio = QRadioButton("Audio only")
        self.video_radio.setChecked(True)
        self.type_group.addButton(self.video_radio)
        self.type_group.addButton(self.audio_radio)
        self.video_radio.toggled.connect(self._on_media_type_changed)
        type_row.addWidget(self.video_radio)
        type_row.addWidget(self.audio_radio)
        type_row.addStretch()
        form.addRow("Type:", type_row)

        self.quality_combo = QComboBox()
        for label, _ in QUALITY_ITEMS:
            self.quality_combo.addItem(label)
        self.quality_combo.setCurrentText("1080p (Full HD)")
        form.addRow("Video quality:", self.quality_combo)

        self.container_combo = QComboBox()
        self.container_combo.addItems(["mp4", "mkv", "webm"])
        form.addRow("Video container:", self.container_combo)

        self.audio_format_combo = QComboBox()
        self.audio_format_combo.addItems(["mp3", "m4a", "wav", "flac", "opus"])
        self.audio_format_combo.setEnabled(False)
        form.addRow("Audio format:", self.audio_format_combo)

        self.audio_bitrate_combo = QComboBox()
        self.audio_bitrate_combo.addItems(["320", "256", "192", "128", "96"])
        self.audio_bitrate_combo.setCurrentText("192")
        self.audio_bitrate_combo.setEnabled(False)
        form.addRow("Audio bitrate (kbps):", self.audio_bitrate_combo)

        folder_row = QHBoxLayout()
        self.folder_input = QLineEdit(self.settings_folder_default())
        folder_btn = QPushButton("Browse…")
        folder_btn.clicked.connect(self._select_folder)
        folder_row.addWidget(self.folder_input)
        folder_row.addWidget(folder_btn)
        form.addRow("Destination:", folder_row)

        self.filename_template_edit = QLineEdit("%(title)s.%(ext)s")
        self.filename_template_edit.setToolTip(
            "yt-dlp output template — pick a preset below or type your own."
        )
        form.addRow("Filename template:", self.filename_template_edit)

        self.filename_preset_combo = QComboBox()
        self.filename_preset_combo.addItems([
            "Custom (edit above)",
            "%(title)s.%(ext)s",
            "%(playlist_index)s - %(title)s.%(ext)s",
            "%(playlist_title)s/%(playlist_index)s - %(title)s.%(ext)s",
            "%(uploader)s/%(title)s.%(ext)s",
            "%(upload_date)s - %(title)s.%(ext)s",
            "%(uploader)s/%(playlist_title)s/%(playlist_index)s - %(title)s.%(ext)s",
        ])
        self.filename_preset_combo.setToolTip("Quick presets — especially useful for playlists (keeps items organized/numbered)")
        self.filename_preset_combo.currentTextChanged.connect(self._on_filename_preset_changed)
        form.addRow("Template preset:", self.filename_preset_combo)

        box.setLayout(form)
        return box

    def _on_filename_preset_changed(self, text: str):
        if text and text != "Custom (edit above)":
            self.filename_template_edit.setText(text)

    def settings_folder_default(self) -> str:
        return self.settings.value("default_folder", str(Path.home() / "Downloads"))

    def _on_media_type_changed(self):
        is_audio = self.audio_radio.isChecked()
        self.audio_format_combo.setEnabled(is_audio)
        self.audio_bitrate_combo.setEnabled(is_audio)
        self.quality_combo.setEnabled(not is_audio)
        self.container_combo.setEnabled(not is_audio)

    def _build_advanced_options_group(self) -> QGroupBox:
        box = QGroupBox("Advanced")
        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)

        inner_tabs = QTabWidget()
        inner_tabs.addTab(self._build_playlist_tab(), "Playlist")
        inner_tabs.addTab(self._build_filters_tab(), "Filters")
        inner_tabs.addTab(self._build_network_tab(), "Network && Auth")
        inner_tabs.addTab(self._build_files_tab(), "Files && Embedding")
        outer.addWidget(inner_tabs)

        box.setLayout(outer)
        return box

    def _build_playlist_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(8)

        self.playlist_mode_combo = QComboBox()
        self.playlist_mode_combo.addItems([
            "Auto-detect", "Single video only", "Entire playlist", "Select items"
        ])
        self.playlist_mode_combo.setToolTip(
            "Auto-detect: yt-dlp decides based on the URL.\n"
            "Single video only: ignore playlist context, grab just this video.\n"
            "Entire playlist: force-download every item.\n"
            "Select items: use the 'Playlist items' field or Preview picker below."
        )
        self.playlist_mode_combo.currentIndexChanged.connect(self._on_playlist_mode_changed)
        form.addRow("Playlist mode:", self.playlist_mode_combo)

        self.playlist_items_edit = QLineEdit()
        self.playlist_items_edit.setPlaceholderText("e.g. 1,3,5-8 — leave blank for all")
        form.addRow("Playlist items:", self.playlist_items_edit)

        preview_row = QHBoxLayout()
        self.preview_playlist_btn = QPushButton("Preview Playlist Items…")
        self.preview_playlist_btn.setToolTip("Fetch the playlist and tick exactly which videos to queue")
        self.preview_playlist_btn.clicked.connect(self._preview_playlist)
        preview_row.addWidget(self.preview_playlist_btn)
        preview_row.addStretch()
        form.addRow("", preview_row)

        limit_row = QHBoxLayout()
        self.playlist_limit_spin = QSpinBox()
        self.playlist_limit_spin.setRange(0, 100000)
        self.playlist_limit_spin.setSpecialValueText("No limit")
        self.playlist_limit_spin.setToolTip("Only download the first N items (ignored if Playlist items is set)")
        limit_row.addWidget(self.playlist_limit_spin)
        limit_row.addStretch()
        form.addRow("Limit to first N items:", limit_row)

        flags_row = QHBoxLayout()
        self.playlist_reverse_check = QCheckBox("Reverse order (oldest first)")
        flags_row.addWidget(self.playlist_reverse_check)
        form.addRow("Order:", flags_row)

        archive_row = QHBoxLayout()
        self.download_archive_check = QCheckBox("Skip items already downloaded before")
        self.download_archive_check.setToolTip(
            "Keeps a small record file in the destination folder so re-running "
            "the same playlist later only fetches new items."
        )
        archive_row.addWidget(self.download_archive_check)
        form.addRow("Resume-friendly:", archive_row)

        return page

    def _on_playlist_mode_changed(self):
        select_mode = self.playlist_mode_combo.currentText() == "Select items"
        self.playlist_items_edit.setEnabled(select_mode or self.playlist_mode_combo.currentText() != "Single video only")

    def _build_filters_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(8)

        hint = QLabel("Skip items that don't match these — handy for large or long-running playlists/channels.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8E8E93; font-size: 11px;")
        form.addRow(hint)

        self.date_after_edit = QLineEdit()
        self.date_after_edit.setPlaceholderText("YYYYMMDD — only items uploaded on/after")
        form.addRow("Uploaded after:", self.date_after_edit)

        self.date_before_edit = QLineEdit()
        self.date_before_edit.setPlaceholderText("YYYYMMDD — only items uploaded on/before")
        form.addRow("Uploaded before:", self.date_before_edit)

        self.min_filesize_edit = QLineEdit()
        self.min_filesize_edit.setPlaceholderText("e.g. 10M — skip smaller files")
        form.addRow("Min file size:", self.min_filesize_edit)

        self.max_filesize_edit = QLineEdit()
        self.max_filesize_edit.setPlaceholderText("e.g. 2G — skip larger files")
        form.addRow("Max file size:", self.max_filesize_edit)

        self.match_filter_edit = QLineEdit()
        self.match_filter_edit.setPlaceholderText('Raw yt-dlp filter, e.g. "duration > 60 & !is_live"')
        self.match_filter_edit.setToolTip(
            "Advanced: yt-dlp's --match-filter expression syntax. "
            "Left blank, nothing is filtered this way."
        )
        form.addRow("Custom match filter:", self.match_filter_edit)

        return page

    def _build_network_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(8)

        self.rate_limit_edit = QLineEdit()
        self.rate_limit_edit.setPlaceholderText("Unlimited (e.g. 2M, 500K)")
        form.addRow("Rate limit:", self.rate_limit_edit)

        self.proxy_edit = QLineEdit()
        self.proxy_edit.setPlaceholderText("e.g. socks5://127.0.0.1:1080")
        form.addRow("Proxy:", self.proxy_edit)

        self.cookies_combo = QComboBox()
        self.cookies_combo.addItems(["", "chrome", "firefox", "edge", "brave", "opera", "safari", "vivaldi"])
        self.cookies_combo.setToolTip("Use cookies from a locally installed, logged-in browser (for private/age-restricted content)")
        form.addRow("Cookies from browser:", self.cookies_combo)

        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(0, 50)
        self.retries_spin.setValue(10)
        form.addRow("Retries on failure:", self.retries_spin)

        self.concurrent_fragments_spin = QSpinBox()
        self.concurrent_fragments_spin.setRange(1, 16)
        self.concurrent_fragments_spin.setValue(1)
        self.concurrent_fragments_spin.setToolTip("Download multiple fragments of the same file in parallel — can speed up single large downloads")
        form.addRow("Concurrent fragments:", self.concurrent_fragments_spin)

        return page

    def _build_files_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(8)

        subs_row = QHBoxLayout()
        self.subs_check = QCheckBox("Download subtitles")
        self.subs_check.toggled.connect(lambda on: self.sub_langs_edit.setEnabled(on) or self.embed_subs_check.setEnabled(on))
        subs_row.addWidget(self.subs_check)
        self.embed_subs_check = QCheckBox("Embed")
        self.embed_subs_check.setEnabled(False)
        subs_row.addWidget(self.embed_subs_check)
        subs_row.addStretch()
        form.addRow("Subtitles:", subs_row)

        self.sub_langs_edit = QLineEdit("en")
        self.sub_langs_edit.setPlaceholderText("Comma-separated language codes, e.g. en,es")
        self.sub_langs_edit.setEnabled(False)
        form.addRow("Subtitle languages:", self.sub_langs_edit)

        meta_row = QHBoxLayout()
        self.embed_thumb_check = QCheckBox("Embed thumbnail")
        self.embed_meta_check = QCheckBox("Embed metadata")
        self.embed_meta_check.setChecked(True)
        self.embed_chapters_check = QCheckBox("Embed chapters")
        meta_row.addWidget(self.embed_thumb_check)
        meta_row.addWidget(self.embed_meta_check)
        meta_row.addWidget(self.embed_chapters_check)
        form.addRow("Embedding:", meta_row)

        extra_row = QHBoxLayout()
        self.sponsorblock_check = QCheckBox("Remove sponsor segments")
        self.sponsorblock_check.setToolTip("Uses SponsorBlock community data to cut sponsored segments (video only)")
        extra_row.addWidget(self.sponsorblock_check)
        form.addRow("SponsorBlock:", extra_row)

        self.custom_format_edit = QLineEdit()
        self.custom_format_edit.setPlaceholderText("Optional raw yt-dlp format string, overrides quality above")
        form.addRow("Custom format string:", self.custom_format_edit)

        extra_files_row = QHBoxLayout()
        self.write_thumb_check = QCheckBox("Save thumbnail file")
        self.write_infojson_check = QCheckBox("Save info .json")
        extra_files_row.addWidget(self.write_thumb_check)
        extra_files_row.addWidget(self.write_infojson_check)
        form.addRow("Extra files:", extra_files_row)

        return page

    def _build_history_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.history_table = QTableWidget(0, 4)
        self.history_table.setHorizontalHeaderLabels(["Title", "Status", "Destination", "When"])
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.verticalHeader().setVisible(False)
        layout.addWidget(self.history_table)

        row = QHBoxLayout()
        open_folder_btn = QPushButton("Open Containing Folder")
        open_folder_btn.clicked.connect(self._open_history_folder)
        row.addWidget(open_folder_btn)

        redownload_btn = QPushButton("Re-queue Selected")
        redownload_btn.clicked.connect(self._requeue_history)
        row.addWidget(redownload_btn)

        row.addStretch()
        clear_history_btn = QPushButton("Clear History")
        clear_history_btn.setObjectName("DangerButton")
        clear_history_btn.clicked.connect(self._clear_history)
        row.addWidget(clear_history_btn)

        layout.addLayout(row)
        self._refresh_history_table()
        return page

    def _build_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        add_action = QAction("Add URL…", self)
        add_action.setShortcut("Ctrl+N")
        add_action.triggered.connect(lambda: (self.url_input.setFocus(),))
        file_menu.addAction(add_action)

        import_action = QAction("Import URLs from Text File…", self)
        import_action.triggered.connect(self._import_urls_from_file)
        file_menu.addAction(import_action)

        export_action = QAction("Export History…", self)
        export_action.triggered.connect(self._export_history)
        file_menu.addAction(export_action)

        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        edit_menu = menubar.addMenu("&Edit")
        prefs_action = QAction("Preferences…", self)
        prefs_action.setShortcut("Ctrl+,")
        prefs_action.triggered.connect(self._open_preferences)
        edit_menu.addAction(prefs_action)

        view_menu = menubar.addMenu("&View")
        theme_action = QAction("Toggle Light / Dark Appearance", self)
        theme_action.triggered.connect(self._toggle_theme)
        view_menu.addAction(theme_action)

        log_action = QAction("Toggle Log Panel", self)
        log_action.triggered.connect(self._toggle_log)
        view_menu.addAction(log_action)

        help_menu = menubar.addMenu("&Help")
        ffmpeg_action = QAction("Check FFmpeg…", self)
        ffmpeg_action.triggered.connect(lambda: self._check_ffmpeg(startup=False))
        help_menu.addAction(ffmpeg_action)

        update_action = QAction("Check yt-dlp Version…", self)
        update_action.triggered.connect(self._check_ytdlp_version)
        help_menu.addAction(update_action)

        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        # Theme toggle lives in the menu bar's own corner, right next to
        # File/Edit/View/Help — no separate toolbar row needed.
        self.theme_toggle_action = QToolButton()
        self.theme_toggle_action.setText("🌙")
        self.theme_toggle_action.setAutoRaise(True)
        self.theme_toggle_action.setToolTip("Toggle light / dark appearance")
        self.theme_toggle_action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_toggle_action.clicked.connect(self._toggle_theme)
        menubar.setCornerWidget(self.theme_toggle_action, Qt.Corner.TopRightCorner)

    def _build_tray(self):
        style = self.style()
        icon = style.standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip(APP_DISPLAY_NAME)

        tray_menu = QMenu()
        show_action = QAction("Show Window", self)
        show_action.triggered.connect(self._restore_from_tray)
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._force_quit)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(
            lambda reason: self._restore_from_tray() if reason == QSystemTrayIcon.ActivationReason.Trigger else None
        )
        self.tray_icon.show()
        self._force_quit_flag = False

    def _restore_from_tray(self):
        self.showNormal()
        self.activateWindow()

    def _force_quit(self):
        self._force_quit_flag = True
        self.close()

    # -- theme -------------------------------------------------------
    def _apply_theme(self, theme: str):
        app = QApplication.instance()
        app.setStyleSheet(DARK_QSS if theme == "Dark" else LIGHT_QSS)
        self.theme_toggle_action.setText("☀️" if theme == "Dark" else "🌙")
        self.settings.setValue("theme", theme)

    def _toggle_theme(self):
        current = self.settings.value("theme", "Light")
        self._apply_theme("Dark" if current == "Light" else "Light")

    # -- drag & drop ---------------------------------------------------
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasText() or event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = []
        if event.mimeData().hasUrls():
            urls = [u.toString() for u in event.mimeData().urls()]
        elif event.mimeData().hasText():
            urls = [line.strip() for line in event.mimeData().text().splitlines() if line.strip()]
        for u in urls:
            if u.startswith(("http://", "https://")):
                self._enqueue_url(u)
        if urls:
            self.statusBar().showMessage(f"Added {len(urls)} URL(s) from drop", 4000)

    # -- option gathering ------------------------------------------------
    def _current_options(self) -> DownloadOptions:
        quality_label = self.quality_combo.currentText()
        quality_key = next((k for lbl, k in QUALITY_ITEMS if lbl == quality_label), "1080p")
        playlist_mode_map = {
            "Auto-detect": "auto",
            "Single video only": "single",
            "Entire playlist": "full",
            "Select items": "select",
        }
        return DownloadOptions(
            destination=self.folder_input.text().strip() or self.settings_folder_default(),
            quality_key=quality_key,
            media_type="audio" if self.audio_radio.isChecked() else "video",
            audio_format=self.audio_format_combo.currentText(),
            audio_bitrate=self.audio_bitrate_combo.currentText(),
            container=self.container_combo.currentText(),
            filename_template=self.filename_template_edit.text().strip() or "%(title)s.%(ext)s",
            download_subs=self.subs_check.isChecked(),
            sub_langs=self.sub_langs_edit.text().strip() or "en",
            embed_subs=self.embed_subs_check.isChecked(),
            embed_thumbnail=self.embed_thumb_check.isChecked(),
            embed_metadata=self.embed_meta_check.isChecked(),
            embed_chapters=self.embed_chapters_check.isChecked(),
            playlist_items=self.playlist_items_edit.text().strip(),
            playlist_mode=playlist_mode_map.get(self.playlist_mode_combo.currentText(), "auto"),
            playlist_reverse=self.playlist_reverse_check.isChecked(),
            playlist_end=self.playlist_limit_spin.value(),
            use_download_archive=self.download_archive_check.isChecked(),
            rate_limit=self.rate_limit_edit.text().strip(),
            proxy=self.proxy_edit.text().strip(),
            cookies_from_browser=self.cookies_combo.currentText(),
            retries=self.retries_spin.value(),
            concurrent_fragments=self.concurrent_fragments_spin.value(),
            custom_format=self.custom_format_edit.text().strip(),
            sponsorblock_remove=self.sponsorblock_check.isChecked(),
            write_thumbnail_file=self.write_thumb_check.isChecked(),
            write_info_json=self.write_infojson_check.isChecked(),
            date_after=self.date_after_edit.text().strip(),
            date_before=self.date_before_edit.text().strip(),
            match_filter=self.match_filter_edit.text().strip(),
            min_filesize=self.min_filesize_edit.text().strip(),
            max_filesize=self.max_filesize_edit.text().strip(),
        )

    def _validate_before_queue(self, url: str, opt: "DownloadOptions") -> Optional[str]:
        """Returns an error message if invalid, else None."""
        destination = opt.destination
        if not url:
            return "Please enter a URL."
        if not re.match(r"^https?://", url):
            return "That doesn't look like a valid URL (must start with http:// or https://)."
        if not destination:
            return "Please choose a destination folder."
        if not os.path.isdir(destination):
            try:
                os.makedirs(destination, exist_ok=True)
            except OSError as exc:
                return f"Destination folder doesn't exist and couldn't be created: {exc}"
        if not os.access(destination, os.W_OK):
            return "You don't have write permission for the destination folder."
        try:
            free_bytes = shutil.disk_usage(destination).free
            if free_bytes < 50 * 1024 * 1024:  # 50 MB safety floor
                return "Less than 50 MB free on the destination drive. Free up space first."
        except OSError:
            pass  # not fatal — some filesystems don't support disk_usage

        date_pattern = re.compile(r"^\d{8}$")
        if opt.date_after and not date_pattern.match(opt.date_after):
            return "Uploaded-after date must be in YYYYMMDD format (e.g. 20240101)."
        if opt.date_before and not date_pattern.match(opt.date_before):
            return "Uploaded-before date must be in YYYYMMDD format (e.g. 20241231)."

        size_pattern = re.compile(r"^\d+(\.\d+)?[KMGkmg]?$")
        if opt.min_filesize and not size_pattern.match(opt.min_filesize):
            return "Min file size looks wrong — try something like 10M or 500K."
        if opt.max_filesize and not size_pattern.match(opt.max_filesize):
            return "Max file size looks wrong — try something like 2G or 700M."

        if opt.match_filter.strip():
            try:
                yt_dlp.utils.match_filter_func(opt.match_filter.strip())
            except Exception:  # noqa: BLE001
                return "That custom match filter doesn't look like valid yt-dlp filter syntax."

        return None

    # -- queue actions -----------------------------------------------------
    def on_add_to_queue(self):
        raw = self.url_input.text().strip()
        if not raw:
            return
        urls = [line.strip() for line in raw.splitlines() if line.strip()]
        added = 0
        for u in urls:
            if self._enqueue_url(u):
                added += 1
        self.url_input.clear()
        if added:
            self.statusBar().showMessage(f"Added {added} item(s) to the queue", 4000)
            if self.settings.value("auto_start", "false") == "true":
                self.on_start_queue()

    def _enqueue_url(self, url: str) -> bool:
        opt = self._current_options()
        err = self._validate_before_queue(url, opt)
        if err:
            self._show_error("Can't add to queue", err)
            return False

        item = QueueItem(url=url, options=opt, title=url)
        self.queue_items[item.uid] = item
        self._add_queue_row(item)
        return True

    def _add_queue_row(self, item: QueueItem):
        row = self.queue_table.rowCount()
        self.queue_table.insertRow(row)
        item.row = row
        self.row_by_uid[item.uid] = row

        title_item = QTableWidgetItem(item.title)
        title_item.setData(Qt.ItemDataRole.UserRole, item.uid)
        self.queue_table.setItem(row, COLUMN_TITLE, title_item)
        status_item = QTableWidgetItem(item.status)
        self.queue_table.setItem(row, COLUMN_STATUS, status_item)

        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(0)
        progress.setTextVisible(False)
        self.queue_table.setCellWidget(row, COLUMN_PROGRESS, progress)

        self.queue_table.setItem(row, COLUMN_SPEED, QTableWidgetItem(""))
        self.queue_table.setItem(row, COLUMN_ETA, QTableWidgetItem(""))
        self.queue_table.setItem(row, COLUMN_SIZE, QTableWidgetItem(""))

    def _row_for_uid(self, uid: int) -> Optional[int]:
        return self.row_by_uid.get(uid)

    def on_start_queue(self):
        pending = [it for it in self.queue_items.values() if it.status in (STATUS_QUEUED, STATUS_ERROR, STATUS_CANCELLED)]
        if not pending:
            self.statusBar().showMessage("Nothing to start — add URLs to the queue first", 4000)
            return

        self.thread_pool.setMaxThreadCount(int(self.settings.value("max_concurrent", 2)))
        ffmpeg_path = self.settings.value("ffmpeg_path", "")

        for item in pending:
            item.status = STATUS_DOWNLOADING
            self._set_status_cell(item.uid, STATUS_DOWNLOADING)
            runnable = DownloadRunnable(item, ffmpeg_path=ffmpeg_path)
            runnable.signals.progress.connect(self._on_progress)
            runnable.signals.status.connect(self._on_status)
            runnable.signals.log.connect(self._on_log)
            runnable.signals.finished.connect(self._on_item_finished)
            runnable.signals.error.connect(self._on_item_error)
            self.runnables[item.uid] = runnable
            self.thread_pool.start(runnable)

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.statusBar().showMessage(f"Started {len(pending)} download(s)")

    def on_stop_all(self):
        for runnable in list(self.runnables.values()):
            runnable.cancel()
        self.statusBar().showMessage("Stopping all active downloads…")
        self.stop_btn.setEnabled(False)

    def on_remove_selected(self):
        rows = sorted({idx.row() for idx in self.queue_table.selectedIndexes()}, reverse=True)
        if not rows:
            return
        uids_to_remove = []
        for uid, row in self.row_by_uid.items():
            if row in rows:
                uids_to_remove.append(uid)
        for uid in uids_to_remove:
            item = self.queue_items.get(uid)
            if item and item.status == STATUS_DOWNLOADING:
                runnable = self.runnables.get(uid)
                if runnable:
                    runnable.cancel()
        for row in rows:
            self.queue_table.removeRow(row)
        for uid in uids_to_remove:
            self.queue_items.pop(uid, None)
            self.runnables.pop(uid, None)
        self._resync_row_indices()

    def on_clear_completed(self):
        done_states = (STATUS_COMPLETED, STATUS_CANCELLED, STATUS_ERROR)
        rows_to_remove = []
        uids_to_remove = []
        for uid, item in self.queue_items.items():
            if item.status in done_states:
                row = self.row_by_uid.get(uid)
                if row is not None:
                    rows_to_remove.append(row)
                    uids_to_remove.append(uid)
        for row in sorted(rows_to_remove, reverse=True):
            self.queue_table.removeRow(row)
        for uid in uids_to_remove:
            self.queue_items.pop(uid, None)
            self.runnables.pop(uid, None)
            self.row_by_uid.pop(uid, None)
        self._resync_row_indices()

    def _resync_row_indices(self):
        """After removing rows, QTableWidget compacts indices — rebuild our
        uid -> row map by re-reading each row's stored uid from item data."""
        self.row_by_uid = {}
        for row in range(self.queue_table.rowCount()):
            title_item = self.queue_table.item(row, COLUMN_TITLE)
            if title_item is None:
                continue
            uid = title_item.data(Qt.ItemDataRole.UserRole)
            if uid is not None:
                self.row_by_uid[uid] = row

    # -- signal handlers ---------------------------------------------------
    def _on_progress(self, uid, percent, speed, eta, size):
        row = self._row_for_uid(uid)
        if row is None:
            return
        widget = self.queue_table.cellWidget(row, COLUMN_PROGRESS)
        if isinstance(widget, QProgressBar):
            widget.setValue(int(max(0, min(100, percent))))
        self.queue_table.item(row, COLUMN_SPEED).setText(speed or "")
        self.queue_table.item(row, COLUMN_ETA).setText(eta or "")
        if size:
            self.queue_table.item(row, COLUMN_SIZE).setText(size)
        item = self.queue_items.get(uid)
        if item:
            item.percent = percent

    def _set_status_cell(self, uid, status_text):
        row = self._row_for_uid(uid)
        if row is None:
            return
        cell = self.queue_table.item(row, COLUMN_STATUS)
        if cell:
            cell.setText(status_text)
            color = STATUS_COLORS_LIGHT.get(status_text)
            if color:
                cell.setForeground(QColor(color))

    def _on_status(self, uid, status_text):
        item = self.queue_items.get(uid)
        if item:
            item.status = status_text
        self._set_status_cell(uid, status_text)
        self.statusBar().showMessage(f"{self._title_for(uid)}: {status_text}", 3000)
        self._maybe_reset_controls()

    def _on_log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.log_panel.appendPlainText(f"[{timestamp}] {message}")
        try:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {message}\n")
        except OSError:
            pass  # logging to disk is best-effort only

    def _title_for(self, uid) -> str:
        item = self.queue_items.get(uid)
        return item.title if item else "Item"

    def _on_item_finished(self, uid):
        item = self.queue_items.get(uid)
        if not item:
            return
        self.history.add(item.title, item.url, item.options.destination, STATUS_COMPLETED)
        self._refresh_history_table()

        if self.settings.value("notify_on_finish", "true") == "true":
            self.tray_icon.showMessage(
                APP_DISPLAY_NAME,
                f"Finished: {item.title}",
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )
        self.runnables.pop(uid, None)
        self._maybe_reset_controls()

    def _on_item_error(self, uid, short_message, suggestion):
        item = self.queue_items.get(uid)
        if item:
            item.error_message = short_message
            self.history.add(item.title, item.url, item.options.destination, f"Error: {short_message}")
            self._refresh_history_table()
        row = self._row_for_uid(uid)
        if row is not None:
            title_item = self.queue_table.item(row, COLUMN_TITLE)
            if title_item:
                title_item.setToolTip(f"{short_message}\n{suggestion}".strip())
        self.runnables.pop(uid, None)
        self._maybe_reset_controls()
        self.statusBar().showMessage(f"Error: {short_message}", 6000)

    def _maybe_reset_controls(self):
        active = any(it.status == STATUS_DOWNLOADING for it in self.queue_items.values())
        self.start_btn.setEnabled(not active)
        self.stop_btn.setEnabled(active)

    # -- fetch info only -----------------------------------------------
    def _fetch_info_only(self):
        url = self.url_input.text().strip().splitlines()[0].strip() if self.url_input.text().strip() else ""
        if not url:
            self._show_error("No URL", "Enter a URL first.")
            return
        if not re.match(r"^https?://", url):
            self._show_error("Invalid URL", "URL must start with http:// or https://")
            return

        temp_uid = int(time.time() * 1000)
        runnable = InfoFetchRunnable(
            temp_uid, url,
            cookies_from_browser=self.cookies_combo.currentText(),
            proxy=self.proxy_edit.text().strip(),
        )
        runnable.signals.title_fetched.connect(self._on_info_fetched)
        runnable.signals.error.connect(lambda _uid, short, sug: self._show_error("Couldn't fetch info", f"{short}\n\n{sug}"))
        self.statusBar().showMessage("Fetching info…")
        self.thread_pool.start(runnable)

    def _on_info_fetched(self, _uid, title, is_playlist, entry_count):
        if is_playlist:
            QMessageBox.information(
                self, "Playlist detected",
                f'"{title}" is a playlist with {entry_count} item(s).\n\n'
                f"Use 'Preview Playlist Items…' in the Playlist tab to pick exactly "
                f"which ones to queue, set 'Playlist mode' to Entire playlist to grab "
                f"all of them, or type a range like 1,3,5-8 into 'Playlist items'."
            )
        else:
            QMessageBox.information(self, "Video detected", f'Title: "{title}"')
        self.statusBar().showMessage("Info fetched", 3000)

    def _preview_playlist(self):
        url = self.url_input.text().strip().splitlines()[0].strip() if self.url_input.text().strip() else ""
        if not url:
            self._show_error("No URL", "Enter a playlist URL first.")
            return
        if not re.match(r"^https?://", url):
            self._show_error("Invalid URL", "URL must start with http:// or https://")
            return

        temp_uid = int(time.time() * 1000)
        runnable = InfoFetchRunnable(
            temp_uid, url,
            cookies_from_browser=self.cookies_combo.currentText(),
            proxy=self.proxy_edit.text().strip(),
            emit_entries=True,
        )
        runnable.signals.playlist_entries.connect(self._on_playlist_entries_fetched)
        runnable.signals.title_fetched.connect(self._on_preview_title_fetched)
        runnable.signals.error.connect(lambda _uid, short, sug: self._show_error("Couldn't fetch playlist", f"{short}\n\n{sug}"))
        self.preview_playlist_btn.setEnabled(False)
        self.statusBar().showMessage("Fetching playlist…")
        self.thread_pool.start(runnable)

    def _on_preview_title_fetched(self, _uid, title, is_playlist, entry_count):
        self.preview_playlist_btn.setEnabled(True)
        if not is_playlist:
            QMessageBox.information(
                self, "Not a playlist",
                f'"{title}" looks like a single video, not a playlist — nothing to preview.'
            )
            self.statusBar().showMessage("Ready", 2000)

    def _on_playlist_entries_fetched(self, _uid, playlist_title, entries):
        self.preview_playlist_btn.setEnabled(True)
        if not entries:
            self._show_error("Empty playlist", "No items were found in this playlist.")
            return

        dlg = PlaylistPreviewDialog(playlist_title, entries, self)
        if dlg.exec():
            items_string = dlg.selected_playlist_items_string()
            self.playlist_items_edit.setText(items_string)
            if items_string:
                self.playlist_mode_combo.setCurrentText("Select items")
                self.statusBar().showMessage(f"Selected items: {items_string}", 5000)
            else:
                self.playlist_mode_combo.setCurrentText("Entire playlist")
                self.statusBar().showMessage("All items selected", 3000)

    # -- misc UI actions -------------------------------------------------
    def _paste_url(self):
        text = QApplication.clipboard().text()
        if text:
            self.url_input.setText(text.strip())

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.folder_input.text())
        if folder:
            self.folder_input.setText(folder)

    def _toggle_log(self):
        visible = not self.log_panel.isVisible()
        self.log_panel.setVisible(visible)
        self.log_toggle_btn.setText("Hide Log ▴" if visible else "Show Log ▾")

    def _import_urls_from_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import URLs", "", "Text Files (*.txt);;All Files (*)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip().startswith(("http://", "https://"))]
        except OSError as exc:
            self._show_error("Couldn't read file", str(exc))
            return
        added = sum(1 for u in lines if self._enqueue_url(u))
        self.statusBar().showMessage(f"Imported {added} URL(s) from file", 4000)

    def _export_history(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export History", "history.json", "JSON Files (*.json)")
        if not path:
            return
        try:
            Path(path).write_text(json.dumps(self.history.all(), indent=2), encoding="utf-8")
            self.statusBar().showMessage("History exported", 4000)
        except OSError as exc:
            self._show_error("Export failed", str(exc))

    def _open_preferences(self):
        dlg = PreferencesDialog(self.settings, self)
        if dlg.exec():
            dlg.save()
            self._apply_theme(self.settings.value("theme", "Light"))
            self.thread_pool.setMaxThreadCount(int(self.settings.value("max_concurrent", 2)))
            self.folder_input.setText(self.settings.value("default_folder", self.folder_input.text()))
            self.statusBar().showMessage("Preferences saved", 3000)

    def _check_ffmpeg(self, startup: bool):
        ffmpeg_path = self.settings.value("ffmpeg_path", "") or "ffmpeg"
        try:
            subprocess.run([ffmpeg_path, "-version"], capture_output=True, check=True, timeout=5)
            if not startup:
                QMessageBox.information(self, "FFmpeg", "FFmpeg was found and is working correctly.")
            self._on_log("FFmpeg check: OK")
        except FileNotFoundError:
            self._on_log("FFmpeg check: not found on PATH")
            if not startup:
                self._show_error(
                    "FFmpeg not found",
                    "FFmpeg is required for merging video/audio and format conversion.\n\n"
                    "Install it and ensure it's on your PATH, or set a custom path in Preferences."
                )
            else:
                self.statusBar().showMessage("Warning: FFmpeg not found — some features will be limited", 8000)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            self._on_log(f"FFmpeg check failed: {exc}")
            if not startup:
                self._show_error("FFmpeg check failed", str(exc))

    def _check_ytdlp_version(self):
        try:
            version = yt_dlp.version.__version__
            QMessageBox.information(self, "yt-dlp Version", f"Currently using yt-dlp version {version}.\n\n"
                                                              f"To update: pip install -U yt-dlp")
        except Exception as exc:  # noqa: BLE001
            self._show_error("Couldn't determine yt-dlp version", str(exc))

    def _show_about(self):
        QMessageBox.about(
            self, f"About {APP_DISPLAY_NAME}",
            f"<b>{APP_DISPLAY_NAME}</b> v{APP_VERSION}<br><br>"
            "A queue-based media downloader built on yt-dlp and PyQt6, "
            "styled after macOS.<br><br>"
            "Supports YouTube and 1800+ other sites via yt-dlp."
        )

    def _show_error(self, title: str, message: str):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(title)
        box.setText(message)
        box.exec()

    # -- history tab actions ----------------------------------------------
    def _refresh_history_table(self):
        entries = self.history.all()
        self.history_table.setRowCount(0)
        for entry in entries:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)
            title_item = QTableWidgetItem(entry.get("title", ""))
            title_item.setData(Qt.ItemDataRole.UserRole, entry)
            self.history_table.setItem(row, 0, title_item)
            self.history_table.setItem(row, 1, QTableWidgetItem(entry.get("status", "")))
            self.history_table.setItem(row, 2, QTableWidgetItem(entry.get("destination", "")))
            self.history_table.setItem(row, 3, QTableWidgetItem(entry.get("timestamp", "")))

    def _open_history_folder(self):
        rows = self.history_table.selectedIndexes()
        if not rows:
            return
        entry = self.history_table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        destination = entry.get("destination", "")
        if not destination or not os.path.isdir(destination):
            self._show_error("Folder not found", "That destination folder no longer exists.")
            return
        self._open_in_file_manager(destination)

    @staticmethod
    def _open_in_file_manager(path: str):
        try:
            system = sys.platform
            if system == "darwin":
                subprocess.run(["open", path], check=False)
            elif system.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                subprocess.run(["xdg-open", path], check=False)
        except Exception:
            pass  # opening a file browser is a convenience action; failures are non-fatal

    def _requeue_history(self):
        rows = self.history_table.selectedIndexes()
        if not rows:
            return
        seen_rows = {idx.row() for idx in rows}
        added = 0
        for row in seen_rows:
            entry = self.history_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            url = entry.get("url", "")
            if url and self._enqueue_url(url):
                added += 1
        if added:
            self.statusBar().showMessage(f"Re-queued {added} item(s)", 4000)
            self.tabs.setCurrentIndex(0)

    def _clear_history(self):
        reply = QMessageBox.question(
            self, "Clear History", "Remove all download history? This can't be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.history.clear()
            self._refresh_history_table()

    # -- window close behavior --------------------------------------------
    def closeEvent(self, event):
        active = any(it.status == STATUS_DOWNLOADING for it in self.queue_items.values())
        minimize_to_tray = self.settings.value("minimize_to_tray", "true") == "true"

        if minimize_to_tray and not getattr(self, "_force_quit_flag", False):
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(APP_DISPLAY_NAME, "Still running in the background.",
                                        QSystemTrayIcon.MessageIcon.Information, 3000)
            return

        if active:
            reply = QMessageBox.question(
                self, "Downloads in progress",
                "Downloads are still running. Stop them and quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            for runnable in list(self.runnables.values()):
                runnable.cancel()
            self.thread_pool.waitForDone(3000)

        event.accept()


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------

def _install_global_exception_hook():
    """Catch anything that slips past local try/except blocks so the app
    shows a dialog instead of dying silently to the terminal."""
    def handle(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n[UNCAUGHT] {datetime.now().isoformat()}\n{details}\n")
        except OSError:
            pass
        try:
            box = QMessageBox()
            box.setIcon(QMessageBox.Icon.Critical)
            box.setWindowTitle("Unexpected Error")
            box.setText("Something went wrong and the app needs to recover from it.")
            box.setDetailedText(details)
            box.exec()
        except Exception:
            print(details, file=sys.stderr)

    sys.excepthook = handle


def main():
    _install_global_exception_hook()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_DISPLAY_NAME)
    app.setOrganizationName(APP_ORG)
    app.setQuitOnLastWindowClosed(False)  # keep running while minimized to tray

    if not QSystemTrayIcon.isSystemTrayAvailable():
        # Not fatal — just means "minimize to tray" won't have visible effect.
        pass

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
