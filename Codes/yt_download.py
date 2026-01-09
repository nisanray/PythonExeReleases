import sys
import threading
import shutil
import os
import yt_dlp

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit,
    QPushButton, QComboBox, QProgressBar, QVBoxLayout,
    QHBoxLayout, QMessageBox, QFileDialog, QTextEdit, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QSettings

# ---------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------
STYLESHEET = """
    QWidget {
        background-color: #2b2b2b;
        color: #ffffff;
        font-family: 'Segoe UI', sans-serif;
        font-size: 14px;
    }
    QLineEdit, QComboBox, QTextEdit {
        background-color: #3a3a3a;
        border: 1px solid #555;
        border-radius: 4px;
        padding: 5px;
        color: #fff;
    }
    QLineEdit:focus, QComboBox:focus {
        border: 1px solid #0078d7;
    }
    QProgressBar {
        border: 1px solid #555;
        border-radius: 4px;
        text-align: center;
        background-color: #3a3a3a;
    }
    QProgressBar::chunk {
        background-color: #0078d7;
        width: 10px;
    }
    QPushButton {
        background-color: #0078d7;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 8px 15px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #0093ff;
    }
    QPushButton:pressed {
        background-color: #005a9e;
        padding-top: 9px;
        padding-bottom: 7px;
    }
    QPushButton:disabled {
        background-color: #555;
        color: #aaa;
    }
    QLabel#Header {
        font-size: 16px;
        font-weight: bold;
        color: #ccc;
    }
"""

# ---------------------------------------------------------
# Custom Logger
# ---------------------------------------------------------
class YtdlpLogger:
    def __init__(self, callback):
        self.callback = callback

    def debug(self, msg):
        if not msg.startswith('[debug] '):
            self.callback(f"[INFO] {msg}")

    def warning(self, msg):
        self.callback(f"[WARNING] {msg}")

    def error(self, msg):
        self.callback(f"[ERROR] {msg}")

# ---------------------------------------------------------
# Main Application Class
# ---------------------------------------------------------
class YouTubeDownloader(QWidget):
    progress_signal = pyqtSignal(int)
    log_signal = pyqtSignal(str)
    enable_controls_signal = pyqtSignal(bool)
    finished_signal = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.setWindowTitle("YT Video Downloader Pro")
        self.resize(600, 500)
        self.setStyleSheet(STYLESHEET)
        
        # Settings to remember locations
        self.settings = QSettings("MySoft", "YTDownloader")

        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # --- Section 1: URL & Quality (Compact) ---
        top_layout = QVBoxLayout()
        top_layout.setSpacing(5)
        
        # URL Input
        self.url_label = QLabel("🔗 YouTube URL:")
        self.url_label.setObjectName("Header")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste YouTube link here...")
        top_layout.addWidget(self.url_label)
        top_layout.addWidget(self.url_input)
        
        # Quality on same row
        quality_layout = QHBoxLayout()
        self.quality_label = QLabel("Quality:")
        self.quality_label.setObjectName("Header")
        self.quality_box = QComboBox()
        self.quality_box.addItems([
            "Best Available",
            "1080p", "720p", "480p", "360p",
            "Audio Only (MP3)", "Audio Only (M4A)",
            "Video Only (1080p)", "Video Only (720p)"
        ])
        quality_layout.addWidget(self.quality_label, 0)
        quality_layout.addWidget(self.quality_box, 1)
        top_layout.addLayout(quality_layout)
        
        main_layout.addLayout(top_layout)

        # --- Section 2: Settings (Collapsible) ---
        settings_box = QGroupBox("⚙️ Settings")
        settings_layout = QVBoxLayout(settings_box)
        settings_layout.setSpacing(5)
        
        # Save Location
        folder_layout = QHBoxLayout()
        self.folder_input = QLineEdit()
        last_save_path = self.settings.value("download_path", "")
        if last_save_path and os.path.exists(last_save_path):
            self.folder_input.setText(last_save_path)
        else:
            default_save = os.path.join(os.path.expanduser("~"), "Downloads")
            self.folder_input.setText(default_save)
        self.folder_input.setReadOnly(True)
        self.browse_save_btn = QPushButton("📂 Browse")
        self.browse_save_btn.setFixedWidth(90)
        self.browse_save_btn.clicked.connect(self.browse_save_folder)
        folder_layout.addWidget(QLabel("Save To:"), 0)
        folder_layout.addWidget(self.folder_input, 1)
        folder_layout.addWidget(self.browse_save_btn, 0)
        settings_layout.addLayout(folder_layout)
        
        # FFmpeg Path
        ffmpeg_layout = QHBoxLayout()
        self.ffmpeg_input = QLineEdit()
        last_ffmpeg = self.settings.value("ffmpeg_path", r"C:\ffmpeg\bin")
        self.ffmpeg_input.setText(last_ffmpeg)
        self.ffmpeg_input.setPlaceholderText(r"C:\ffmpeg\bin")
        self.browse_ffmpeg_btn = QPushButton("⚙️ Browse")
        self.browse_ffmpeg_btn.setFixedWidth(90)
        self.browse_ffmpeg_btn.clicked.connect(self.browse_ffmpeg_folder)
        ffmpeg_layout.addWidget(QLabel("FFmpeg:"), 0)
        ffmpeg_layout.addWidget(self.ffmpeg_input, 1)
        ffmpeg_layout.addWidget(self.browse_ffmpeg_btn, 0)
        settings_layout.addLayout(ffmpeg_layout)
        
        main_layout.addWidget(settings_box)

        # --- Section 3: Actions & Progress ---
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)
        self.fetch_btn = QPushButton("📊 Check Info")
        self.download_btn = QPushButton("⬇️ Download")
        self.download_btn.setEnabled(False)
        action_layout.addWidget(self.fetch_btn)
        action_layout.addWidget(self.download_btn)
        main_layout.addLayout(action_layout)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFixedHeight(20)
        main_layout.addWidget(self.progress)

        # --- Section 4: Compact Logs ---
        log_layout = QHBoxLayout()
        log_label = QLabel("📝 Logs:")
        log_label.setObjectName("Header")
        self.clear_log_btn = QPushButton("Clear")
        self.clear_log_btn.setFixedWidth(60)
        self.clear_log_btn.clicked.connect(self.log_window_clear)
        log_layout.addWidget(log_label)
        log_layout.addStretch()
        log_layout.addWidget(self.clear_log_btn)
        main_layout.addLayout(log_layout)

        self.log_window = QTextEdit()
        self.log_window.setReadOnly(True)
        self.log_window.setFixedHeight(120)
        main_layout.addWidget(self.log_window)

        main_layout.addStretch()

        # --- Connections ---
        self.fetch_btn.clicked.connect(self.fetch_info)
        self.download_btn.clicked.connect(self.start_download)
        self.progress_signal.connect(self.update_progress)
        self.log_signal.connect(self.append_log)
        self.enable_controls_signal.connect(self.set_controls_enabled)
        self.finished_signal.connect(self.on_download_complete)
        
        # Validate FFmpeg on startup
        self.validate_ffmpeg_path()

    # ---------------- UI Logic ----------------

    def browse_save_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.folder_input.text())
        if folder:
            self.folder_input.setText(folder)
            self.settings.setValue("download_path", folder)
            self.append_log(f"[UI] Save location set to: {folder}")

    def browse_ffmpeg_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select FFmpeg 'bin' Folder", self.ffmpeg_input.text())
        if folder:
            self.ffmpeg_input.setText(folder)
            self.settings.setValue("ffmpeg_path", folder)
            self.validate_ffmpeg_path()

    def validate_ffmpeg_path(self):
        path = self.ffmpeg_input.text().strip()
        exe_path = os.path.join(path, "ffmpeg.exe")
        
        if os.path.exists(exe_path):
            self.append_log(f"[INIT] FFmpeg found at: {exe_path}")
            self.ffmpeg_input.setStyleSheet("border: 1px solid #00ff00;") # Green border
            return True
        else:
            self.append_log(f"[WARNING] ffmpeg.exe NOT found in: {path}")
            self.ffmpeg_input.setStyleSheet("border: 1px solid #ff0000;") # Red border
            return False

    @pyqtSlot(int)
    def update_progress(self, val):
        self.progress.setValue(val)

    @pyqtSlot(str)
    def append_log(self, text):
        self.log_window.append(text)
        scrollbar = self.log_window.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def log_window_clear(self):
        self.log_window.clear()

    @pyqtSlot(bool)
    def set_controls_enabled(self, enabled):
        self.fetch_btn.setEnabled(enabled)
        self.download_btn.setEnabled(enabled)
        self.browse_save_btn.setEnabled(enabled)
        self.browse_ffmpeg_btn.setEnabled(enabled)
        self.url_input.setEnabled(enabled)
        self.ffmpeg_input.setEnabled(enabled)
        
    @pyqtSlot()
    def on_download_complete(self):
        self.progress.setValue(100)
        self.append_log("[SUCCESS] Process Finished.")
        QMessageBox.information(self, "Done", "Download Completed Successfully!")
        self.set_controls_enabled(True)

    # ---------------- Threading Logic ----------------

    def get_opts(self, out_tmpl=None):
        opts = {
            "quiet": False,
            "noplaylist": True,
            "js_runtimes": {"node": {}},
            "remote_components": ["ejs:github", "ejs:npm"],
            "logger": YtdlpLogger(self.log_signal.emit),
            "socket_timeout": 30,
        }
        
        # Use the path from the Input Box
        ffmpeg_dir = self.ffmpeg_input.text().strip()
        if os.path.exists(os.path.join(ffmpeg_dir, "ffmpeg.exe")):
            opts["ffmpeg_location"] = ffmpeg_dir
        
        if out_tmpl:
            opts["outtmpl"] = out_tmpl
            
        return opts

    def fetch_info(self):
        url = self.url_input.text().strip()
        if not url:
            self.append_log("[ERROR] Please enter a YouTube URL.")
            return
        
        if "youtube.com" not in url and "youtu.be" not in url:
            self.append_log("[ERROR] Invalid YouTube URL. Please enter a valid YouTube link.")
            return
        
        self.set_controls_enabled(False)
        self.log_signal.emit(f"[UI] Fetching info for: {url}...")
        threading.Thread(target=self._fetch_info_thread, args=(url,), daemon=True).start()

    def _fetch_info_thread(self, url):
        try:
            ydl_opts = self.get_opts()
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get('title', 'Unknown')
                self.log_signal.emit(f"[INFO] Title: {title}")

                # --- Size Calculation ---
                quality = self.quality_box.currentText()
                formats = info.get('formats', [])
                
                estimated_size = 0
                found_est = False

                if "Audio Only" in quality:
                    best_audio = next((f for f in reversed(formats) 
                                     if f.get('acodec') != 'none' and f.get('vcodec') == 'none'), None)
                    if best_audio:
                        estimated_size = best_audio.get('filesize') or best_audio.get('filesize_approx') or 0
                        found_est = True

                elif quality == "Best Available":
                    best_video = next((f for f in reversed(formats) if f.get('vcodec') != 'none'), None)
                    best_audio = next((f for f in reversed(formats) if f.get('acodec') != 'none' and f.get('vcodec') == 'none'), None)
                    v_size = best_video.get('filesize') or best_video.get('filesize_approx') or 0 if best_video else 0
                    a_size = best_audio.get('filesize') or best_audio.get('filesize_approx') or 0 if best_audio else 0
                    estimated_size = v_size + a_size
                    if estimated_size > 0: found_est = True

                elif "Video Only" in quality:
                    target_height = 1080 if "1080" in quality else 720
                    vid_format = next((f for f in formats if f.get('height') == target_height and f.get('vcodec') != 'none'), None)
                    if vid_format:
                        estimated_size = vid_format.get('filesize') or vid_format.get('filesize_approx') or 0
                        if estimated_size > 0: found_est = True
                    else:
                        self.log_signal.emit(f"[INFO] {target_height}p video-only format not found.")

                else:
                    heights = {"1080p": 1080, "720p": 720, "480p": 480, "360p": 360}
                    target_height = heights.get(quality, 720)
                    vid_format = next((f for f in formats if f.get('height') == target_height and f.get('vcodec') != 'none'), None)
                    aud_format = next((f for f in reversed(formats) if f.get('acodec') != 'none' and f.get('vcodec') == 'none'), None)

                    if vid_format:
                        v_size = vid_format.get('filesize') or vid_format.get('filesize_approx') or 0
                        a_size = 0
                        if vid_format.get('acodec') == 'none' and aud_format:
                            a_size = aud_format.get('filesize') or aud_format.get('filesize_approx') or 0
                        estimated_size = v_size + a_size
                        if estimated_size > 0: found_est = True
                    else:
                        self.log_signal.emit(f"[INFO] {target_height}p format not found available.")

                if found_est and estimated_size > 0:
                    size_mb = estimated_size / (1024 * 1024)
                    self.log_signal.emit(f"[INFO] Estimated Download Size: ~{size_mb:.2f} MB")
                elif not found_est:
                    self.log_signal.emit("[INFO] Could not calculate exact size (Stream data missing).")

        except Exception as e:
            self.log_signal.emit(f"[ERROR] Fetch failed: {str(e)}")
        finally:
            self.enable_controls_signal.emit(True)

    def start_download(self):
        url = self.url_input.text().strip()
        save_path = self.folder_input.text()
        ffmpeg_path = self.ffmpeg_input.text()
        
        # Save preferences
        self.settings.setValue("download_path", save_path)
        self.settings.setValue("ffmpeg_path", ffmpeg_path)

        if not os.path.exists(save_path):
            self.append_log("[ERROR] Invalid download folder.")
            return

        if not self.validate_ffmpeg_path():
             self.append_log("[ERROR] Invalid FFmpeg folder. Cannot proceed.")
             return

        self.set_controls_enabled(False)
        self.progress.setValue(0)
        self.append_log(f"[UI] Downloading to: {save_path}")

        threading.Thread(target=self._download_thread, args=(url, save_path), daemon=True).start()

    def _download_thread(self, url, save_path):
        try:
            quality = self.quality_box.currentText()
            # Append quality tag to filename for easier identification
            quality_tag = self._map_quality_tag(quality)
            out_tmpl = os.path.join(save_path, f"%(title)s [{quality_tag}].%(ext)s")
            
            if quality == "Audio Only (MP3)":
                format_str = "bestaudio/best"
                postprocessors = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
            elif quality == "Audio Only (M4A)":
                format_str = "bestaudio[ext=m4a]/best[ext=m4a]/bestaudio/best"
                postprocessors = []
            elif quality == "Video Only (1080p)":
                format_str = "bestvideo[height=1080]+bestaudio/best[height=1080]/bestvideo+bestaudio/best"
                postprocessors = []
            elif quality == "Video Only (720p)":
                format_str = "bestvideo[height=720]+bestaudio/best[height=720]/bestvideo+bestaudio/best"
                postprocessors = []
            elif quality == "Best Available":
                format_str = "bestvideo+bestaudio/best"
                postprocessors = []
            elif quality == "1080p":
                format_str = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
                postprocessors = []
            elif quality == "720p":
                format_str = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
                postprocessors = []
            elif quality == "480p":
                format_str = "bestvideo[height<=480]+bestaudio/best[height<=480]/best"
                postprocessors = []
            else:  # 360p
                format_str = "bestvideo[height<=360]+bestaudio/best[height<=360]/best"
                postprocessors = []

            ydl_opts = self.get_opts(out_tmpl)
            ydl_opts.update({
                "format": format_str,
                "postprocessors": postprocessors,
                "progress_hooks": [self.progress_hook]
            })

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            self.finished_signal.emit()

        except Exception as e:
            self.log_signal.emit(f"[ERROR] Download failed: {str(e)}")
            self.enable_controls_signal.emit(True)

    def _map_quality_tag(self, quality: str) -> str:
        q = quality.lower()
        if "audio only" in q:
            if "mp3" in q:
                return "mp3"
            if "m4a" in q:
                return "m4a"
            return "audio"
        if "video only" in q:
            if "1080" in q:
                return "1080p-video"
            if "720" in q:
                return "720p-video"
            return "video"
        if "best" in q:
            return "best"
        if "1080" in q:
            return "1080p"
        if "720" in q:
            return "720p"
        if "480" in q:
            return "480p"
        if "360" in q:
            return "360p"
        return quality.replace(" ", "")

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            try:
                p = d.get('_percent_str', '0%').replace('%','')
                import re
                ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                p = ansi_escape.sub('', p)
                self.progress_signal.emit(int(float(p)))
            except:
                pass
        elif d['status'] == 'finished':
            self.log_signal.emit("[INFO] Segment download complete. Merging/Converting...")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YouTubeDownloader()
    window.show()
    sys.exit(app.exec())