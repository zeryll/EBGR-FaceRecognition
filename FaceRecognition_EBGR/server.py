"""
E-BGR Local Server - Cross-Platform (Windows & Raspberry Pi OS)
Admin  : akses penuh (dashboard, log, face preview)
User   : hanya check-in + logout
"""
from flask import Flask, jsonify, send_from_directory, request, session, redirect
import subprocess
import platform
import os
import base64
import functools

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
WEB_DIR       = os.path.join(os.path.dirname(BASE_DIR), 'Web_Dashboard_EBGR')
DATA_TAMU_DIR = os.path.join(BASE_DIR, 'data', 'tamu')

IS_WINDOWS = platform.system() == 'Windows'

# Path Python virtual environment (berbeda antara Windows dan Linux/RPi)
if IS_WINDOWS:
    VENV_PYTHON = os.path.join(os.path.dirname(BASE_DIR), 'Face recognition', 'venv', 'Scripts', 'python.exe')
else:
    # Di Raspberry Pi, venv ada di dalam folder proyek
    VENV_PYTHON = os.path.join(BASE_DIR, 'venv', 'bin', 'python3')

app = Flask(__name__, static_folder=WEB_DIR)
app.secret_key = 'ebgr_pln_updl_bogor_2025_xK9z'

# Akun: {username: (password, role)}
ACCOUNTS = {
    'admin':  ('ebgr2025', 'admin'),
    'denzel': ('ta2025',   'user'),
}

running_processes = {}

# ==================== HELPERS ====================

def nocache(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma']        = 'no-cache'
    response.headers['Expires']       = '0'
    return response

def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({'status': 'unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({'status': 'unauthorized'}), 401
        if session.get('role') != 'admin':
            return jsonify({'status': 'forbidden', 'message': 'Akses ditolak. Hanya Admin.'}), 403
        return f(*args, **kwargs)
    return decorated

# ==================== PAGE ROUTING ====================

@app.route('/')
def root():
    if session.get('logged_in'):
        return nocache(send_from_directory(WEB_DIR, 'index.html'))
    return nocache(send_from_directory(WEB_DIR, 'login.html'))

@app.route('/login')
def login_page():
    if session.get('logged_in'):
        return redirect('/')
    return nocache(send_from_directory(WEB_DIR, 'login.html'))

@app.route('/<path:filename>')
def serve_static(filename):
    # Blokir akses langsung ke index.html jika belum login
    if filename in ('index.html',):
        if not session.get('logged_in'):
            return redirect('/')
    return send_from_directory(WEB_DIR, filename)

# ==================== AUTH API ====================

@app.route('/api/login', methods=['POST'])
def api_login():
    body = request.get_json() or {}
    username = body.get('username', '').strip().lower()
    password = body.get('password', '').strip()

    account = ACCOUNTS.get(username)
    if account and account[0] == password:
        session.clear()
        session['logged_in'] = True
        session['username']  = username
        session['role']      = account[1]
        return jsonify({'status': 'success', 'role': account[1], 'username': username})

    return jsonify({'status': 'error', 'message': 'Username atau password salah.'}), 401

@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return nocache(jsonify({'status': 'success'}))

@app.route('/api/auth-check', methods=['GET'])
def api_auth_check():
    if not session.get('logged_in'):
        return jsonify({'status': 'unauthorized'}), 401
    return jsonify({
        'status':    'ok',
        'username':  session.get('username'),
        'role':      session.get('role'),
        'is_admin':  (session.get('role') == 'admin'),
    })

# ==================== CAMERA (Login Required) ====================

def launch_script(script_name):
    """Jalankan script Python di terminal baru — cross-platform."""
    script_path = os.path.join(BASE_DIR, script_name)
    if IS_WINDOWS:
        proc = subprocess.Popen(
            [VENV_PYTHON, script_path],
            cwd=BASE_DIR,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
    else:
        # Raspberry Pi / Linux: buka di terminal grafis baru
        # Coba lxterminal (default RPi), xterm, atau gnome-terminal
        for terminal in ['lxterminal', 'xterm', 'gnome-terminal', 'konsole']:
            try:
                if terminal in ('lxterminal', 'xterm'):
                    proc = subprocess.Popen(
                        [terminal, '-e', f'{VENV_PYTHON} {script_path}'],
                        cwd=BASE_DIR
                    )
                elif terminal == 'gnome-terminal':
                    proc = subprocess.Popen(
                        ['gnome-terminal', '--', VENV_PYTHON, script_path],
                        cwd=BASE_DIR
                    )
                else:
                    proc = subprocess.Popen(
                        [terminal, '-e', f'{VENV_PYTHON} {script_path}'],
                        cwd=BASE_DIR
                    )
                return proc
            except FileNotFoundError:
                continue
        # Fallback: jalankan di background tanpa terminal
        proc = subprocess.Popen(
            [VENV_PYTHON, script_path],
            cwd=BASE_DIR
        )
    return proc

@app.route('/api/start-checkin', methods=['POST'])
@login_required
def start_checkin():
    if 'checkin' in running_processes and running_processes['checkin'].poll() is None:
        return jsonify({'status': 'warning', 'message': 'Program Check-In sudah berjalan!'}), 409
    try:
        proc = launch_script('app_checkin.py')
        running_processes['checkin'] = proc
        return jsonify({'status': 'success', 'message': 'Kamera Check-In berhasil dibuka!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/start-checkout', methods=['POST'])
@admin_required
def start_checkout():
    if 'checkout' in running_processes and running_processes['checkout'].poll() is None:
        return jsonify({'status': 'warning', 'message': 'Program Verifikasi sudah berjalan!'}), 409
    try:
        proc = launch_script('app_checkout.py')
        running_processes['checkout'] = proc
        return jsonify({'status': 'success', 'message': 'Kamera Verifikasi/Check-Out berhasil dibuka!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==================== DATA (Admin Only) ====================

@app.route('/api/logs', methods=['GET'])
@admin_required
def get_logs():
    try:
        from modules.database import get_connection
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT l.id_log, l.id_tamu, t.nama, l.tipe_event,
                   l.status_verifikasi, l.timestamp, t.status as status_tamu
            FROM log_verifikasi l
            LEFT JOIN tamu t ON l.id_tamu = t.id_tamu
            ORDER BY l.id_log DESC
        ''')
        rows = cursor.fetchall()
        cursor.execute("SELECT status, COUNT(*) as total FROM tamu GROUP BY status")
        stats = {r['status']: r['total'] for r in cursor.fetchall()}
        conn.close()

        logs = []
        for r in rows:
            id_t     = r['id_tamu']
            foto_dir = os.path.join(DATA_TAMU_DIR, str(id_t))
            logs.append({
                'id_log':            r['id_log'],
                'id_tamu':           id_t,
                'nama':              r['nama'] or 'Tamu Terdaftar',
                'event':             r['tipe_event'],
                'status_verifikasi': r['status_verifikasi'],
                'timestamp':         r['timestamp'],
                'status_tamu':       r['status_tamu'],
                'has_photos':        os.path.isdir(foto_dir) and bool(os.listdir(foto_dir)),
            })
        return jsonify({'status': 'success', 'logs': logs, 'stats': stats})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/tamu-photos/<id_tamu>', methods=['GET'])
@admin_required
def get_tamu_photos(id_tamu):
    try:
        foto_dir = os.path.join(DATA_TAMU_DIR, str(id_tamu))
        if not os.path.isdir(foto_dir):
            return jsonify({'status': 'error', 'message': 'Folder foto tidak ada.'}), 404
        photos = []
        for fn in sorted(os.listdir(foto_dir)):
            if fn.lower().endswith(('.jpg', '.jpeg', '.png')):
                with open(os.path.join(foto_dir, fn), 'rb') as f:
                    enc = base64.b64encode(f.read()).decode()
                    photos.append({'filename': fn, 'data': f'data:image/jpeg;base64,{enc}'})
        return jsonify({'status': 'success', 'photos': photos})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==================== MAIN ====================

if __name__ == '__main__':
    print("=" * 55)
    print("  E-BGR SERVER  |  http://localhost:5000")
    print("  Admin  →  admin  / ebgr2025")
    print("  User   →  denzel / ta2025")
    print("=" * 55)
    app.run(host='0.0.0.0', port=5000, debug=False)
