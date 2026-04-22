import sys
import sqlite3
import re
import multiprocessing
import time
import os
import json
import socket
import io
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, send_from_directory
from werkzeug.utils import secure_filename

# PyQt6 Imports
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTextEdit, QTabWidget, QTableWidget, QTableWidgetItem,
                             QHeaderView, QMessageBox, QFileDialog, QSystemTrayIcon,
                             QMenu, QFrame, QSplitter)
from PyQt6.QtCore import QTimer, Qt, QSize
from PyQt6.QtGui import QIcon, QAction, QPixmap, QImage, QColor

# Try importing qrcode for Mobile connect feature
try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False
###

# -------------------------------------------------------------------------
# Part 1: Shared Utilities & Config
# -------------------------------------------------------------------------

DB_NAME = "chat.db"
UPLOAD_FOLDER = "uploads"
CONFIG_FILE = "app_config.json"

def get_local_ip():
    """Detects the machine's local LAN IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't actually connect, just calculates the route
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def load_config():
    global UPLOAD_FOLDER
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                UPLOAD_FOLDER = config.get('upload_folder', 'uploads')
        except:
            pass

def save_config():
    config = {'upload_folder': UPLOAD_FOLDER}
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            message TEXT,
            has_link INTEGER,
            timestamp TEXT,
            filename TEXT
        )
    """)
    # Migration check
    try:
        cursor.execute("SELECT filename FROM messages LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE messages ADD COLUMN filename TEXT")
    conn.commit()
    conn.close()

class QueueWriter:
    def __init__(self, queue, original_stream):
        self.queue = queue
        self.original_stream = original_stream

    def write(self, msg):
        if msg.strip():
            self.queue.put(msg)
        if self.original_stream:
            self.original_stream.write(msg)

    def flush(self):
        if self.original_stream:
            self.original_stream.flush()

# -------------------------------------------------------------------------
# Part 2: Flask Server Process
# -------------------------------------------------------------------------

def make_links_clickable(text):
    url_pattern = r'(https?://\S+|www\.\S+)'
    def replace_url(match):
        url = match.group(0)
        href = url if url.startswith('http') else f'https://{url}'
        return f'<a href="{href}" target="_blank" style="color: #039be5;">{url}</a>'
    return re.sub(url_pattern, replace_url, text)

def run_flask_process(port, log_queue):
    sys.stdout = QueueWriter(log_queue, sys.stdout)
    sys.stderr = QueueWriter(log_queue, sys.stderr)

    app = Flask(__name__)
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    
    init_db()

    # --- HTML Template (Updated for Mobile Responsiveness) ---
    HTML_TEMPLATE = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>LAN Chat</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
        <style>
            :root { --primary: #007bff; --bg: #f5f7fa; --bubble-sent: #007bff; --bubble-rec: #ffffff; }
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); height: 100vh; display: flex; flex-direction: column; }
            .header { background: #fff; padding: 15px; border-bottom: 1px solid #ddd; font-weight: 600; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
            #chat { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 10px; }
            .message { max-width: 85%; align-self: flex-start; animation: fadeIn 0.3s; }
            .message.sent { align-self: flex-end; }
            .message.admin { align-self: center; max-width: 90%; }
            .bubble { padding: 10px 14px; border-radius: 12px; font-size: 15px; line-height: 1.4; box-shadow: 0 1px 2px rgba(0,0,0,0.1); position: relative; }
            
            .message:not(.sent):not(.admin) .bubble { background: var(--bubble-rec); color: #333; border-bottom-left-radius: 2px; }
            .message.sent .bubble { background: var(--primary); color: white; border-bottom-right-radius: 2px; }
            .message.sent .bubble a { color: #e1f5fe !important; }
            
            .message.admin .bubble { background: #ff9800; color: white; border-radius: 20px; font-weight: 500; font-size: 14px; text-align: center; box-shadow: 0 2px 5px rgba(255,152,0,0.3); }
            .meta { font-size: 10px; margin-top: 4px; opacity: 0.7; text-align: right; }
            
            .input-area { background: #fff; padding: 10px; display: flex; gap: 10px; border-top: 1px solid #eee; }
            #message { flex: 1; padding: 12px; border: 1px solid #ddd; border-radius: 20px; outline: none; transition: border 0.2s; }
            #message:focus { border-color: var(--primary); }
            .btn { border: none; padding: 10px 20px; border-radius: 20px; font-weight: 600; cursor: pointer; transition: opacity 0.2s; }
            .btn-send { background: var(--primary); color: white; }
            .btn-file { background: #e9ecef; color: #555; width: 45px; display: flex; align-items: center; justify-content: center; font-size: 1.2rem; }
            .media-preview { max-width: 100%; border-radius: 8px; margin-top: 5px; display: block; }
            @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        </style>
    </head>
    <body>
        <div class="header">
            <span>LAN Messenger</span>
            <span style="font-size: 0.8em; color: #888; font-weight: normal;">Online</span>
        </div>
        <div id="chat"></div>
        <div class="input-area">
            <input type="file" id="fileInput" multiple style="display: none;">
            <button class="btn btn-file" onclick="document.getElementById('fileInput').click()">📎</button>
            <input id="message" placeholder="Type a message..." autocomplete="off">
            <button class="btn btn-send" onclick="sendMessage()">Send</button>
        </div>

        <script>
            let userId = localStorage.getItem('userId') || 'user_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('userId', userId);
            let lastMsgCount = 0;

            document.getElementById('fileInput').onchange = (e) => {
                if(e.target.files.length) Array.from(e.target.files).forEach(uploadFile);
            };

            document.getElementById('message').onkeypress = (e) => {
                if(e.key === 'Enter') sendMessage();
            };

            function uploadFile(file) {
                let fd = new FormData();
                fd.append('file', file);
                fd.append('user_id', userId);
                fetch('/upload', { method: 'POST', body: fd }).then(r => r.json()).then(d => {
                    if(d.status === 'ok') { 
                        document.getElementById('fileInput').value = '';
                        fetchMessages(); 
                    }
                });
            }

            function sendMessage() {
                let msg = document.getElementById('message').value.trim();
                if(!msg) return;
                fetch('/send', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({user_id: userId, message: msg})
                }).then(() => {
                    document.getElementById('message').value = '';
                    fetchMessages();
                });
            }

            function fetchMessages() {
                fetch('/messages')
                    .then(res => res.json())
                    .then(data => {
                        if (data.length === lastMsgCount) return;
                        
                        let chat = document.getElementById('chat');
                        let isScrolledBottom = chat.scrollHeight - chat.scrollTop <= chat.clientHeight + 100;
                        
                        chat.innerHTML = data.map(msg => {
                            let isMe = msg.user_id === userId;
                            let isAdmin = msg.user_id === 'ADMIN';
                            let cls = isAdmin ? 'message admin' : (isMe ? 'message sent' : 'message');
                            let content = `<div class="msg-content">${msg.message_html}</div>`;
                            
                            if(msg.filename) {
                                let ext = msg.filename.split('.').pop().toLowerCase();
                                let link = `/uploads/${msg.filename}`;
                                if(['jpg','jpeg','png','gif'].includes(ext)) 
                                    content += `<a href="${link}" target="_blank"><img src="${link}" class="media-preview"></a>`;
                                else if(['mp4','webm'].includes(ext))
                                    content += `<video controls src="${link}" class="media-preview"></video>`;
                                else 
                                    content += `<div style="margin-top:5px; font-size:0.9em;">📄 <a href="${link}" target="_blank">Download File</a></div>`;
                            }
                            
                            return `<div class="${cls}">
                                        <div class="bubble">
                                            ${content}
                                            <div class="meta">${new Date(msg.timestamp).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</div>
                                        </div>
                                    </div>`;
                        }).join('');

                        lastMsgCount = data.length;
                        if(isScrolledBottom || data.length === 1) chat.scrollTop = chat.scrollHeight;
                    });
            }
            setInterval(fetchMessages, 1000);
            fetchMessages();
        </script>
    </body>
    </html>
    """

    @app.route("/")
    def index(): return render_template_string(HTML_TEMPLATE)

    @app.route("/uploads/<filename>")
    def uploaded_file(filename): return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    @app.route("/upload", methods=["POST"])
    def upload():
        f = request.files.get('file')
        uid = request.form.get('user_id', 'anon')
        if f and f.filename:
            fname = f"{int(time.time())}_{secure_filename(f.filename)}"
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
            save_msg(uid, f"Shared file: {f.filename}", fname)
            print(f"File uploaded: {fname}")
            return jsonify({"status": "ok"})
        return jsonify({"status": "err"})

    @app.route("/send", methods=["POST"])
    def send():
        d = request.json
        save_msg(d.get("user_id"), d.get("message"), None)
        print(f"Msg: {d.get('message')}")
        return jsonify({"status": "ok"})

    @app.route("/messages")
    def get_msgs():
        conn = sqlite3.connect(DB_NAME)
        rows = conn.execute("SELECT user_id, message, timestamp, filename FROM messages ORDER BY id ASC").fetchall()
        conn.close()
        return jsonify([
            {
                "user_id": r[0], 
                "message_html": make_links_clickable(r[1]), 
                "timestamp": r[2], 
                "filename": r[3]
            } for r in rows
        ])

    def save_msg(uid, msg, fname):
        conn = sqlite3.connect(DB_NAME)
        conn.execute("INSERT INTO messages (user_id, message, has_link, timestamp, filename) VALUES (?, ?, ?, ?, ?)",
                     (uid, msg, 0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), fname))
        conn.commit()
        conn.close()

    app.run(host="0.0.0.0", port=port, use_reloader=False)

# -------------------------------------------------------------------------
# Part 3: PyQt6 Enhanced GUI
# -------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LAN Chat Server & Admin")
        self.resize(1000, 650)
        self.local_ip = get_local_ip()
        self.server_process = None
        self.log_queue = multiprocessing.Queue()

        self.setup_ui()
        self.setup_tray()
        
        # Timer for log updates
        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self.update_logs)
        self.log_timer.start(200)

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # --- Left Panel: Controls & Status ---
        left_panel = QFrame()
        left_panel.setFrameShape(QFrame.Shape.StyledPanel)
        left_panel.setFixedWidth(300)
        left_layout = QVBoxLayout(left_panel)

        # Status Section
        lbl_title = QLabel("Server Status")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #333;")
        left_layout.addWidget(lbl_title)

        self.lbl_status = QLabel("Stopped")
        self.lbl_status.setStyleSheet("color: red; font-weight: bold; font-size: 14px;")
        left_layout.addWidget(self.lbl_status)

        # IP and Port Config
        form_layout = QVBoxLayout()
        form_layout.addWidget(QLabel("Port:"))
        self.txt_port = QLineEdit("5000")
        form_layout.addWidget(self.txt_port)
        
        form_layout.addWidget(QLabel("Upload Path:"))
        path_layout = QHBoxLayout()
        self.txt_path = QLineEdit(UPLOAD_FOLDER)
        self.txt_path.setReadOnly(True)
        btn_browse = QPushButton("...")
        btn_browse.setFixedWidth(30)
        btn_browse.clicked.connect(self.browse_folder)
        path_layout.addWidget(self.txt_path)
        path_layout.addWidget(btn_browse)
        form_layout.addLayout(path_layout)
        left_layout.addLayout(form_layout)

        # Action Buttons
        self.btn_start = QPushButton("Start Server")
        self.btn_start.setStyleSheet("background-color: #28a745; color: white; padding: 8px; font-weight: bold;")
        self.btn_start.clicked.connect(self.start_server)
        left_layout.addWidget(self.btn_start)

        self.btn_stop = QPushButton("Stop Server")
        self.btn_stop.setStyleSheet("background-color: #dc3545; color: white; padding: 8px; font-weight: bold;")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_server)
        left_layout.addWidget(self.btn_stop)

        # QR Code Section
        left_layout.addSpacing(20)
        left_layout.addWidget(QLabel("Mobile Connection QR:"))
        self.lbl_qr = QLabel()
        self.lbl_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_qr.setMinimumHeight(200)
        self.lbl_qr.setStyleSheet("background: #fff; border: 1px solid #ccc;")
        self.lbl_qr.setText("Start Server to\nGenerate QR")
        left_layout.addWidget(self.lbl_qr)

        self.lbl_url = QLabel("")
        self.lbl_url.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_url.setStyleSheet("color: #007bff; font-weight: bold;")
        left_layout.addWidget(self.lbl_url)

        left_layout.addStretch()
        main_layout.addWidget(left_panel)

        # --- Right Panel: Logs, DB, Admin Chat ---
        right_tabs = QTabWidget()
        
        # Tab 1: Console Logs
        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setStyleSheet("background: #1e1e1e; color: #00ff00; font-family: Consolas;")
        right_tabs.addTab(self.txt_logs, "Console Logs")

        # Tab 2: Admin Broadcast
        admin_widget = QWidget()
        admin_layout = QVBoxLayout(admin_widget)
        
        # Chat Preview (Simplified Table)
        self.tbl_msgs = QTableWidget()
        self.tbl_msgs.setColumnCount(3)
        self.tbl_msgs.setHorizontalHeaderLabels(["Time", "User", "Message"])
        self.tbl_msgs.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        admin_layout.addWidget(self.tbl_msgs)

        # Input
        input_layout = QHBoxLayout()
        self.txt_admin_msg = QLineEdit()
        self.txt_admin_msg.setPlaceholderText("Type a message to broadcast to all users...")
        self.txt_admin_msg.returnPressed.connect(self.send_admin_msg)
        
        btn_send = QPushButton("Broadcast")
        btn_send.clicked.connect(self.send_admin_msg)
        
        btn_refresh = QPushButton("Refresh List")
        btn_refresh.clicked.connect(self.refresh_db_view)

        input_layout.addWidget(self.txt_admin_msg)
        input_layout.addWidget(btn_send)
        input_layout.addWidget(btn_refresh)
        admin_layout.addLayout(input_layout)
        
        right_tabs.addTab(admin_widget, "Admin Chat & Monitor")
        
        main_layout.addWidget(right_tabs)

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
        
        menu = QMenu()
        action_show = QAction("Show", self)
        action_show.triggered.connect(self.show)
        action_quit = QAction("Quit", self)
        action_quit.triggered.connect(QApplication.instance().quit)
        
        menu.addAction(action_show)
        menu.addAction(action_quit)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def start_server(self):
        try:
            port = int(self.txt_port.text())
        except ValueError:
            return

        if self.server_process: return

        self.server_process = multiprocessing.Process(target=run_flask_process, args=(port, self.log_queue))
        self.server_process.start()
        
        self.btn_start.setEnabled(False)
        self.txt_port.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.lbl_status.setText("Running")
        self.lbl_status.setStyleSheet("color: green; font-weight: bold; font-size: 14px;")
        
        url = f"http://{self.local_ip}:{port}"
        self.lbl_url.setText(url)
        self.generate_qr(url)
        self.log_msg(f"Server started at {url}")

    def stop_server(self):
        if self.server_process:
            self.server_process.terminate()
            self.server_process.join()
            self.server_process = None
            
        self.btn_start.setEnabled(True)
        self.txt_port.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText("Stopped")
        self.lbl_status.setStyleSheet("color: red; font-weight: bold; font-size: 14px;")
        self.lbl_qr.setText("Server Stopped")
        self.lbl_qr.setPixmap(QPixmap())
        self.log_msg("Server stopped.")

    def generate_qr(self, data):
        if not QR_AVAILABLE:
            self.lbl_qr.setText("Install 'qrcode' lib\nto see QR code")
            return

        qr = qrcode.QRCode(box_size=4, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')
        
        # Convert PIL image to QPixmap
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qimg = QImage.fromData(buffer.getvalue())
        pixmap = QPixmap.fromImage(qimg)
        
        self.lbl_qr.setPixmap(pixmap)

    def update_logs(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            if isinstance(msg, bytes): msg = msg.decode()
            self.txt_logs.append(msg.strip())

    def log_msg(self, text):
        self.txt_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {text}")

    def send_admin_msg(self):
        msg = self.txt_admin_msg.text().strip()
        if not msg: return
        
        # Direct DB Insert
        conn = sqlite3.connect(DB_NAME)
        conn.execute("INSERT INTO messages (user_id, message, has_link, timestamp) VALUES (?, ?, ?, ?)",
                     ("ADMIN", msg, 0, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        
        self.txt_admin_msg.clear()
        self.refresh_db_view()
        self.log_msg(f"Broadcast: {msg}")

    def refresh_db_view(self):
        try:
            conn = sqlite3.connect(DB_NAME)
            rows = conn.execute("SELECT timestamp, user_id, message FROM messages ORDER BY id DESC LIMIT 50").fetchall()
            conn.close()
            
            self.tbl_msgs.setRowCount(0)
            for i, row in enumerate(rows):
                self.tbl_msgs.insertRow(i)
                self.tbl_msgs.setItem(i, 0, QTableWidgetItem(row[0]))
                self.tbl_msgs.setItem(i, 1, QTableWidgetItem(row[1]))
                self.tbl_msgs.setItem(i, 2, QTableWidgetItem(row[2]))
        except:
            pass

    def browse_folder(self):
        global UPLOAD_FOLDER
        f = QFileDialog.getExistingDirectory(self, "Select Upload Folder", UPLOAD_FOLDER)
        if f:
            UPLOAD_FOLDER = f
            self.txt_path.setText(f)
            save_config()

    def closeEvent(self, event):
        # Minimize to tray instead of closing immediately if server is running?
        # For now, let's just kill server and close to be safe.
        self.stop_server()
        event.accept()

if __name__ == "__main__":
    multiprocessing.freeze_support()
    load_config()
    init_db()
    
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False) # For tray icon
    
    w = MainWindow()
    w.show()
    
    sys.exit(app.exec())