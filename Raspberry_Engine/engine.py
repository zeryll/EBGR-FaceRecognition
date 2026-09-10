"""
E-BGR Raspberry Pi Engine API
Mini Flask server yang berjalan terus di RPi.
Menerima perintah dari Laptop Backend dan menjalankan program kamera.

Jalankan: python3 engine.py
Port: 5001
"""
from flask import Flask, jsonify, request
import subprocess
import os
import sys

sys.path.append(os.path.dirname(__file__))
from engine_config import ENGINE_HOST, ENGINE_PORT

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(BASE_DIR, 'venv', 'bin', 'python3')

# Fallback: gunakan python3 sistem jika venv belum ada
if not os.path.isfile(VENV_PYTHON):
    VENV_PYTHON = sys.executable

app = Flask(__name__)
running_processes = {}  # { 'checkin': proc, 'checkout': proc }


def _launch(script_path: str, extra_args: list = None) -> subprocess.Popen:
    """Jalankan script Python dengan venv, pastikan DISPLAY tersedia untuk Tkinter GUI."""
    env = os.environ.copy()
    env.setdefault('DISPLAY', ':0')  # wajib untuk Tkinter di RPi

    cmd = [VENV_PYTHON, script_path] + (extra_args or [])
    proc = subprocess.Popen(cmd, cwd=BASE_DIR, env=env)
    return proc


# --- ENDPOINTS ---

@app.route('/engine/status', methods=['GET'])
def engine_status():
    """Cek status engine: proses mana yang sedang berjalan."""
    statuses = {}
    for name, proc in running_processes.items():
        statuses[name] = 'running' if proc.poll() is None else 'idle'
    return jsonify({'status': 'ok', 'processes': statuses})


@app.route('/engine/start-checkin', methods=['POST'])
def start_checkin():
    """
    Terima perintah check-in dari laptop.
    Body: { id_tamu: str, nama: str }
    """
    data    = request.get_json() or {}
    id_tamu = data.get('id_tamu', '').strip()
    nama    = data.get('nama', '').strip()

    if not id_tamu or not nama:
        return jsonify({'status': 'error', 'message': 'id_tamu dan nama wajib diisi'}), 400

    # Cek apakah check-in sudah berjalan
    proc = running_processes.get('checkin')
    if proc and proc.poll() is None:
        return jsonify({'status': 'warning', 'message': 'Program Check-In sudah berjalan!'}), 409

    try:
        script = os.path.join(BASE_DIR, 'app_checkin.py')
        p = _launch(script, extra_args=['--id', id_tamu, '--nama', nama])
        running_processes['checkin'] = p
        print(f"[ENGINE] Check-In dimulai: {nama} ({id_tamu}) | PID {p.pid}")
        return jsonify({'status': 'success', 'message': f'Kamera check-in dibuka untuk {nama}', 'pid': p.pid})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/engine/start-checkout', methods=['POST'])
def start_checkout():
    """Terima perintah verifikasi/check-out dari laptop."""
    proc = running_processes.get('checkout')
    if proc and proc.poll() is None:
        return jsonify({'status': 'warning', 'message': 'Program Verifikasi sudah berjalan!'}), 409

    try:
        script = os.path.join(BASE_DIR, 'app_checkout.py')
        p = _launch(script)
        running_processes['checkout'] = p
        print(f"[ENGINE] Check-Out dimulai | PID {p.pid}")
        return jsonify({'status': 'success', 'message': 'Kamera verifikasi dibuka', 'pid': p.pid})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# --- MAIN ---

if __name__ == '__main__':
    print("=" * 55)
    print(f"  E-BGR ENGINE  |  http://0.0.0.0:{ENGINE_PORT}")
    print(f"  Python: {VENV_PYTHON}")
    print("  Endpoints:")
    print("    GET  /engine/status")
    print("    POST /engine/start-checkin")
    print("    POST /engine/start-checkout")
    print("=" * 55)
    app.run(host=ENGINE_HOST, port=ENGINE_PORT, debug=False)
