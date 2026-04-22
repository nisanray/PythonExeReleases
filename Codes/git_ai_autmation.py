import sys
import os
import subprocess
import datetime
import traceback
import threading
import json
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLineEdit, QListWidget, QListWidgetItem,
    QFileDialog, QLabel, QMessageBox, QSplitter, QGroupBox, QComboBox, QDialog,
    QSpinBox, QCheckBox, QInputDialog, QDialogButtonBox, QFormLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, qInstallMessageHandler, QtMsgType
from PyQt6.QtGui import QTextCursor


def _now_ts():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _console_log(message, level="INFO", source="APP"):
    line = f"[{_now_ts()}] [{level}] [{source}] {message}"
    print(line, flush=True)


def _append_debug_file(message, level="INFO", source="APP", log_path=None):
    try:
        target = log_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_git_assistant_debug.log")
        with open(target, "a", encoding="utf-8") as f:
            f.write(f"[{_now_ts()}] [{level}] [{source}] {message}\n")
    except Exception:
        pass


def _qt_message_handler(mode, context, message):
    if mode == QtMsgType.QtDebugMsg:
        level = "DEBUG"
    elif mode == QtMsgType.QtInfoMsg:
        level = "INFO"
    elif mode == QtMsgType.QtWarningMsg:
        level = "WARNING"
    elif mode == QtMsgType.QtCriticalMsg:
        level = "CRITICAL"
    else:
        level = "FATAL"

    _console_log(message, level=level, source="QT")
    _append_debug_file(message, level=level, source="QT")

# ==========================================
# 🧠 Background Thread for AI (Non-Blocking)
# ==========================================
class AIWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, diff_text, model="llama3", custom_prompt=None):
        super().__init__()
        self.diff_text = diff_text
        self.model = model
        self.custom_prompt = custom_prompt

    def run(self):
        _console_log(f"AIWorker started. model={self.model}, diff_chars={len(self.diff_text)}", source="AI")
        # Truncate diff to prevent overwhelming the AI context window
        max_chars = 10000
        diff_to_send = self.diff_text[:max_chars]
        if len(self.diff_text) > max_chars:
            diff_to_send += "\n... [DIFF TRUNCATED FOR AI]"
            _console_log(f"Diff truncated from {len(self.diff_text)} to {len(diff_to_send)} chars", source="AI")

        if self.custom_prompt:
            prompt = self.custom_prompt.replace("{diff}", diff_to_send)
        else:
            prompt = f"""Summarize this git diff into a concise commit message.
Rules:
- max 1 line
- imperative tone (e.g., 'Add feature' not 'Added feature')
- skip trivial changes
- ONLY output the commit message, no introductions or explanations.

Diff:
{diff_to_send}"""

        try:
            # Calls local Ollama instance
            _console_log("Running: ollama run <model> <prompt>", source="AI")
            result = subprocess.run(
                ["ollama", "run", self.model, prompt],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120
            )
            _console_log(f"Ollama process finished with code {result.returncode}", source="AI")
            
            if result.returncode != 0:
                _console_log(f"Ollama stderr: {result.stderr.strip()}", level="ERROR", source="AI")
                self.error.emit(f"Ollama Error: {result.stderr}")
            else:
                _console_log(f"AI response length: {len(result.stdout.strip())}", source="AI")
                self.finished.emit(result.stdout.strip())
        except FileNotFoundError:
            self.error.emit("Failed to run Ollama: 'ollama' command not found. Install Ollama and ensure it is in PATH.")
        except subprocess.TimeoutExpired:
            self.error.emit("Ollama request timed out after 120 seconds.")
        except Exception as e:
            _console_log(traceback.format_exc(), level="ERROR", source="AI")
            self.error.emit(f"Failed to run Ollama: {str(e)}")

# ==========================================
# 🖥️ Main GUI Application
# ==========================================
class AIGitAssistant(QMainWindow):
    def __init__(self):
        super().__init__()
        self.debug_log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_git_assistant_debug.log")
        self.config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_git_assistant_config.json")
        _console_log("Initializing AIGitAssistant window")
        _append_debug_file("Initializing AIGitAssistant window", log_path=self.debug_log_file)
        self.repo_path = ""
        self.settings = self.load_settings()
        self.commit_groups = {}  # Store groups: { "group_name": ["file1", "file2"] }
        self.custom_commit_prompt = "" # Store user-defined prompt
        
        # Timer setup for delayed commits
        self.commit_timer = QTimer(self)
        self.commit_timer.timeout.connect(self.timer_tick)
        self.time_left = 0
        
        # PREMIUM: Agent/Watcher timer
        self.watch_timer = QTimer(self)
        self.watch_timer.timeout.connect(self.watcher_tick)
        self.last_unstaged_count = 0
        
        self.dark_mode = False # Default to Light mode
        self.apply_theme()
        self.init_ui()

    def apply_theme(self):
        """Applies a high-tech theme (supports Light and Dark)."""
        if self.dark_mode:
            self.setStyleSheet("""
                QMainWindow, QWidget { 
                    background-color: #1a1b26; 
                    color: #a9b1d6; 
                    font-family: 'Segoe UI', Roboto, sans-serif;
                }
                QGroupBox { 
                    border: 1px solid #24283b; 
                    border-radius: 10px;
                    margin-top: 12px; 
                    font-weight: bold; 
                    background-color: #24283b44;
                    padding: 6px;
                }
                QGroupBox::title { 
                    subcontrol-origin: margin; 
                    left: 12px; 
                    padding: 0 5px;
                    color: #7aa2f7;
                }
                QLineEdit, QListWidget, QTextEdit, QComboBox, QSpinBox { 
                    background-color: #16161e; 
                    color: #c0caf5; 
                    border: 1px solid #292e42; 
                    border-radius: 6px;
                    padding: 8px;
                }
                QLineEdit:focus { border: 1px solid #7aa2f7; }
                
                QPushButton { 
                    background-color: #24283b; 
                    color: #c0caf5; 
                    border: 1px solid #414868; 
                    padding: 8px 15px; 
                    border-radius: 6px; 
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #2f3549; border: 1px solid #7aa2f7; }
                QPushButton:pressed { background-color: #3b4261; }
                QPushButton:disabled { color: #565f89; background-color: #1a1b26; }
                
                QPushButton#primary_btn { background-color: #7aa2f7; color: #1a1b26; border: none; }
                QPushButton#primary_btn:hover { background-color: #89ddff; }
                
                QPushButton#ai_btn { background-color: #bb9af7; color: #1a1b26; border: none; }
                QPushButton#ai_btn:hover { background-color: #c0caf5; }
                
                QPushButton#success_btn { background-color: #9ece6a; color: #1a1b26; border: none; }
                QPushButton#success_btn:hover { background-color: #b9f27c; }

                QPushButton#danger_btn { background-color: #f7768e; color: #1a1b26; border: none; }
                QPushButton#danger_btn:hover { background-color: #ff9e64; }

                QSplitter::handle { background-color: #24283b; }
                
                QScrollBar:vertical {
                    border: none; background: #16161e; width: 10px; margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background: #292e42; min-height: 20px; border-radius: 5px;
                }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow, QWidget { 
                    background-color: #f8fafc; 
                    color: #1e293b; 
                    font-family: 'Segoe UI', Roboto, sans-serif;
                }
                QGroupBox { 
                    border: 1px solid #e2e8f0; 
                    border-radius: 10px;
                    margin-top: 12px; 
                    font-weight: bold; 
                    background-color: #ffffff;
                    padding: 6px;
                }
                QGroupBox::title { 
                    subcontrol-origin: margin; 
                    left: 12px; 
                    padding: 0 5px;
                    color: #0ea5e9;
                }
                QLineEdit, QListWidget, QTextEdit, QComboBox, QSpinBox { 
                    background-color: #ffffff; 
                    color: #1e293b; 
                    border: 1px solid #cbd5e1; 
                    border-radius: 6px;
                    padding: 8px;
                }
                QLineEdit:focus { border: 1px solid #0ea5e9; }
                
                QPushButton { 
                    background-color: #f1f5f9; 
                    color: #475569; 
                    border: 1px solid #cbd5e1; 
                    padding: 8px 15px; 
                    border-radius: 6px; 
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #e2e8f0; border: 1px solid #0ea5e9; }
                QPushButton:pressed { background-color: #cbd5e1; }
                QPushButton:disabled { color: #94a3b8; background-color: #f8fafc; }
                
                QPushButton#primary_btn { background-color: #0ea5e9; color: white; border: none; }
                QPushButton#primary_btn:hover { background-color: #38bdf8; }
                
                QPushButton#ai_btn { background-color: #8b5cf6; color: white; border: none; }
                QPushButton#ai_btn:hover { background-color: #a78bfa; }
                
                QPushButton#success_btn { background-color: #10b981; color: white; border: none; }
                QPushButton#success_btn:hover { background-color: #34d399; }

                QPushButton#danger_btn { background-color: #ef4444; color: white; border: none; }
                QPushButton#danger_btn:hover { background-color: #f87171; }

                QSplitter::handle { background-color: #e2e8f0; }
                
                QScrollBar:vertical {
                    border: none; background: #f8fafc; width: 10px; margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background: #cbd5e1; min-height: 20px; border-radius: 5px;
                }
            """)

    def init_ui(self):
        self.setWindowTitle("AI Git Assistant - Pro Edition")
        self.resize(1200, 850)

        # Main Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # -- Top Bar: Repo Selection --
        top_bar = QHBoxLayout()
        self.btn_select_repo = QPushButton("📂 Select Repository")
        self.btn_select_repo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_select_repo.clicked.connect(self.select_repo)
        self.lbl_repo_path = QLabel("No repository selected")
        self.lbl_repo_path.setStyleSheet("color: #565f89; font-style: italic;")
        
        top_bar.addWidget(self.btn_select_repo)
        top_bar.addWidget(self.lbl_repo_path)
        
        # --- PREMIUM: Branch & Network Controls ---
        top_bar.addSpacing(10)
        self.combo_branch = QComboBox()
        self.combo_branch.setFixedWidth(120)
        self.combo_branch.activated.connect(self.checkout_branch)
        top_bar.addWidget(QLabel("🌿"))
        top_bar.addWidget(self.combo_branch)

        self.btn_new_branch = QPushButton("➕")
        self.btn_new_branch.setToolTip("New Branch")
        self.btn_new_branch.clicked.connect(self.create_branch)
        top_bar.addWidget(self.btn_new_branch)
        
        self.btn_pull = QPushButton("⬇️")
        self.btn_pull.setToolTip("Pull from Remote")
        self.btn_pull.clicked.connect(self.pull_repo)
        
        self.btn_push = QPushButton("⬆️")
        self.btn_push.setToolTip("Push to Remote")
        self.btn_push.clicked.connect(self.push_repo)
        
        self.btn_history = QPushButton("📜")
        self.btn_history.setToolTip("View History")
        self.btn_history.clicked.connect(self.show_history)
        
        top_bar.addWidget(self.btn_pull)
        top_bar.addWidget(self.btn_push)
        top_bar.addWidget(self.btn_history)

        # PREMIUM Extras in Top Bar
        self.btn_standup = QPushButton("📅")
        self.btn_standup.setToolTip("Daily Standup")
        self.btn_standup.clicked.connect(self.generate_daily_standup)
        
        self.btn_settings = QPushButton("⚙️")
        self.btn_settings.setToolTip("Settings")
        self.btn_settings.clicked.connect(self.open_settings)

        self.btn_toggle_logs = QPushButton("🧾 Hub")
        self.btn_toggle_logs.setToolTip("Show/Hide Activity Hub")
        self.btn_toggle_logs.setCheckable(True)
        self.btn_toggle_logs.setChecked(True)
        self.btn_toggle_logs.clicked.connect(self.toggle_activity_hub)
        
        self.chk_agent_mode = QCheckBox("🤖 Watcher")
        self.chk_agent_mode.stateChanged.connect(self.toggle_agent_mode)
        
        top_bar.addWidget(self.btn_standup)
        top_bar.addWidget(self.btn_settings)
        top_bar.addWidget(self.btn_toggle_logs)
        top_bar.addWidget(self.chk_agent_mode)

        top_bar.addStretch()
        
        # PREMIUM: Auto-detect Ollama Models
        self.lbl_model = QLabel("🧠 Model:")
        self.combo_model = QComboBox()
        self.combo_model.setFixedWidth(120)
        self.fetch_ollama_models()
        
        top_bar.addWidget(self.lbl_model)
        top_bar.addWidget(self.combo_model)
        
        main_layout.addLayout(top_bar)

        # -- Splitter for 3 Panels: Files, Diff, Actions --
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.content_splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(self.content_splitter)
        self.content_splitter.addWidget(self.main_splitter)

        # 1. Left Panel: File Selection
        file_panel = QGroupBox("Git Workspace")
        file_layout = QVBoxLayout(file_panel)
        
        # PREMIUM: File Focus Mode (Filter)
        self.entry_file_filter = QLineEdit()
        self.entry_file_filter.setPlaceholderText("🔍 Filter files...")
        self.entry_file_filter.textChanged.connect(self.filter_files)
        file_layout.addWidget(self.entry_file_filter)

        btn_refresh = QPushButton("🔄 Sync Status")
        btn_refresh.clicked.connect(self.refresh_status)
        file_layout.addWidget(btn_refresh)

        # --- Unstaged ---
        unstaged_header = QHBoxLayout()
        unstaged_header.addWidget(QLabel("📝 Working Tree"))
        self.btn_ai_split = QPushButton("🤖 Split")
        self.btn_ai_split.setObjectName("ai_btn")
        self.btn_ai_split.clicked.connect(self.suggest_commit_splits)
        unstaged_header.addWidget(self.btn_ai_split)
        file_layout.addLayout(unstaged_header)
        
        self.list_unstaged = QListWidget()
        self.list_unstaged.itemDoubleClicked.connect(self.stage_single_item)
        file_layout.addWidget(self.list_unstaged)
        
        un_btn_layout = QHBoxLayout()
        btn_stage_sel = QPushButton("Stage ⬇️")
        btn_stage_sel.clicked.connect(self.stage_selected)
        btn_stage_all = QPushButton("All ⏬")
        btn_stage_all.clicked.connect(self.stage_all)
        un_btn_layout.addWidget(btn_stage_sel)
        un_btn_layout.addWidget(btn_stage_all)
        file_layout.addLayout(un_btn_layout)

        # PREMIUM: Discard and Stash
        un_btn_layout2 = QHBoxLayout()
        btn_discard = QPushButton("🗑️ Discard")
        btn_discard.setObjectName("danger_btn")
        btn_discard.clicked.connect(self.discard_selected)
        
        btn_stash = QPushButton("📦 Stash")
        btn_stash.clicked.connect(self.stash_changes)
        un_btn_layout2.addWidget(btn_discard)
        un_btn_layout2.addWidget(btn_stash)
        file_layout.addLayout(un_btn_layout2)

        # --- Staged ---
        file_layout.addWidget(QLabel("📦 Staged Area"))
        self.list_staged = QListWidget()
        self.list_staged.itemDoubleClicked.connect(self.unstage_single_item)
        file_layout.addWidget(self.list_staged)
        
        st_btn_layout = QHBoxLayout()
        btn_unstage_sel = QPushButton("Unstage ⬆️")
        btn_unstage_sel.clicked.connect(self.unstage_selected)
        btn_unstage_all = QPushButton("All ⏬")
        btn_unstage_all.clicked.connect(self.unstage_all)
        st_btn_layout.addWidget(btn_unstage_sel)
        st_btn_layout.addWidget(btn_unstage_all)
        file_layout.addLayout(st_btn_layout)
        
        btn_pop = QPushButton("📤 Pop Stash")
        btn_pop.clicked.connect(self.pop_stash)
        file_layout.addWidget(btn_pop)
        
        # --- Commit Groups UI ---
        group_box = QGroupBox("Custom Groups")
        group_layout = QVBoxLayout(group_box)
        
        group_ctrl_layout = QHBoxLayout()
        self.entry_group_name = QLineEdit()
        self.entry_group_name.setPlaceholderText("Name...")
        btn_save_group = QPushButton("💾")
        btn_save_group.clicked.connect(self.save_group)
        group_ctrl_layout.addWidget(self.entry_group_name)
        group_ctrl_layout.addWidget(btn_save_group)
        group_layout.addLayout(group_ctrl_layout)

        load_layout = QHBoxLayout()
        self.combo_groups = QComboBox()
        btn_load_group = QPushButton("📂")
        btn_load_group.clicked.connect(self.load_group)
        load_layout.addWidget(self.combo_groups)
        load_layout.addWidget(btn_load_group)
        group_layout.addLayout(load_layout)

        file_layout.addWidget(group_box)
        self.main_splitter.addWidget(file_panel)

        # 2. Middle Panel: Diff Viewer
        diff_panel = QGroupBox("Diff Inspector")
        diff_layout = QVBoxLayout(diff_panel)

        diff_btn_layout = QHBoxLayout()
        btn_diff_unstaged = QPushButton("🔍 Unstaged")
        btn_diff_unstaged.clicked.connect(self.check_diff_unstaged)
        btn_diff_staged = QPushButton("📦 Staged")
        btn_diff_staged.clicked.connect(self.check_diff_staged)
        self.btn_blame = QPushButton("🕵️ Blame")
        self.btn_blame.clicked.connect(self.blame_file)
        
        diff_btn_layout.addWidget(btn_diff_unstaged)
        diff_btn_layout.addWidget(btn_diff_staged)
        diff_btn_layout.addWidget(self.btn_blame)
        diff_layout.addLayout(diff_btn_layout)

        # PREMIUM: Diff Search & Filters
        search_filter_layout = QHBoxLayout()
        self.chk_ignore_ws = QCheckBox("Ignore WS")
        search_filter_layout.addWidget(self.chk_ignore_ws)
        
        self.entry_search_diff = QLineEdit()
        self.entry_search_diff.setPlaceholderText("🔍 Search...")
        self.entry_search_diff.returnPressed.connect(self.search_diff)
        btn_search_diff = QPushButton("Next")
        btn_search_diff.clicked.connect(self.search_diff)
        search_filter_layout.addWidget(self.entry_search_diff)
        search_filter_layout.addWidget(btn_search_diff)
        diff_layout.addLayout(search_filter_layout)

        self.text_diff = QTextEdit()
        self.text_diff.setReadOnly(True)
        self.text_diff.setStyleSheet(f"font-family: 'JetBrains Mono', 'Consolas', monospace; background-color: {'#0f111a' if self.dark_mode else '#ffffff'}; border: 1px solid {'#1a1b26' if self.dark_mode else '#cbd5e1'};")
        diff_layout.addWidget(self.text_diff)
        
        btn_save_diff = QPushButton("💾 Export Diff")
        btn_save_diff.clicked.connect(self.save_diff)
        diff_layout.addWidget(btn_save_diff)
        
        self.main_splitter.addWidget(diff_panel)

        # 3. Right Panel: AI & Commit Actions
        action_panel = QGroupBox("Intelligence Center")
        action_layout = QVBoxLayout(action_panel)

        # PREMIUM: Issue Linking + Conventional Commits
        conv_issue_layout = QHBoxLayout()
        self.chk_conventional = QCheckBox("Conventional")
        self.chk_conventional.setChecked(True)
        conv_issue_layout.addWidget(self.chk_conventional)
        
        self.entry_issue = QLineEdit()
        self.entry_issue.setPlaceholderText("Issue #")
        self.entry_issue.setFixedWidth(80)
        conv_issue_layout.addWidget(self.entry_issue)
        action_layout.addLayout(conv_issue_layout)

        self.btn_ai_gen = QPushButton("🤖 Generate AI Message")
        self.btn_ai_gen.setObjectName("ai_btn")
        self.btn_ai_gen.clicked.connect(self.generate_ai_message)
        action_layout.addWidget(self.btn_ai_gen)

        # AI Tools Grid
        ai_tools_grid1 = QHBoxLayout()
        self.btn_ai_explain = QPushButton("🧠 Explain")
        self.btn_ai_explain.setObjectName("ai_btn")
        self.btn_ai_explain.clicked.connect(self.explain_ai_message)
        self.btn_ai_risk = QPushButton("⚠️ Risk")
        self.btn_ai_risk.setObjectName("ai_btn")
        self.btn_ai_risk.clicked.connect(self.analyze_risk_message)
        ai_tools_grid1.addWidget(self.btn_ai_explain)
        ai_tools_grid1.addWidget(self.btn_ai_risk)
        action_layout.addLayout(ai_tools_grid1)
        
        ai_tools_grid2 = QHBoxLayout()
        self.btn_ai_review = QPushButton("🔎 Review")
        self.btn_ai_review.setObjectName("ai_btn")
        self.btn_ai_review.clicked.connect(self.review_single_file)
        self.btn_ai_conflicts = QPushButton("🔀 Conflicts")
        self.btn_ai_conflicts.setObjectName("danger_btn")
        self.btn_ai_conflicts.clicked.connect(self.explain_conflicts)
        ai_tools_grid2.addWidget(self.btn_ai_review)
        ai_tools_grid2.addWidget(self.btn_ai_conflicts)
        action_layout.addLayout(ai_tools_grid2)

        action_layout.addSpacing(10)
        action_layout.addWidget(QLabel("📝 Commit Message:"))
        self.entry_commit = QTextEdit()
        self.entry_commit.setPlaceholderText("Summarize your work...")
        self.entry_commit.setFixedHeight(80)
        action_layout.addWidget(self.entry_commit)

        # PREMIUM: Pre-commit checks
        self.entry_pre_commit = QLineEdit()
        self.entry_pre_commit.setPlaceholderText("Pre-commit test (e.g., pytest)...")
        action_layout.addWidget(self.entry_pre_commit)

        # --- Timed Commit Controls ---
        timer_box = QGroupBox("Timed Execution")
        timer_layout = QVBoxLayout(timer_box)
        
        spin_layout = QHBoxLayout()
        spin_layout.addWidget(QLabel("Delay:"))
        self.spin_delay = QSpinBox()
        self.spin_delay.setRange(0, 3600)
        self.spin_delay.setSuffix("s")
        spin_layout.addWidget(self.spin_delay)
        timer_layout.addLayout(spin_layout)

        timer_btn_layout = QHBoxLayout()
        self.btn_timed_commit = QPushButton("⏲️ Start")
        self.btn_timed_commit.clicked.connect(self.start_timed_commit)
        self.btn_cancel_timer = QPushButton("🛑 Stop")
        self.btn_cancel_timer.setObjectName("danger_btn")
        self.btn_cancel_timer.clicked.connect(self.cancel_timer)
        self.btn_cancel_timer.setEnabled(False)
        timer_btn_layout.addWidget(self.btn_timed_commit)
        timer_btn_layout.addWidget(self.btn_cancel_timer)
        timer_layout.addLayout(timer_btn_layout)
        
        action_layout.addWidget(timer_box)

        self.lbl_timer_status = QLabel("")
        self.lbl_timer_status.setStyleSheet("color: #ff9e64; font-weight: bold;")
        action_layout.addWidget(self.lbl_timer_status)

        self.btn_commit = QPushButton("✅ Commit Now")
        self.btn_commit.setObjectName("success_btn")
        self.btn_commit.setFixedHeight(40)
        self.btn_commit.clicked.connect(self.commit_files)
        action_layout.addWidget(self.btn_commit)

        action_layout.addSpacing(10)
        self.btn_auto_commit = QPushButton("⚡ Smart Auto-Flow")
        self.btn_auto_commit.setObjectName("primary_btn")
        self.btn_auto_commit.setFixedHeight(45)
        self.btn_auto_commit.clicked.connect(self.auto_commit_flow)
        action_layout.addWidget(self.btn_auto_commit)
        
        action_layout.addStretch()
        
        danger_box = QGroupBox("Danger Zone")
        danger_layout = QVBoxLayout(danger_box)
        self.btn_undo = QPushButton("↩️ Undo Last Commit")
        self.btn_undo.setObjectName("danger_btn")
        self.btn_undo.clicked.connect(self.undo_last_commit)
        danger_layout.addWidget(self.btn_undo)
        action_layout.addWidget(danger_box)

        self.main_splitter.addWidget(action_panel)

        # Set initial splitter sizes
        self.main_splitter.setSizes([300, 500, 300])

        # -- Bottom Panel: Logs --
        self.log_panel = QGroupBox("Activity Hub")
        log_layout = QVBoxLayout(self.log_panel)
        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("Runtime Logs"))
        log_header.addStretch()
        self.btn_close_hub = QPushButton("✕")
        self.btn_close_hub.setToolTip("Close Activity Hub")
        self.btn_close_hub.setFixedWidth(34)
        self.btn_close_hub.clicked.connect(self.close_activity_hub)
        log_header.addWidget(self.btn_close_hub)
        log_layout.addLayout(log_header)
        self.text_log = QTextEdit()
        self.text_log.setMinimumHeight(70)
        self.text_log.setReadOnly(True)
        self.text_log.setStyleSheet(f"background-color: {'#0f111a' if self.dark_mode else '#ffffff'}; color: {'#7aa2f7' if self.dark_mode else '#0ea5e9'}; border: none;")
        log_layout.addWidget(self.text_log)
        self.content_splitter.addWidget(self.log_panel)
        self.content_splitter.setSizes([760, 150])
        self.content_splitter.setCollapsible(1, True)

        self.log("AI Intelligence Suite ready.")
        self.restore_last_repo()

    def close_activity_hub(self):
        self.btn_toggle_logs.setChecked(False)
        self.toggle_activity_hub()

    def toggle_activity_hub(self):
        visible = self.btn_toggle_logs.isChecked()
        self.log_panel.setVisible(visible)
        if visible:
            self.content_splitter.setSizes([760, 150])
            self.log("Activity Hub opened.")
        else:
            self.content_splitter.setSizes([1000, 0])
            self.log("Activity Hub closed.")

    # ==========================================
    # 🛠️ Helper Methods
    # ==========================================
    def log(self, text):
        line = f"[{_now_ts()}] {text}"
        _console_log(text)
        _append_debug_file(text, log_path=self.debug_log_file)

        if hasattr(self, "text_log"):
            self.text_log.append(line)
            scrollbar = self.text_log.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        
        if self.repo_path:
            try:
                log_file = os.path.join(self.repo_path, "ai_git_assistant.log")
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"{line}\n")
            except Exception:
                pass

    def load_settings(self):
        default_settings = {"last_repo_path": ""}
        if not os.path.exists(self.config_file):
            return default_settings

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                default_settings.update(data)
            return default_settings
        except Exception as e:
            _console_log(f"Failed to load settings file: {e}", level="WARNING", source="SETTINGS")
            _append_debug_file(f"Failed to load settings file: {e}", level="WARNING", source="SETTINGS", log_path=self.debug_log_file)
            return default_settings

    def save_settings(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
            self.log(f"Saved settings to {self.config_file}")
        except Exception as e:
            self.log(f"Failed to save settings: {e}")

    def restore_last_repo(self):
        last_repo = self.settings.get("last_repo_path", "").strip()
        if not last_repo:
            self.log("No previous repository path stored.")
            return

        if os.path.isdir(last_repo) and os.path.exists(os.path.join(last_repo, ".git")):
            self.set_repo_path(last_repo, restored=True)
        else:
            self.log(f"Stored repository path is invalid or missing .git: {last_repo}")

    def set_repo_path(self, folder, restored=False):
        self.repo_path = folder
        self.lbl_repo_path.setText(folder)
        label_color = "#c0caf5" if self.dark_mode else "#1e293b"
        self.lbl_repo_path.setStyleSheet(f"color: {label_color};")

        self.settings["last_repo_path"] = folder
        self.save_settings()

        if restored:
            self.log(f"Restored repository from last session: {self.repo_path}")
        else:
            self.log(f"Selected repository: {self.repo_path}")
        self.refresh_status()

    def run_git(self, cmd_args):
        if not self.repo_path:
            self.log("Error: No repository selected.")
            return False, ""

        if not os.path.isdir(self.repo_path):
            self.log(f"Error: Repository path no longer exists: {self.repo_path}")
            return False, "Repository path does not exist."

        if not os.path.exists(os.path.join(self.repo_path, ".git")):
            self.log(f"Error: Missing .git directory at: {self.repo_path}")
            return False, "Selected folder is not a git repository."
        
        try:
            cmd_display = "git " + " ".join(cmd_args)
            self.log(f"Running command: {cmd_display}")
            result = subprocess.run(
                ["git"] + cmd_args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60
            )
            self.log(f"Command exit code: {result.returncode}")

            if result.stdout.strip():
                self.log(f"stdout ({len(result.stdout.strip())} chars): {result.stdout.strip()[:1000]}")
            if result.stderr.strip():
                self.log(f"stderr ({len(result.stderr.strip())} chars): {result.stderr.strip()[:1000]}")

            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip() or f"Git command failed with exit code {result.returncode}."
                return False, error_msg
            return True, result.stdout.strip()
        except FileNotFoundError:
            msg = "Git command not found. Install Git and ensure it is in PATH."
            self.log(msg)
            return False, msg
        except subprocess.TimeoutExpired:
            msg = "Git command timed out after 60 seconds."
            self.log(msg)
            return False, msg
        except PermissionError:
            msg = "Permission denied while accessing repository or running Git."
            self.log(msg)
            return False, msg
        except Exception as e:
            self.log(f"Exception while running git command: {traceback.format_exc()}")
            return False, str(e)

    def get_checked_items(self, list_widget):
        files = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked and not item.isHidden():
                files.append(item.data(Qt.ItemDataRole.UserRole))
        return files

    def fetch_ollama_models(self):
        """Automatically detects installed Ollama models."""
        try:
            self.log("Detecting local Ollama models...")
            res = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=20)
            self.log(f"ollama list exit code: {res.returncode}")
            if res.returncode == 0:
                lines = res.stdout.strip().split('\n')[1:] # Skip header
                models = [line.split()[0] for line in lines if line]
                self.combo_model.addItems(models)
                self.log(f"Detected {len(models)} local Ollama models.")
            else:
                self.combo_model.addItem("llama3")
                self.log("Could not read Ollama models, fallback to llama3.")
                if res.stderr.strip():
                    self.log(f"ollama list stderr: {res.stderr.strip()[:500]}")
        except FileNotFoundError:
            self.combo_model.addItem("llama3")
            self.log("Ollama command not found. Install Ollama or keep using fallback model 'llama3'.")
        except subprocess.TimeoutExpired:
            self.combo_model.addItem("llama3")
            self.log("ollama list timed out. Using fallback model 'llama3'.")
        except Exception as e:
            self.combo_model.addItem("llama3")
            self.log(f"Failed to detect Ollama models. Using fallback model llama3. Error: {e}")

    # ==========================================
    # 📦 Commit Group & Workflow Methods
    # ==========================================
    def toggle_agent_mode(self):
        if self.chk_agent_mode.isChecked():
            self.watch_timer.start(60000) 
            self.log("🤖 Agent Mode activated. Monitoring repository in background.")
        else:
            self.watch_timer.stop()
            self.log("🤖 Agent Mode disabled.")

    def watcher_tick(self):
        if not self.repo_path: return
        success, output = self.run_git(["status", "--porcelain"])
        if not success: return

        unstaged_files = [line for line in output.split('\n') if len(line) > 2 and line[1] != ' ']
        count = len(unstaged_files)

        if count > 0 and count != self.last_unstaged_count:
            if count >= 5:
                self.log(f"🤖 Agent Notice: You have {count} unstaged files accumulated. Consider reviewing and committing!")
        self.last_unstaged_count = count

    def stash_changes(self):
        success, out = self.run_git(["stash", "push", "-m", "Auto-stash from AI Git Assistant"])
        if success:
            self.log(f"📦 Stashed changes: {out}")
            self.refresh_status()
        else:
            QMessageBox.critical(self, "Stash Error", f"Failed to stash:\n{out}")

    def pop_stash(self):
        success, out = self.run_git(["stash", "pop"])
        if success:
            self.log(f"📤 Popped stash: {out}")
            self.refresh_status()
        else:
            QMessageBox.warning(self, "Stash Pop Error", f"Failed to pop stash (might be empty or conflict):\n{out}")

    def discard_selected(self):
        files = self.get_checked_items(self.list_unstaged)
        if not files:
            QMessageBox.warning(self, "No Files", "Select unstaged files to discard.")
            return
            
        reply = QMessageBox.question(
            self, "Discard Changes", 
            f"WARNING: This will permanently delete your uncommitted changes in {len(files)} files. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            success, out = self.run_git(["restore", "--"] + files)
            if success:
                self.log(f"🗑️ Discarded changes in {len(files)} files.")
                self.refresh_status()
            else:
                self.log(f"Failed to discard: {out}")

    def filter_files(self):
        query = self.entry_file_filter.text().lower()
        for list_widget in [self.list_unstaged, self.list_staged]:
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                filename = item.data(Qt.ItemDataRole.UserRole).lower()
                item.setHidden(query not in filename)

    def open_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("AI Configuration & Settings")
        dialog.resize(500, 300)
        layout = QVBoxLayout(dialog)
        
        form = QFormLayout()
        
        self.text_custom_prompt = QTextEdit()
        self.text_custom_prompt.setPlaceholderText("Leave blank to use default. Use {diff} as a placeholder for the git diff.")
        self.text_custom_prompt.setPlainText(self.custom_commit_prompt)
        
        form.addRow("Custom Commit Prompt:", self.text_custom_prompt)
        layout.addLayout(form)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.custom_commit_prompt = self.text_custom_prompt.toPlainText().strip()
            self.log("Settings saved.")

    def save_group(self):
        group_name = self.entry_group_name.text().strip()
        selected = self.get_checked_items(self.list_unstaged)
        
        if not group_name or not selected:
            QMessageBox.warning(self, "Error", "Ensure a group name is entered and unstaged files are selected.")
            return
        
        self.commit_groups[group_name] = selected
        if self.combo_groups.findText(group_name) == -1:
            self.combo_groups.addItem(group_name)
        self.log(f"Saved group '{group_name}'.")
        self.entry_group_name.clear()

    def load_group(self):
        group_name = self.combo_groups.currentText()
        if not group_name or group_name not in self.commit_groups: return
        
        target_files = self.commit_groups[group_name]
        for i in range(self.list_unstaged.count()):
            item = self.list_unstaged.item(i)
            filename = item.data(Qt.ItemDataRole.UserRole)
            item.setCheckState(Qt.CheckState.Checked if filename in target_files else Qt.CheckState.Unchecked)
        self.log(f"Loaded group '{group_name}'.")

    # ==========================================
    # 🚀 Core Functions
    # ==========================================
    def select_repo(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Git Repository")
        if folder:
            if os.path.exists(os.path.join(folder, ".git")):
                self.set_repo_path(folder)
            else:
                QMessageBox.warning(self, "Invalid Repo", "Selected folder does not contain a .git directory.")

    def refresh_status(self):
        self.list_unstaged.clear()
        self.list_staged.clear()
        self.refresh_branches()
        
        success, output = self.run_git(["status", "--porcelain"])
        if not success:
            self.log(f"Error fetching status: {output}")
            return
        if not output:
            self.log("Working tree is clean.")
            return

        lines = output.split('\n')
        for line in lines:
            if len(line) < 3: continue
            status_staged = line[0]
            status_unstaged = line[1]
            filename = line[3:]
            
            if status_staged not in [' ', '?']:
                item = QListWidgetItem(f"[{status_staged} ] {filename}")
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                item.setData(Qt.ItemDataRole.UserRole, filename)
                self.list_staged.addItem(item)
                
            if status_unstaged != ' ':
                display_status = status_unstaged
                if status_staged == '?' and status_unstaged == '?':
                    display_status = '??' 
                item = QListWidgetItem(f"[ {display_status}] {filename}")
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                item.setData(Qt.ItemDataRole.UserRole, filename)
                self.list_unstaged.addItem(item)
            
        self.log(f"Found {self.list_staged.count()} staged, {self.list_unstaged.count()} unstaged files.")

    def stage_single_item(self, item):
        filename = item.data(Qt.ItemDataRole.UserRole)
        self.run_git(["add", "--", filename])
        self.log(f"Staged {filename}")
        self.refresh_status()

    def unstage_single_item(self, item):
        filename = item.data(Qt.ItemDataRole.UserRole)
        self.run_git(["reset", "HEAD", "--", filename])
        self.log(f"Unstaged {filename}")
        self.refresh_status()

    def stage_selected(self):
        files = self.get_checked_items(self.list_unstaged)
        if files:
            self.run_git(["add", "--"] + files)
            self.log(f"Staged {len(files)} files.")
            self.refresh_status()

    def stage_all(self):
        if self.list_staged.count() > 0:
            reply = QMessageBox.question(self, "Warning", "Staging all will include already staged + new files. Continue?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No: return
        self.run_git(["add", "."])
        self.log("Staged all files.")
        self.refresh_status()

    def unstage_selected(self):
        files = self.get_checked_items(self.list_staged)
        if files:
            self.run_git(["reset", "HEAD", "--"] + files)
            self.log(f"Unstaged {len(files)} files.")
            self.refresh_status()

    def unstage_all(self):
        self.run_git(["reset", "HEAD"])
        self.log("Unstaged all files.")
        self.refresh_status()

    def _get_diff_cmd(self, base_cmd):
        if self.chk_ignore_ws.isChecked():
            base_cmd.insert(1, "-w")
        return base_cmd

    def check_diff_unstaged(self):
        selected = self.get_checked_items(self.list_unstaged)
        if not selected:
            QMessageBox.information(self, "No files", "Please select unstaged files to diff.")
            return ""

        cmd = self._get_diff_cmd(["diff", "--"]) + selected
        success, output = self.run_git(cmd)
        if success:
            self.display_diff_html(output if output else "No diff available (might be untracked or whitespace only).")
            self.log(f"Generated unstaged diff for {len(selected)} file(s).")
            return output
        return ""

    def check_diff_staged(self):
        cmd = self._get_diff_cmd(["diff", "--cached"])
        success, output = self.run_git(cmd)
        if success:
            self.display_diff_html(output if output else "No staged changes.")
            self.log("Generated staged diff.")
            return output
        return ""

    def search_diff(self):
        search_term = self.entry_search_diff.text()
        if not search_term: return
        
        found = self.text_diff.find(search_term)
        if not found:
            self.text_diff.moveCursor(QTextCursor.MoveOperation.Start)
            found = self.text_diff.find(search_term)
            if not found:
                self.log(f"Search term '{search_term}' not found in diff.")

    def blame_file(self):
        """Displays Git blame for a selected file."""
        files = self.get_checked_items(self.list_unstaged) + self.get_checked_items(self.list_staged)
        if not files:
            QMessageBox.warning(self, "No File Selected", "Please select a file to blame.")
            return
            
        file_to_blame = files[0] # Take first selected
        success, out = self.run_git(["blame", file_to_blame])
        
        if success:
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Git Blame: {file_to_blame}")
            dialog.resize(900, 600)
            layout = QVBoxLayout(dialog)
            
            text_box = QTextEdit()
            text_box.setReadOnly(True)
            text_box.setPlainText(out)
            text_box.setStyleSheet("font-family: Consolas, monospace; white-space: pre;")
            layout.addWidget(text_box)
            dialog.exec()
        else:
            QMessageBox.critical(self, "Blame Error", f"Failed to blame file:\n{out}")

    # ==========================================
    # 💎 Premium Features: Display, Branch, Network
    # ==========================================
    def display_diff_html(self, diff_text):
        """Renders Git diff with premium syntax highlighting."""
        if not diff_text or diff_text.startswith("No diff"):
            self.text_diff.setPlainText(diff_text)
            return

        # Theme-aware colors
        if self.dark_mode:
            color_add = "#a6e22e"; bg_add = "#1a3315"
            color_sub = "#f92672"; bg_sub = "#331515"
            color_hunk = "#66d9ef"
            color_header = "#fd971f"
            color_base = "#f8f8f2"
        else:
            color_add = "#16a34a"; bg_add = "#f0fdf4"
            color_sub = "#dc2626"; bg_sub = "#fef2f2"
            color_hunk = "#0284c7"
            color_header = "#ea580c"
            color_base = "#1e293b"

        html = f"<pre style='font-family: JetBrains Mono, Consolas, monospace; line-height: 1.4; color: {color_base};'>"
        for line in diff_text.splitlines():
            clean_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if line.startswith("+") and not line.startswith("+++"):
                html += f"<div style='color: {color_add}; background-color: {bg_add};'>{clean_line}</div>"
            elif line.startswith("-") and not line.startswith("---"):
                html += f"<div style='color: {color_sub}; background-color: {bg_sub};'>{clean_line}</div>"
            elif line.startswith("@@"):
                html += f"<div style='color: {color_hunk}; font-weight: bold;'>{clean_line}</div>"
            elif line.startswith("diff ") or line.startswith("index ") or line.startswith("---") or line.startswith("+++"):
                html += f"<div style='color: {color_header}; font-weight: bold;'>{clean_line}</div>"
            else:
                html += f"<div style='color: {color_base};'>{clean_line}</div>"
        html += "</pre>"
        self.text_diff.setHtml(html)

    def refresh_branches(self):
        success, output = self.run_git(["branch", "--format=%(refname:short)"])
        if success:
            self.combo_branch.blockSignals(True)
            self.combo_branch.clear()
            branches = output.splitlines()
            self.combo_branch.addItems(branches)
            
            _, current = self.run_git(["branch", "--show-current"])
            idx = self.combo_branch.findText(current.strip())
            if idx >= 0:
                self.combo_branch.setCurrentIndex(idx)
            self.combo_branch.blockSignals(False)

    def checkout_branch(self):
        branch = self.combo_branch.currentText()
        if branch:
            success, output = self.run_git(["checkout", branch])
            self.log(f"Switched to branch '{branch}': {output}")
            self.refresh_status()

    def create_branch(self):
        text, ok = QInputDialog.getText(self, "New Branch", "Enter new branch name:")
        if ok and text.strip():
            branch_name = text.strip()
            success, output = self.run_git(["checkout", "-b", branch_name])
            if success:
                self.log(f"Created and switched to branch '{branch_name}'")
                self.refresh_status()
            else:
                QMessageBox.critical(self, "Error", f"Failed to create branch:\n{output}")

    def pull_repo(self):
        self.log("Pulling from remote...")
        success, output = self.run_git(["pull"])
        self.log(f"Pull result: {output}")
        self.refresh_status()

    def push_repo(self):
        self.log("Pushing to remote...")
        success, output = self.run_git(["push"])
        self.log(f"Push result: {output}")

    def show_history(self):
        if not self.repo_path: return
        success, output = self.run_git(["log", "--oneline", "-n", "30"])
        if not success: return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Commit History (Last 30)")
        dialog.resize(600, 500)
        layout = QVBoxLayout(dialog)
        
        history_list = QListWidget()
        history_list.addItems(output.splitlines())
        layout.addWidget(history_list)

        btn_summarize = QPushButton("🧠 AI: Summarize Recent Activity")
        btn_summarize.setStyleSheet("background-color: #6b2b84; color: white;")
        layout.addWidget(btn_summarize)

        def summarize_history():
            btn_summarize.setEnabled(False)
            btn_summarize.setText("⏳ Analyzing History...")
            prompt = "Summarize the following git commit history. Group related changes and explain the general direction of the recent work:\n\n{diff}"
            model = self.combo_model.currentText() or "llama3"
            self.ai_thread = AIWorker(output, model, custom_prompt=prompt)
            self.ai_thread.finished.connect(lambda res: self._show_ai_dialog("History Summary", res, btn_summarize, "🧠 AI: Summarize Recent Activity"))
            self.ai_thread.error.connect(self.on_ai_error)
            self.ai_thread.start()

        btn_summarize.clicked.connect(summarize_history)
        dialog.exec()

    def generate_daily_standup(self):
        if not self.repo_path:
            QMessageBox.warning(self, "No Repo", "Select a repository first.")
            return
            
        self.btn_standup.setEnabled(False)
        self.btn_standup.setText("⏳ Analyzing...")
        
        success, output = self.run_git(["log", "--since=1.day", "--oneline", "--author", ""])
        if not success or not output.strip():
            QMessageBox.information(self, "No Activity", "No commits found in the last 24 hours.")
            self.btn_standup.setEnabled(True)
            self.btn_standup.setText("📅 Daily Standup")
            return
            
        prompt = """I need a summary of my work for a daily standup meeting.
Based on the following git commits from the last 24 hours, write a brief, professional summary of what I accomplished. 
Use bullet points.

Commits:
{diff}"""
        model = self.combo_model.currentText() or "llama3"

        self.ai_thread = AIWorker(output, model, custom_prompt=prompt)
        self.ai_thread.finished.connect(lambda res: self._show_ai_dialog("Daily Standup Summary", res, self.btn_standup, "📅 Daily Standup"))
        self.ai_thread.error.connect(self.on_ai_error)
        self.ai_thread.start()

    # ==========================================
    # 🧠 AI Core Methods
    # ==========================================
    def generate_ai_message(self, auto_commit=False):
        success, diff = self.run_git(["diff", "--cached"])
        if not diff.strip():
            if not auto_commit: QMessageBox.warning(self, "No Staged Changes", "Stage files first.")
            return

        self.btn_ai_gen.setEnabled(False)
        self.btn_ai_gen.setText("⏳ Generating...")
        self.entry_commit.clear()
        
        model = self.combo_model.currentText() or "llama3"
        prompt = None

        if self.custom_commit_prompt:
            prompt = self.custom_commit_prompt
        elif self.chk_conventional.isChecked():
            prompt = """Summarize this git diff into a CONVENTIONAL commit message.
Rules:
- max 1 line
- Must start with feat:, fix:, refactor:, docs:, style:, or chore:
- imperative tone
- ONLY output the commit message.

Diff:
{diff}"""

        self.ai_thread = AIWorker(diff, model, custom_prompt=prompt)
        self.ai_thread.finished.connect(lambda msg: self.on_ai_success(msg, auto_commit))
        self.ai_thread.error.connect(self.on_ai_error)
        self.ai_thread.start()

    def explain_ai_message(self):
        success, diff = self.run_git(["diff", "--cached"])
        if not diff.strip():
            QMessageBox.warning(self, "No Staged Changes", "Stage files first to get an explanation.")
            return

        self.btn_ai_explain.setEnabled(False)
        self.btn_ai_explain.setText("⏳ Analyzing...")
        
        prompt = "Explain the following code changes simply and clearly. Point out any potential bugs or interesting logic changes.\n\nDiff:\n{diff}"
        model = self.combo_model.currentText() or "llama3"

        self.ai_thread = AIWorker(diff, model, custom_prompt=prompt)
        self.ai_thread.finished.connect(lambda res: self._show_ai_dialog("AI Code Explanation", res, self.btn_ai_explain, "🧠 Explain"))
        self.ai_thread.error.connect(self.on_ai_error)
        self.ai_thread.start()

    def analyze_risk_message(self):
        success, diff = self.run_git(["diff", "--cached"])
        if not diff.strip():
            QMessageBox.warning(self, "No Staged Changes", "Stage files first to analyze risk.")
            return

        self.btn_ai_risk.setEnabled(False)
        self.btn_ai_risk.setText("⏳ Scanning...")
        
        prompt = """Analyze the following git diff for potential risks:
1. Breaking changes or backward incompatibilities.
2. Hardcoded secrets, API keys, or credentials.
3. Unintended large scale deletions.
4. Performance bottlenecks or infinite loops.
Reply with '✅ Safe' if absolutely no risks are found. Otherwise, list the risks clearly.

Diff:
{diff}"""
        model = self.combo_model.currentText() or "llama3"

        self.ai_thread = AIWorker(diff, model, custom_prompt=prompt)
        self.ai_thread.finished.connect(lambda res: self._show_ai_dialog("AI Risk Analysis", res, self.btn_ai_risk, "⚠️ Risk"))
        self.ai_thread.error.connect(self.on_ai_error)
        self.ai_thread.start()

    def review_single_file(self):
        selected = self.get_checked_items(self.list_unstaged)
        if not selected:
            QMessageBox.warning(self, "No Files", "Select unstaged files to review.")
            return

        success, diff = self.run_git(["diff", "--"] + selected)
        if not diff.strip():
            QMessageBox.warning(self, "No Changes", "No visible diff for selected files.")
            return

        self.btn_ai_review.setEnabled(False)
        self.btn_ai_review.setText("⏳ Reviewing...")

        prompt = """Perform a senior-level code review on the following git diff.
Focus ONLY on:
1. Logic bugs or edge cases.
2. Performance optimizations.
3. Code readability/maintainability issues.
Do not comment on trivial styling. Keep it structured and constructive.

Diff:
{diff}"""
        model = self.combo_model.currentText() or "llama3"

        self.ai_thread = AIWorker(diff, model, custom_prompt=prompt)
        self.ai_thread.finished.connect(lambda res: self._show_ai_dialog("AI Code Review", res, self.btn_ai_review, "🔎 Review"))
        self.ai_thread.error.connect(self.on_ai_error)
        self.ai_thread.start()

    def suggest_commit_splits(self):
        success, diff = self.run_git(["diff"])
        if not diff.strip():
            QMessageBox.warning(self, "No Unstaged Changes", "There are no unstaged changes to analyze.")
            return

        self.btn_ai_split.setEnabled(False)
        self.btn_ai_split.setText("⏳ Analyzing Files...")
        
        prompt = """Look at the following unstaged git diff. Suggest how to split these files into logical, separate commits. 
Format your output cleanly as:
- Commit 1 (Type): [file1, file2] - [Reason]
- Commit 2 (Type): [file3] - [Reason]

Diff:
{diff}"""
        model = self.combo_model.currentText() or "llama3"

        self.ai_thread = AIWorker(diff, model, custom_prompt=prompt)
        self.ai_thread.finished.connect(lambda res: self._show_ai_dialog("AI Split Suggestions", res, self.btn_ai_split, "🤖 AI: Suggest Splits"))
        self.ai_thread.error.connect(self.on_ai_error)
        self.ai_thread.start()

    def explain_conflicts(self):
        """Finds unmerged files and asks AI how to resolve the conflicts."""
        success, out = self.run_git(["diff", "--diff-filter=U"])
        if not success or not out.strip():
            QMessageBox.information(self, "No Conflicts", "No merge conflicts detected in the working tree.")
            return

        self.btn_ai_conflicts.setEnabled(False)
        self.btn_ai_conflicts.setText("⏳ Analyzing Conflicts...")
        
        prompt = """Analyze the following git merge conflicts.
Explain exactly what the two conflicting versions are trying to do, and suggest a clear strategy on how to resolve the <<<<<<<, =======, and >>>>>>> blocks safely.

Conflicts:
{diff}"""
        model = self.combo_model.currentText() or "llama3"

        self.ai_thread = AIWorker(out, model, custom_prompt=prompt)
        self.ai_thread.finished.connect(lambda res: self._show_ai_dialog("AI Conflict Resolution", res, self.btn_ai_conflicts, "🔀 Resolve Conflicts"))
        self.ai_thread.error.connect(self.on_ai_error)
        self.ai_thread.start()

    def _show_ai_dialog(self, title, content, button_to_reset, reset_text):
        button_to_reset.setEnabled(True)
        button_to_reset.setText(reset_text)
        
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(800, 600)
        layout = QVBoxLayout(dialog)
        
        text_box = QTextEdit()
        text_box.setReadOnly(True)
        text_box.setPlainText(content)
        text_box.setStyleSheet("font-size: 14px; padding: 10px; font-family: Consolas, monospace;")
        layout.addWidget(text_box)
        dialog.exec()

    def on_ai_success(self, message, auto_commit):
        issue_no = self.entry_issue.text().strip()
        if issue_no:
            if not issue_no.startswith("#"):
                issue_no = f"#{issue_no}"
            message = f"{message} ({issue_no})"

        self.entry_commit.setText(message)
        self.btn_ai_gen.setEnabled(True)
        self.btn_ai_gen.setText("🤖 Generate AI Message")
        self.log("AI successfully generated commit message.")

        if auto_commit:
            self.start_timed_commit()

    def on_ai_error(self, err_msg):
        self.btn_ai_gen.setEnabled(True)
        self.btn_ai_gen.setText("🤖 Generate AI Message")
        self.btn_ai_explain.setEnabled(True)
        self.btn_ai_explain.setText("🧠 Explain")
        self.btn_ai_risk.setEnabled(True)
        self.btn_ai_risk.setText("⚠️ Risk")
        self.btn_ai_split.setEnabled(True)
        self.btn_ai_split.setText("🤖 AI: Suggest Splits")
        if hasattr(self, 'btn_ai_review'):
            self.btn_ai_review.setEnabled(True)
            self.btn_ai_review.setText("🔎 Review")
        if hasattr(self, 'btn_ai_conflicts'):
            self.btn_ai_conflicts.setEnabled(True)
            self.btn_ai_conflicts.setText("🔀 Resolve Conflicts")
            
        self.log(f"AI Error: {err_msg}")
        QMessageBox.critical(self, "AI Error", err_msg)

    # ==========================================
    # 💾 Action & Commit Methods
    # ==========================================
    def save_diff(self):
        diff_text = self.text_diff.toPlainText()
        if not diff_text.strip():
            QMessageBox.warning(self, "Empty Diff", "There is no diff to save.")
            return

        filepath, _ = QFileDialog.getSaveFileName(self, "Save Diff", "diff.txt", "Text Files (*.txt)")
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(diff_text)
            self.log(f"Saved diff to {filepath}")

    def execute_pre_commit_hook(self):
        cmd = self.entry_pre_commit.text().strip()
        if not cmd:
            return True 
            
        self.log(f"⏳ Running pre-commit check: {cmd}")
        try:
            res = subprocess.run(cmd, shell=True, cwd=self.repo_path, capture_output=True, text=True)
            if res.returncode != 0:
                self.log(f"❌ Pre-commit failed: {res.stderr or res.stdout}")
                QMessageBox.critical(self, "Pre-commit Validation Failed", f"Command '{cmd}' failed to execute successfully.\n\nOutput:\n{res.stderr or res.stdout}")
                return False
            self.log("✅ Pre-commit check passed successfully!")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Pre-commit Execution Error", str(e))
            return False

    def commit_files(self):
        msg = self.entry_commit.toPlainText().strip()
        if self.list_staged.count() == 0:
            QMessageBox.warning(self, "Nothing Staged", "There are no staged files to commit.")
            return
        if not msg:
            QMessageBox.warning(self, "No Message", "Please provide a commit message.")
            return
            
        if not self.execute_pre_commit_hook():
            return

        commit_success, commit_out = self.run_git(["commit", "-m", msg])
        if commit_success:
            self.log(f"✅ Successfully committed: '{msg}'")
            self.entry_commit.clear()
            self.text_diff.clear()
            self.refresh_status()
        else:
            self.log(f"Commit failed: {commit_out}")

    def auto_commit_flow(self):
        files = self.get_checked_items(self.list_unstaged)
        if not files:
            QMessageBox.warning(self, "No Files", "Please select unstaged files to auto-commit.")
            return
            
        delay = self.spin_delay.value()
        delay_msg = f" wait {delay} seconds," if delay > 0 else ""
        
        reply = QMessageBox.question(
            self, "Smart Auto-Commit", 
            f"This will Stage {len(files)} files, generate an AI message,{delay_msg} run pre-commit hooks, and Commit. Proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.log("Starting smart auto-commit flow...")
            self.run_git(["add", "--"] + files)
            self.refresh_status()
            self.generate_ai_message(auto_commit=True)

    # ==========================================
    # ⏲️ Timer Core Methods
    # ==========================================
    def start_timed_commit(self):
        if self.list_staged.count() == 0:
            QMessageBox.warning(self, "Nothing Staged", "There are no staged files to commit.")
            return
        if not self.entry_commit.toPlainText().strip():
            QMessageBox.warning(self, "No Message", "Please provide a commit message before starting the timer.")
            return

        delay = self.spin_delay.value()
        if delay <= 0:
            self.commit_files()
        else:
            self.time_left = delay
            self.lbl_timer_status.setText(f"⏳ Committing automatically in {self.time_left} seconds...")
            self.btn_cancel_timer.setEnabled(True)
            self.btn_commit.setEnabled(False)
            self.btn_timed_commit.setEnabled(False)
            self.btn_auto_commit.setEnabled(False)
            self.commit_timer.start(1000)
            self.log(f"Timer started. Committing in {delay} seconds.")

    def timer_tick(self):
        self.time_left -= 1
        if self.time_left <= 0:
            self.cancel_timer(log_cancel=False) 
            self.commit_files()
        else:
            self.lbl_timer_status.setText(f"⏳ Committing automatically in {self.time_left} seconds...")

    def cancel_timer(self, log_cancel=True):
        self.commit_timer.stop()
        self.lbl_timer_status.setText("")
        self.btn_cancel_timer.setEnabled(False)
        self.btn_commit.setEnabled(True)
        self.btn_timed_commit.setEnabled(True)
        self.btn_auto_commit.setEnabled(True)
        if log_cancel:
            self.log("🛑 Commit timer cancelled by user.")

    def undo_last_commit(self):
        reply = QMessageBox.question(
            self, "Undo Commit", 
            "Undo the last commit? (Files will remain safely in your working directory uncommitted).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            success, out = self.run_git(["reset", "HEAD~1"])
            if success:
                self.log("✅ Undid last commit successfully.")
                self.refresh_status()
            else:
                self.log(f"Failed to undo commit: {out}")
                QMessageBox.critical(self, "Git Error", f"Could not undo commit:\n{out}")


if __name__ == "__main__":
    def _global_exception_hook(exc_type, exc_value, exc_tb):
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        _console_log(tb_text, level="CRITICAL", source="EXCEPTION")
        _append_debug_file(tb_text, level="CRITICAL", source="EXCEPTION")

    def _thread_exception_hook(args):
        tb_text = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        _console_log(f"Thread exception in {args.thread.name}:\n{tb_text}", level="CRITICAL", source="THREAD")
        _append_debug_file(f"Thread exception in {args.thread.name}:\n{tb_text}", level="CRITICAL", source="THREAD")

    def _unraisable_hook(unraisable):
        tb_text = ""
        if unraisable.exc_traceback is not None:
            tb_text = "".join(traceback.format_tb(unraisable.exc_traceback))
        msg = (
            f"Unraisable exception: {unraisable.exc_type.__name__}: {unraisable.exc_value}\n"
            f"Object: {repr(unraisable.object)}\n"
            f"Traceback:\n{tb_text}"
        )
        _console_log(msg, level="CRITICAL", source="UNRAISABLE")
        _append_debug_file(msg, level="CRITICAL", source="UNRAISABLE")

    sys.excepthook = _global_exception_hook
    threading.excepthook = _thread_exception_hook
    sys.unraisablehook = _unraisable_hook
    qInstallMessageHandler(_qt_message_handler)

    _console_log("Application boot started")
    app = QApplication(sys.argv)
    app.setStyle("Fusion") 
    window = AIGitAssistant()
    window.show()
    _console_log("Application event loop starting")
    sys.exit(app.exec())