# Python to EXE Release Repository

This repository contains Python applications that are automatically converted to Windows executables using GitHub Actions. The CI/CD pipeline automatically detects all third-party libraries from the source code, builds standalone EXEs, and creates a new GitHub release — no manual dependency management needed.

## Applications

### 🖥️ Internet Speed Meter
A floating, draggable overlay that displays real-time internet upload and download speeds on Windows.

**Features:**
- Minimal, always-on-top overlay window
- Real-time download and upload speed display
- Draggable and closable interface
- Uses PyQt6 for GUI and psutil for network statistics

### 🔒 Lock Scheduler GUI
A Windows desktop application that provides automated system lock functionality with multiple scheduling options and mouse-triggered locking capabilities.

**Features:**
- **Specific Time Lock**: Schedule system lock at a specific time
- **Duration-based Lock**: Lock system after a specified duration (hours, minutes, seconds)
- **Quick Lock**: Pre-configured quick lock options (1 min, 5 min, 15 min, 30 min, 1 hour)
- **Immediate Lock**: Lock system immediately with confirmation
- **Mouse Movement Lock**: Lock system when mouse movement is detected after an activation delay
- Modern tabbed interface built with PyQt6
- Real-time current time display and professional Windows 11-inspired design

### 📂 LAN Share (File Upload Server)
A cross-platform local file sharing server with a modern web interface and a PyQt6 GUI for easy control. Allows uploading files from any device on the same network to your computer via a browser.

**Features:**
- Drag-and-drop or select files to upload from any device on the LAN
- Modern, responsive web interface for uploads
- PyQt6 desktop GUI to start/stop the server, set upload folder, and view logs
- Customizable upload folder location
- Displays LAN IP and server URL for easy access
- All files saved with unique names to prevent overwrites
- Works on Windows, macOS, and Linux

### 💬 LAN Chat & File Share
A comprehensive LAN messenger and file sharing tool. It combines a Flask-based web server for browser-based chatting/file sharing with a PyQt6 desktop admin interface.

**Features:**
- **Local Chat**: Browser-based chat accessible from any device on the network
- **File Sharing**: Easy file upload and download via the web interface
- **Admin GUI**: Desktop application to monitor logs, broadcast admin messages, and manage the server
- **Mobile Connect**: Generates a QR code for easy mobile connection
- **Video/Image Preview**: In-chat previews for shared media

### 🎬 YouTube Video Downloader
A desktop tool to download YouTube videos or audio with quick presets and progress tracking.

**Features:**
- Choose best available, specific resolutions, or audio-only (MP3/M4A)
- Automatic FFmpeg path validation with saved preferences
- Estimated size display plus live download progress bar
- Selectable download directory with recent path recall and logging

### 🤖 Facebook Unsave Automation Bot
An advanced image-based automation bot with a PyQt6 GUI. Uses screen image recognition to automate repetitive two-step click workflows (e.g., unsaving Facebook posts).

**Features:**
- Two-target image recognition with configurable actions (click, right-click, double-click, hover)
- Per-target X/Y offset controls for precise coordinate tuning
- Configurable timing: initial delay, inter-step delay, cycle delay, and search timeout
- Adjustable match confidence for image recognition accuracy
- **Humanize Mode**: Randomizes delays by ±20% to mimic natural behavior
- Max cycle limiter and per-image search timeout
- **F9 hotkey** for emergency stop plus PyAutoGUI fail-safe (move mouse to corner)
- Full execution logging with real-time console output

### ⚡ PowerFlow Advanced System Manager
A comprehensive Windows system utility that combines performance monitoring, security traps, and automated power management into one powerful interface.

**Features:**
- **Smart Scheduling**: Timer-based and'exact time' shutdown/restart/lock tasks.
- **Security Traps**: Armed Jiggler (decoy movement detector), Intrusion Trap (input detector), and Ransomware Honeypot (file change detector).
- **Physical & Network Safety**: VPN/Wi-Fi connection shields and USB Kill Switch.
- **Productivity Tools**: App Quota (usage limits), Focus Mode (instantly kills forbidden apps), and Mouse Jiggler (stay-awake).
- **Resource Protection**: CPU/Thermal sustained load monitor and Battery Savior for laptops.
- **Stealth Mode**: Screen Shield (transparent lock) and Fake Windows Update decoy screens.

## Repository Structure

```
PythonExeReleases/
├── .github/
│   └── workflows/
│       └── build_and_release.yml    # GitHub Actions workflow (auto-detect deps & build)
├── Codes/
│   ├── Internet_Speed_Meter.py      # Internet Speed Meter overlay
│   ├── lan_chat_file_share.py       # LAN Chat & File Share
│   ├── lan_share.py                 # LAN Share (file upload server)
│   ├── lock_scheduler_gui.py        # Lock Scheduler application
│   ├── powerflow_advanced_system_manager.py # PowerFlow System Manager
│   ├── unsave_facebook.py           # Facebook Unsave Automation Bot
│   └── yt_download.py               # YouTube Video Downloader
├── Readme.md                        # This file
└── .gitignore                       # Git ignore patterns
```

## Automated Build Process

This repository uses GitHub Actions to automatically:

1. **Detect Dependencies**: Scans all Python files in `Codes/` using AST parsing to extract third-party imports — no `requirements.txt` needed
2. **Install Packages**: Maps import names to PyPI packages and installs them automatically
3. **Build Executables**: Converts each Python script to a standalone Windows EXE using PyInstaller
4. **Create Release**: Creates a GitHub release with version tag and uploads all EXE files

### Workflow Triggers
- Builds are triggered only when files in `Codes/` are pushed to the `master` branch
- Each build creates a new release with incrementing version numbers
- Executables are built on Windows environment using Python 3.11

## Download Latest EXEs

Visit the [Releases](../../releases/latest) page to download the latest built executables.

### Quick Links
- **📥 [Download Latest Release](../../releases/latest)** - Get the newest EXE files
- **📋 [All Releases](../../releases)** - View complete release history
- **🔧 [GitHub Actions](../../actions)** - Monitor build status
- **📖 [Repository](../../)** - View source code
- **🐛 [Issues](../../issues)** - Report bugs or request features

### Direct Download Links (Latest Release)
- [Internet_Speed_Meter.exe](../../releases/latest/download/Internet_Speed_Meter.exe) - Internet Speed Meter Overlay
- [lock_scheduler_gui.exe](../../releases/latest/download/lock_scheduler_gui.exe) - Lock Scheduler Application
- [lan_share.exe](../../releases/latest/download/lan_share.exe) - LAN Share (File Upload Server)
- [lan_chat_file_share.exe](../../releases/latest/download/lan_chat_file_share.exe) - LAN Chat & File Share
- [yt_download.exe](../../releases/latest/download/yt_download.exe) - YouTube Video Downloader
- [unsave_facebook.exe](../../releases/latest/download/unsave_facebook.exe) - Facebook Unsave Automation Bot
- [powerflow_advanced_system_manager.exe](../../releases/latest/download/powerflow_advanced_system_manager.exe) - PowerFlow System Manager

> **Note**: Links will be active after pushing to GitHub. The automated workflow will build and upload EXE files to releases.

## Getting Started

### For Users (Download & Run)
1. Visit the [Releases page](../../releases/latest)
2. Download the desired `.exe` file
3. Run the executable (no installation required)

### For Developers (Run from Source)
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd PythonExeReleases
   ```

2. Install dependencies (pick what you need):
   ```bash
   pip install PyQt6 psutil flask werkzeug qrcode Pillow yt-dlp pyautogui pynput
   ```

3. Run any application:
   ```bash
   python Codes/Internet_Speed_Meter.py
   python Codes/lock_scheduler_gui.py
   python Codes/lan_share.py
   python Codes/lan_chat_file_share.py
   python Codes/yt_download.py
   python Codes/unsave_facebook.py
   python Codes/powerflow_advanced_system_manager.py
   ```

## Manual Build

To manually build executables:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed Codes/Internet_Speed_Meter.py
pyinstaller --onefile --windowed Codes/lock_scheduler_gui.py
pyinstaller --onefile --windowed Codes/lan_share.py
pyinstaller --onefile --windowed Codes/lan_chat_file_share.py
pyinstaller --onefile --windowed Codes/yt_download.py
pyinstaller --onefile --windowed Codes/unsave_facebook.py
pyinstaller --onefile --windowed Codes/powerflow_advanced_system_manager.py
```

## System Requirements

- **For Development**: Python 3.7+ and dependencies
- **For Executables**: Windows operating system only
- **For Lock Scheduler**: Administrator privileges may be required for system locking functionality
- **For Unsave Bot**: Requires screen image files for target recognition

## CI/CD Pipeline Features

- **Zero-Config Dependencies**: Automatically detects imports from source code via AST parsing
- **Smart Package Mapping**: Handles import-to-PyPI name differences (e.g., `PIL` → `Pillow`)
- **Cross-platform Building**: Uses GitHub-hosted Windows runners
- **Automated Versioning**: Incremental release numbering
- **Asset Management**: Automatic upload of built executables
- **Change-based Triggers**: Only rebuilds when code in `Codes/` changes

## Contributing

1. Add your Python script to the `Codes/` directory
2. Push to `master` — dependencies are detected automatically, no manual config needed
3. GitHub Actions will build the EXE and create a release

## Security Notice

The Lock Scheduler application uses Windows system APIs to lock the workstation. The Unsave Bot uses screen automation (PyAutoGUI) — use responsibly and ensure you have proper permissions.

## License

This project is provided as-is for educational and personal use purposes.