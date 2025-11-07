import os
import sys
import socket
import threading
import uuid
from PyQt6 import QtWidgets, QtGui, QtCore
from flask import Flask, request, redirect, url_for, flash, render_template_string
from werkzeug.utils import secure_filename

# --- Default Server Config ---
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5000  # default, can be changed in GUI

# --- Default Upload Folder ---
if os.name == 'nt':  # Windows
    downloads_path = os.path.join(os.environ['USERPROFILE'], 'Downloads')
    UPLOAD_FOLDER = os.path.join(downloads_path, "localUploads")
else:
    UPLOAD_FOLDER = os.path.join(os.getcwd(), "web_uploads")

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- Flask App ---
app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# HTML Template
HTML_TEMPLATE = """ 
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Upload Files</title>
<style>
body { font-family: Arial; background:#f4f7f6; display:flex; justify-content:center; align-items:center; min-height:100vh; }
.container { background:#fff; padding:30px 40px; border-radius:12px; box-shadow:0 8px 16px rgba(0,0,0,0.1); max-width:500px; }
h1 { text-align:center; margin-bottom:25px; color:#333; }
form { display:flex; flex-direction:column; }
.file-input-wrapper { position:relative; background:#f9f9f9; border:2px dashed #ddd; border-radius:8px; padding:30px; text-align:center; cursor:pointer; }
.file-input-wrapper:hover { border-color:#007bff; background:#fdfdfd; }
input[type="file"] { position:absolute; left:0; top:0; width:100%; height:100%; opacity:0; cursor:pointer; }
.file-input-label { color:#555; font-weight:500; }
#file-name { margin-top:15px; font-style:italic; color:#777; }
.submit-btn { background:#007bff; color:#fff; padding:14px 20px; margin-top:25px; border:none; border-radius:8px; cursor:pointer; font-size:16px; font-weight:600; }
.submit-btn:hover { background:#0056b3; }
.flash { padding:15px; margin-bottom:20px; border-radius:8px; text-align:center; font-weight:500; }
.flash.success { background:#d4edda; color:#155724; border:1px solid #c3e6cb; }
.flash.error { background:#f8d7da; color:#721c24; border:1px solid #f5c6cb; }
</style>
</head>
<body>
<div class="container">
<h1>Upload Files to Server</h1>
{% with messages = get_flashed_messages(with_categories=true) %}
{% if messages %}{% for category, message in messages %}
<div class="flash {{ category }}">{{ message }}</div>{% endfor %}{% endif %}
{% endwith %}
<form method="post" action="/upload" enctype="multipart/form-data">
<div class="file-input-wrapper">
<span class="file-input-label">Drag & drop files or click to select</span>
<input type="file" name="file" id="fileInput" required multiple>
<div id="file-name">No files chosen</div>
</div>
<input type="submit" value="Upload" class="submit-btn">
</form>
</div>
<script>
const fileInput = document.getElementById('fileInput');
const fileNameDisplay = document.getElementById('file-name');
fileInput.addEventListener('change', function() {
    if(fileInput.files.length>1){ fileNameDisplay.textContent=fileInput.files.length+' files chosen'; }
    else if(fileInput.files.length===1){ fileNameDisplay.textContent=fileInput.files[0].name; }
    else { fileNameDisplay.textContent='No files chosen'; }
});
</script>
</body>
</html>
"""

# --- Flask routes ---
def allowed_file(filename):
    return True  # allow all files

def get_lan_ip():
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except:
        return "127.0.0.1"
    finally:
        if s: s.close()

@app.route('/', methods=['GET'])
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/upload', methods=['POST'])
def upload_file():
    files = request.files.getlist('file')
    if not files or files[0].filename == '':
        flash('No files selected.', 'error')
        return redirect(url_for('index'))

    uploaded_files = []
    for file in files:
        if file:
            filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            uploaded_files.append(filename)

    if uploaded_files:
        flash(f"Uploaded {len(uploaded_files)} file(s): {', '.join(uploaded_files)}", 'success')
    return redirect(url_for('index'))

# --- PyQt6 GUI ---
class FileServerGUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Flask File Upload Server")
        self.setGeometry(100, 100, 650, 450)
        self.server_thread = None
        self.setup_ui()

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout()

        # Folder selection
        folder_layout = QtWidgets.QHBoxLayout()
        self.folder_input = QtWidgets.QLineEdit()
        self.folder_input.setText(UPLOAD_FOLDER)
        folder_btn = QtWidgets.QPushButton("Select Upload Folder")
        folder_btn.clicked.connect(self.select_folder)
        folder_layout.addWidget(self.folder_input)
        folder_layout.addWidget(folder_btn)
        layout.addLayout(folder_layout)

        # Open folder button
        open_folder_btn = QtWidgets.QPushButton("Open Upload Folder")
        open_folder_btn.clicked.connect(self.open_upload_folder)
        layout.addWidget(open_folder_btn)

        # Port selection
        port_layout = QtWidgets.QHBoxLayout()
        self.port_input = QtWidgets.QLineEdit(str(SERVER_PORT))
        self.port_input.setValidator(QtGui.QIntValidator(1024, 65535))
        port_label = QtWidgets.QLabel("Port:")
        port_layout.addWidget(port_label)
        port_layout.addWidget(self.port_input)
        layout.addLayout(port_layout)

        # Server info labels
        self.ip_label = QtWidgets.QLabel(f"LAN IP: {get_lan_ip()}")
        self.port_label = QtWidgets.QLabel(f"Port: {SERVER_PORT}")
        self.url_label = QtWidgets.QLabel(f"URL: http://{get_lan_ip()}:{SERVER_PORT}")
        layout.addWidget(self.ip_label)
        layout.addWidget(self.port_label)
        layout.addWidget(self.url_label)

        # Start/Stop buttons
        btn_layout = QtWidgets.QHBoxLayout()
        self.start_btn = QtWidgets.QPushButton("Start Server")
        self.start_btn.clicked.connect(self.start_server)
        self.stop_btn = QtWidgets.QPushButton("Stop Server")
        self.stop_btn.clicked.connect(self.stop_server)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)

        # Logs
        self.log_output = QtWidgets.QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        self.setLayout(layout)

    def select_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Upload Folder")
        if folder:
            self.folder_input.setText(folder)
            app.config['UPLOAD_FOLDER'] = folder
            if not os.path.exists(folder):
                os.makedirs(folder)
            self.log_output.append(f"Upload folder set to: {folder}")

    def open_upload_folder(self):
        folder = self.folder_input.text()
        if os.path.exists(folder):
            if os.name == 'nt':
                os.startfile(folder)
            elif sys.platform == 'darwin':
                os.system(f'open "{folder}"')
            else:
                os.system(f'xdg-open "{folder}"')
            self.log_output.append(f"Opened folder: {folder}")
        else:
            self.log_output.append(f"Folder does not exist: {folder}")

    def start_server(self):
        if self.server_thread and self.server_thread.is_alive():
            self.log_output.append("Server is already running!")
            return

        global SERVER_PORT
        try:
            SERVER_PORT = int(self.port_input.text())
        except ValueError:
            self.log_output.append("Invalid port! Using default 5000.")
            SERVER_PORT = 5000

        self.ip_label.setText(f"LAN IP: {get_lan_ip()}")
        self.port_label.setText(f"Port: {SERVER_PORT}")
        self.url_label.setText(f"URL: http://{get_lan_ip()}:{SERVER_PORT}")

        self.server_thread = threading.Thread(target=self.run_flask)
        self.server_thread.daemon = True
        self.server_thread.start()
        self.log_output.append(f"Server started at http://{get_lan_ip()}:{SERVER_PORT}")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def stop_server(self):
        self.log_output.append("To stop the server, close the GUI or press CTRL+C in terminal.")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def run_flask(self):
        app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False, use_reloader=False)

# --- Main ---
if __name__ == '__main__':
    app_gui = QtWidgets.QApplication(sys.argv)
    gui = FileServerGUI()
    gui.show()
    sys.exit(app_gui.exec())
