"""
E-BGR Raspberry Pi Engine API v2 — Web Streaming Edition
=========================================================
Semua kontrol kamera dilakukan dari web browser laptop.
RPi hanya menjalankan:
  - MJPEG live stream webcam
  - Capture + face recognition saat diminta
  - Kirim hasil ke laptop backend

Tidak ada GUI Tkinter — RPi headless (tanpa monitor).

Jalankan: python3 engine.py
Port: 5001
"""
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import cv2
import numpy as np
import threading
import time
import base64
import json
import os
import sys

sys.path.append(os.path.dirname(__file__))
from engine_config import ENGINE_HOST, ENGINE_PORT
try:
    from engine_config import CAMERA_SOURCE
except ImportError:
    CAMERA_SOURCE = 0
try:
    from engine_config import BLUR_THRESHOLD
except ImportError:
    BLUR_THRESHOLD = 100.0  # nilai awal (kalibrasi webcam Xiaovv)

# Face recognition modules
from modules.vision import is_image_blurry
from modules.face_engine import detect_faces, get_embeddings, is_consistent, find_match
from modules.laptop_api import send_enrollment, send_verification_result, get_embeddings_from_laptop

# ─── Flask App ───────────────────────────────────────────────────

app = Flask(__name__)
CORS(app)  # Izinkan browser laptop mengakses RPi langsung (cross-origin)

# ─── Camera Manager ──────────────────────────────────────────────

class CameraManager:
    """Thread-safe webcam manager."""

    def __init__(self):
        self.cap = None
        self.lock = threading.Lock()
        self.latest_frame = None      # Frame BGR terbaru
        self.is_open = False

    def _try_open(self, src):
        """Membuka VideoCapture dengan setting optimal untuk Linux/Raspberry Pi."""
        cap = None
        if isinstance(src, int) and hasattr(cv2, 'CAP_V4L2'):
            cap = cv2.VideoCapture(src, cv2.CAP_V4L2)
        if not cap or not cap.isOpened():
            cap = cv2.VideoCapture(src)

        if cap and cap.isOpened():
            if isinstance(src, int):
                # Gunakan format MJPG langsung dari hardware webcam
                # Menurunkan beban USB Raspberry Pi hingga 80-90% dan mencegah USB drop
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            # Cek baca 1 frame untuk memastikan bukan node dummy/ISP
            ret, test_f = cap.read()
            if ret and test_f is not None:
                self.latest_frame = test_f.copy()
                return cap
            cap.release()
        return None

    def open(self, source=None):
        if source is None:
            source = CAMERA_SOURCE

        with self.lock:
            if self.cap and self.cap.isOpened():
                return True

            # Konversi string angka misal "0" ke integer
            if isinstance(source, str) and source.strip().isdigit():
                source = int(source.strip())

            cap = self._try_open(source)

            # Jika gagal dan source adalah angka, coba auto-probe index lain di RPi [0, 2, 4, 1]
            if not cap and isinstance(source, int):
                candidates = [i for i in [0, 2, 4, 1] if i != source]
                print(f"[ENGINE CAM] Index {source} gagal, mencoba auto-probe index: {candidates}...")
                for alt_idx in candidates:
                    cap = self._try_open(alt_idx)
                    if cap:
                        print(f"[ENGINE CAM] ✅ Kamera berhasil terdeteksi di index {alt_idx}!")
                        break

            if not cap or not cap.isOpened():
                self.cap = None
                self.is_open = False
                print(f"[ENGINE CAM] ❌ Gagal membuka kamera pada source: {source}")
                return False

            self.cap = cap
            self.is_open = True
            return True

    def close(self):
        with self.lock:
            if self.cap:
                self.cap.release()
                self.cap = None
            self.is_open = False
            self.latest_frame = None

    def read(self):
        """Baca frame terbaru dari kamera."""
        with self.lock:
            if not self.cap or not self.cap.isOpened():
                return False, None
            ret, frame = self.cap.read()
            if ret:
                self.latest_frame = frame.copy()
            return ret, frame

    def get_latest(self):
        """Ambil copy frame terakhir yang berhasil dibaca."""
        with self.lock:
            if self.latest_frame is not None:
                return True, self.latest_frame.copy()
            return False, None


camera = CameraManager()

# ─── Session State ───────────────────────────────────────────────

class SessionState:
    """Menyimpan state session check-in / check-out yang aktif."""

    def __init__(self):
        self.active = False
        self.mode = None          # 'checkin' | 'checkout'
        self.id_tamu = None
        self.nama = None
        self.captured_frames = []  # list of BGR numpy arrays
        self.embeddings = []       # list of 128-D numpy arrays
        self.capture_count = 0
        self.lock = threading.Lock()

    def start(self, mode, id_tamu=None, nama=None):
        with self.lock:
            self.active = True
            self.mode = mode
            self.id_tamu = id_tamu
            self.nama = nama
            self.captured_frames = []
            self.embeddings = []
            self.capture_count = 0

    def reset(self):
        with self.lock:
            self.active = False
            self.mode = None
            self.id_tamu = None
            self.nama = None
            self.captured_frames = []
            self.embeddings = []
            self.capture_count = 0

    def to_dict(self):
        with self.lock:
            return {
                'active': self.active,
                'mode': self.mode,
                'id_tamu': self.id_tamu,
                'nama': self.nama,
                'capture_count': self.capture_count,
            }


session = SessionState()

# ─── Background Frame Reader ────────────────────────────────────

def _frame_reader_loop():
    """Background thread: terus membaca frame agar buffer kamera tidak stale."""
    while True:
        if camera.is_open:
            camera.read()
        time.sleep(0.03)  # ~30 fps


reader_thread = threading.Thread(target=_frame_reader_loop, daemon=True)
reader_thread.start()

# ─── MJPEG Streaming ────────────────────────────────────────────

def _generate_mjpeg():
    """Generator yang menghasilkan frame JPEG secara terus-menerus."""
    while camera.is_open:
        ret, frame = camera.get_latest()
        if not ret:
            time.sleep(0.05)
            continue

        # Gambar kotak panduan wajah di tengah frame
        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2
        color = (0, 255, 100)  # Hijau

        cv2.rectangle(frame, (cx - 140, cy - 180), (cx + 140, cy + 140), color, 2)
        cv2.putText(frame, "Posisikan Wajah Di Sini",
                    (cx - 125, cy - 195),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1, cv2.LINE_AA)

        # Tampilkan info session
        if session.active:
            info = f"Mode: {'CHECK-IN' if session.mode == 'checkin' else 'CHECK-OUT'}"
            cv2.putText(frame, info, (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 255), 2, cv2.LINE_AA)
            if session.mode == 'checkin':
                cv2.putText(frame, f"Foto: {session.capture_count}/3", (10, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 100), 2, cv2.LINE_AA)

        # Encode ke JPEG
        _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        jpg_bytes = buf.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpg_bytes + b'\r\n')

        time.sleep(0.05)  # ~20 fps untuk menghemat bandwidth


# ═════════════════════════════════════════════════════════════════
#  API ENDPOINTS
# ═════════════════════════════════════════════════════════════════

@app.route('/engine/status', methods=['GET'])
def api_status():
    """Cek status engine + session."""
    return jsonify({
        'status': 'ok',
        'camera_open': camera.is_open,
        'session': session.to_dict(),
    })


@app.route('/engine/stream', methods=['GET'])
def api_stream():
    """MJPEG live stream dari webcam RPi. Tampilkan di browser: <img src="...">"""
    if not camera.is_open:
        return jsonify({'status': 'error', 'message': 'Kamera belum dibuka. Mulai session dulu.'}), 503

    return Response(
        _generate_mjpeg(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@app.route('/engine/start-session', methods=['POST'])
def api_start_session():
    """
    Mulai session kamera baru.
    Body: { mode: 'checkin'|'checkout', id_tamu: str (opt), nama: str (opt) }
    """
    data = request.get_json() or {}
    mode = data.get('mode', '').strip()

    if mode not in ('checkin', 'checkout'):
        return jsonify({'status': 'error', 'message': 'mode harus "checkin" atau "checkout"'}), 400

    if session.active:
        print("[ENGINE] Menghentikan session aktif sebelumnya secara otomatis...")
        session.reset()
        camera.close()
        time.sleep(0.1)

    # Buka kamera (menggunakan konfigurasi CAMERA_SOURCE)
    if not camera.open(CAMERA_SOURCE):
        return jsonify({'status': 'error', 'message': f'Gagal membuka webcam (source: {CAMERA_SOURCE})! Pastikan terhubung.'}), 500

    # Mulai session
    id_tamu = data.get('id_tamu', '').strip() if mode == 'checkin' else None
    nama = data.get('nama', '').strip() if mode == 'checkin' else None
    session.start(mode, id_tamu=id_tamu, nama=nama)

    print(f"[ENGINE] Session dimulai: mode={mode}, id={id_tamu}, nama={nama}")
    return jsonify({
        'status': 'success',
        'message': f'Kamera dibuka — mode {mode}',
        'session': session.to_dict(),
    })


@app.route('/engine/stop-session', methods=['POST'])
def api_stop_session():
    """Tutup kamera dan reset session."""
    session.reset()
    camera.close()
    print("[ENGINE] Session dihentikan, kamera ditutup.")
    return jsonify({'status': 'success', 'message': 'Session dihentikan.'})


@app.route('/engine/capture', methods=['POST'])
def api_capture():
    """
    Tangkap 1 frame dari kamera, validasi, dan proses.
    - Mode checkin: simpan foto + embedding, kirim ke laptop setelah foto ke-3
    - Mode checkout: cocokkan wajah, kirim hasil
    """
    if not session.active:
        return jsonify({'status': 'error', 'message': 'Tidak ada session aktif.'}), 400

    if not camera.is_open:
        return jsonify({'status': 'error', 'message': 'Kamera tidak terbuka.'}), 500

    # Ambil frame terbaru
    ret, frame = camera.get_latest()
    if not ret or frame is None:
        return jsonify({'status': 'error', 'message': 'Gagal membaca frame dari kamera.'}), 500

    # ─── Validasi: Blur ───
    is_blur, var = is_image_blurry(frame, BLUR_THRESHOLD)
    if is_blur:
        return jsonify({
            'status': 'fail',
            'reason': 'blur',
            'message': f'Gambar terlalu buram (var={var:.1f}, ambang={BLUR_THRESHOLD:g}). Pastikan pencahayaan cukup.',
            'session': session.to_dict(),
        })

    # ─── Validasi: Deteksi Wajah ───
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    boxes = detect_faces(rgb)

    if len(boxes) == 0:
        return jsonify({
            'status': 'fail',
            'reason': 'no_face',
            'message': 'Wajah tidak terdeteksi. Posisikan wajah di dalam kotak.',
            'session': session.to_dict(),
        })

    if len(boxes) > 1:
        return jsonify({
            'status': 'fail',
            'reason': 'multi_face',
            'message': f'Terdeteksi {len(boxes)} wajah. Hanya boleh 1 orang.',
            'session': session.to_dict(),
        })

    # ─── Wajah valid — proses sesuai mode ───

    if session.mode == 'checkin':
        return _handle_checkin_capture(frame, rgb, boxes)
    else:
        return _handle_checkout_capture(frame, rgb, boxes)


# ═════════════════════════════════════════════════════════════════
#  CHECK-IN LOGIC
# ═════════════════════════════════════════════════════════════════

def _handle_checkin_capture(frame, rgb, boxes):
    """Proses capture untuk check-in: simpan foto + embedding."""
    if session.capture_count >= 3:
        return jsonify({'status': 'error', 'message': 'Sudah 3 foto diambil.'}), 400

    # Ekstrak embedding
    emb = get_embeddings(rgb, boxes)[0]

    # Simpan
    session.captured_frames.append(frame)
    session.embeddings.append(emb)
    session.capture_count += 1

    # Buat thumbnail preview (base64) untuk ditampilkan di browser
    _, thumb_buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
    thumb_b64 = base64.b64encode(thumb_buf.tobytes()).decode('utf-8')

    # Apakah sudah 3 foto?
    if session.capture_count >= 3:
        # Cek konsistensi 3 foto
        is_cons, dists = is_consistent(
            session.embeddings[0], session.embeddings[1], session.embeddings[2]
        )

        if not is_cons:
            # Reset foto, minta ulang
            session.captured_frames = []
            session.embeddings = []
            session.capture_count = 0
            return jsonify({
                'status': 'fail',
                'reason': 'inconsistent',
                'message': 'Wajah tidak konsisten antar 3 foto. Silakan ulangi dari awal.',
                'session': session.to_dict(),
            })

        # Kirim ke laptop backend
        result = send_enrollment(session.id_tamu, session.captured_frames, session.embeddings)

        # Selesai — stop session
        enrollment_success = (result.get('status') == 'success')
        session.reset()
        camera.close()

        return jsonify({
            'status': 'complete',
            'enrollment_status': result.get('status', 'error'),
            'message': result.get('message', 'Enrollment selesai.'),
            'capture_count': 3,
            'preview': f'data:image/jpeg;base64,{thumb_b64}',
        })

    # Belum 3 foto — kirim update progress
    return jsonify({
        'status': 'captured',
        'capture_count': session.capture_count,
        'message': f'Foto {session.capture_count} dari 3 diterima!',
        'preview': f'data:image/jpeg;base64,{thumb_b64}',
        'session': session.to_dict(),
    })


# ═════════════════════════════════════════════════════════════════
#  CHECK-OUT LOGIC
# ═════════════════════════════════════════════════════════════════

def _handle_checkout_capture(frame, rgb, boxes):
    """Proses capture untuk check-out: cocokkan wajah."""

    # Ekstrak embedding target
    target_emb = get_embeddings(rgb, boxes)[0]

    # Ambil semua embedding dari laptop
    db_records = get_embeddings_from_laptop()
    if not db_records:
        return jsonify({
            'status': 'fail',
            'reason': 'no_data',
            'message': 'Tidak ada data tamu yang sedang check-in di database.',
            'session': session.to_dict(),
        })

    # Cocokkan
    is_match, best_match, min_dist = find_match(target_emb, db_records, threshold=0.6)

    # Buat thumbnail
    _, thumb_buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
    thumb_b64 = base64.b64encode(thumb_buf.tobytes()).decode('utf-8')

    if is_match:
        pct = max(0, int((1 - min_dist) * 100))
        return jsonify({
            'status': 'matched',
            'id_tamu': best_match['id_tamu'],
            'nama': best_match['nama'],
            'match_pct': pct,
            'distance': float(min_dist),
            'preview': f'data:image/jpeg;base64,{thumb_b64}',
            'message': f'Wajah dikenali: {best_match["nama"]} (kecocokan {pct}%)',
            'session': session.to_dict(),
        })
    else:
        return jsonify({
            'status': 'not_matched',
            'distance': float(min_dist),
            'preview': f'data:image/jpeg;base64,{thumb_b64}',
            'message': 'Wajah tidak dikenali dalam database.',
            'session': session.to_dict(),
        })


@app.route('/engine/confirm-checkout', methods=['POST'])
def api_confirm_checkout():
    """
    Konfirmasi check-out setelah wajah cocok.
    Body: { id_tamu: str }
    """
    data = request.get_json() or {}
    id_tamu = data.get('id_tamu', '').strip()

    if not id_tamu:
        return jsonify({'status': 'error', 'message': 'id_tamu wajib diisi'}), 400

    # Kirim hasil ke laptop
    result = send_verification_result(id_tamu, 'success', data.get('distance', 0))

    # Selesai
    session.reset()
    camera.close()

    return jsonify({
        'status': result.get('status', 'error'),
        'message': result.get('message', 'Check-out diproses.'),
    })


# ═════════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("=" * 60)
    print(f"  E-BGR ENGINE v2  |  http://0.0.0.0:{ENGINE_PORT}")
    print(f"  Mode: Web Streaming (tanpa monitor/Tkinter)")
    print(f"  Kamera: {CAMERA_SOURCE}  |  Ambang blur: {BLUR_THRESHOLD:g}")
    print(f"  Endpoints:")
    print(f"    GET  /engine/status")
    print(f"    GET  /engine/stream          <- MJPEG live stream")
    print(f"    POST /engine/start-session")
    print(f"    POST /engine/stop-session")
    print(f"    POST /engine/capture")
    print(f"    POST /engine/confirm-checkout")
    print("=" * 60)
    app.run(host=ENGINE_HOST, port=ENGINE_PORT, debug=False, threaded=True)
