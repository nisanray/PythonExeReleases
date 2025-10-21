# Python to EXE Release Repository

This repository contains Python applications that are automatically converted to Windows executables using GitHub Actions. The repository features automated CI/CD pipeline that builds and releases executable files for easy distribution.

## Applications


### Lock Scheduler GUI
A Windows desktop application that provides automated system lock functionality with multiple scheduling options and mouse-triggered locking capabilities.

**Features:**
- **Specific Time Lock**: Schedule system lock at a specific time
- **Duration-based Lock**: Lock system after a specified duration (hours, minutes, seconds)
- **Quick Lock**: Pre-configured quick lock options (1 min, 5 min, 15 min, 30 min, 1 hour)
- **Immediate Lock**: Lock system immediately with confirmation
- **Mouse Movement Lock**: Lock system when mouse movement is detected after an activation delay
- Modern tabbed interface built with PyQt6
- Real-time current time display and professional Windows 11-inspired design

### Internet Speed Meter
A floating, draggable overlay that displays real-time internet upload and download speeds on Windows.

**Features:**
- Minimal, always-on-top overlay window
- Real-time download and upload speed display
- Draggable and closable interface
- Uses PyQt6 for GUI and psutil for network statistics

## Repository Structure

```
PythonToEXERelease/
├── .github/
│   └── workflows/
│       └── build_and_release.yml    # GitHub Actions workflow for automated builds
├── Codes/
│   └── lock_scheduler_gui.py        # Lock Scheduler application source code
├── Internet_Speed_Meter.py          # Internet Speed Meter overlay source code
├── requirements.txt                 # Python dependencies
├── README.md                       # This file
└── .gitignore                      # Git ignore patterns
```

## Automated Build Process

This repository uses GitHub Actions to automatically:

1. **Build Process**: Converts Python scripts to Windows executables using PyInstaller
2. **Release Creation**: Creates GitHub releases with version tags
3. **Asset Upload**: Uploads built EXE files to releases for easy download
4. **Documentation**: Updates README with download links

### Workflow Triggers
- Builds are triggered on pushes to the `main` branch
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
- [lock_scheduler_gui.exe](../../releases/latest/download/lock_scheduler_gui.exe) - Lock Scheduler Application

> **Note**: Links will be active after pushing to GitHub. The automated workflow will build and upload EXE files to releases.

## Dependencies

- **PyQt6**: Modern GUI framework for desktop applications
- **pyinstaller**: Tool for converting Python applications to executables
- **psutil**: Cross-platform library for retrieving information on running processes and system utilization (used by Internet Speed Meter)

## Getting Started

### For Users (Download & Run)
1. Visit the [Releases page](../../releases/latest)
2. Download the latest `lock_scheduler_gui.exe`
3. Run the executable (no installation required)

### For Developers (Setup Repository)
1. Create a new repository on GitHub named `PythonToEXERelease`
2. Add the remote to your local repository:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/PythonToEXERelease.git
   ```
3. Push to GitHub:
   ```bash
   git push -u origin main
   ```
4. GitHub Actions will automatically build and create the first release

## Development Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd PythonToEXERelease
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run applications locally:
   ```bash
   python Codes/lock_scheduler_gui.py
   ```

## Manual Build

To manually build executables:

```bash
pyinstaller --onefile --windowed Codes/lock_scheduler_gui.py
```

## System Requirements

- **For Development**: Python 3.7+ and dependencies
- **For Executables**: Windows operating system only
- **For Lock Scheduler**: Administrator privileges may be required for system locking functionality

## CI/CD Pipeline Features

- **Cross-platform Building**: Uses GitHub-hosted Windows runners
- **Automated Versioning**: Incremental release numbering
- **Asset Management**: Automatic upload of built executables
- **Documentation Updates**: Automated README updates with download links

## Security Notice

The Lock Scheduler application uses Windows system APIs to lock the workstation. Ensure you have proper permissions and use responsibly.

## Contributing

1. Add Python scripts to the `Codes/` directory
2. Update `requirements.txt` if new dependencies are needed
3. Push to main branch to trigger automated build and release

## License

This project is provided as-is for educational and personal use purposes.