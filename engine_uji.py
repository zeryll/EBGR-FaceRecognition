#!/usr/bin/env python3
"""
E-BGR Engine — MODE PENGUJIAN (khusus pengujian Bab IV)
=======================================================
Menjalankan engine.py yang SAMA PERSIS (tidak diubah), lalu menambahkan pencatatan:

  1. hasil_uji/capture_<tanggal>.csv
     Satu baris per permintaan /engine/capture: mode, status, reason, nilai var (blur),
     jarak, ID dikenali, dan waktu tiap tahap di Raspberry Pi
     (blur, deteksi HOG, ekstraksi vektor, ambil data laptop, pencocokan, kirim enrollment).

  2. hasil_uji/lembar_uji_sumberdaya_<tanggal>.csv
     Sampel CPU, RAM, dan suhu Raspberry Pi setiap 1 detik, langsung dalam format
     PENULISAN/analisis/lembar_uji_sumberdaya.csv (kondisi: idle / stream / capture).

Cara pakai di Raspberry Pi (folder yang sama dengan engine.py):
    venv/bin/python engine_uji.py          # pengganti: python3 engine.py
Hentikan dengan Ctrl+C. Kembali ke mode normal cukup jalankan engine.py seperti biasa.
"""
import csv
import os
import sys
import threading
import time
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import engine  # noqa: E402  (engine asli; Flask app, kamera, dan endpoint dibuat di sini)

HASIL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hasil_uji')
os.makedirs(HASIL_DIR, exist_ok=True)
_STAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
CAPTURE_CSV = os.path.join(HASIL_DIR, f'capture_{_STAMP}.csv')
SUMBERDAYA_CSV = os.path.join(HASIL_DIR, f'lembar_uji_sumberdaya_{_STAMP}.csv')
INTERVAL_SAMPEL = 1.0  # detik

_tulis_lock = threading.Lock()
_lokal = threading.local()      # waktu tiap tahap untuk permintaan yang sedang diproses
_capture_aktif = 0              # jumlah capture yang sedang berjalan
_capture_terjadi = False        # ada capture dalam interval sampel terakhir
_status_lock = threading.Lock()


def _tulis_baris(path, header, row):
    with _tulis_lock:
        baru = not os.path.exists(path)
        with open(path, 'a', newline='', encoding='utf-8-sig' if baru else 'utf-8') as fh:
            w = csv.writer(fh, delimiter=';')
            if baru:
                w.writerow(header)
            w.writerow(row)


def _ms(detik):
    return f'{detik * 1000:.1f}'.replace('.', ',')


# ─── Pembungkus fungsi engine untuk mengukur waktu tiap tahap ────────────────

def _bungkus(nama_fungsi, kunci, catat_hasil=None):
    asli = getattr(engine, nama_fungsi)

    def dibungkus(*args, **kwargs):
        t0 = time.perf_counter()
        hasil = asli(*args, **kwargs)
        waktu = getattr(_lokal, 'waktu', None)
        if waktu is not None:
            waktu[kunci] = waktu.get(kunci, 0.0) + (time.perf_counter() - t0)
            if catat_hasil:
                catat_hasil(hasil)
        return hasil

    setattr(engine, nama_fungsi, dibungkus)


def _catat_var(hasil):
    _lokal.var = float(hasil[1])


_bungkus('is_image_blurry', 'blur', _catat_var)
_bungkus('detect_faces', 'deteksi')
_bungkus('get_embeddings', 'vektor')
_bungkus('get_embeddings_from_laptop', 'ambil_data')
_bungkus('find_match', 'cocok')
_bungkus('is_consistent', 'konsistensi')
_bungkus('send_enrollment', 'kirim')

CAPTURE_HEADER = ['no', 'waktu', 'mode', 'id_tamu_sesi', 'foto_ke', 'status', 'reason', 'var_blur',
                  'distance', 'id_tamu_dikenali', 'total_rpi_ms', 'blur_ms', 'deteksi_ms', 'vektor_ms',
                  'ambil_data_ms', 'cocok_ms', 'konsistensi_ms', 'kirim_ms', 'suhu_c']
_no_capture = 0

_capture_asli = engine.app.view_functions['api_capture']


def capture_uji():
    global _no_capture, _capture_aktif, _capture_terjadi
    sesi = engine.session.to_dict()
    with _status_lock:
        _capture_aktif += 1
        _capture_terjadi = True
    _lokal.waktu = {}
    _lokal.var = None
    t0 = time.perf_counter()
    try:
        resp = _capture_asli()
    finally:
        total = time.perf_counter() - t0
        with _status_lock:
            _capture_aktif -= 1
    try:
        obj = resp[0] if isinstance(resp, tuple) else resp
        data = obj.get_json(silent=True) or {}
        if data.get('status') == 'error':  # tidak ada sesi / kamera gagal: bukan pemindaian
            return resp
        w = _lokal.waktu
        _no_capture += 1
        foto_ke = data.get('capture_count') if data.get('status') in ('captured', 'complete') else ''
        dist = data.get('distance')
        _tulis_baris(CAPTURE_CSV, CAPTURE_HEADER, [
            _no_capture, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            sesi.get('mode') or '', sesi.get('id_tamu') or '', foto_ke,
            data.get('status', ''), data.get('reason', ''),
            f'{_lokal.var:.1f}'.replace('.', ',') if _lokal.var is not None else '',
            f'{dist:.4f}'.replace('.', ',') if isinstance(dist, (int, float)) else '',
            data.get('id_tamu', ''), _ms(total),
            *[_ms(w[k]) if k in w else '' for k in
              ('blur', 'deteksi', 'vektor', 'ambil_data', 'cocok', 'konsistensi', 'kirim')],
            _baca_suhu() or '',
        ])
    except Exception as e:  # pencatatan tidak boleh mengganggu engine
        print(f'[UJI] Gagal mencatat capture: {e}')
    finally:
        _lokal.waktu = None
    return resp


engine.app.view_functions['api_capture'] = capture_uji


# ─── Pemantauan sumber daya Raspberry Pi ─────────────────────────────────────

def _baca_cpu():
    try:
        with open('/proc/stat') as fh:
            v = [int(x) for x in fh.readline().split()[1:]]
        idle = v[3] + (v[4] if len(v) > 4 else 0)
        return sum(v), idle
    except Exception:
        return None


def _baca_ram():
    try:
        info = {}
        with open('/proc/meminfo') as fh:
            for line in fh:
                k, val = line.split(':', 1)
                info[k] = int(val.split()[0])
        total = info['MemTotal'] / 1024
        return total - info['MemAvailable'] / 1024, total
    except Exception:
        return None, None


def _baca_suhu():
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as fh:
            return f'{int(fh.read().strip()) / 1000:.1f}'.replace('.', ',')
    except Exception:
        return None


SUMBERDAYA_HEADER = ['no', 'kondisi', 'cpu_persen', 'ram_terpakai_mb', 'ram_total_mb', 'suhu_c', 'catatan']


def _pantau_sumberdaya():
    global _capture_terjadi
    no = 0
    sebelum = _baca_cpu()
    if sebelum is None:
        print('[UJI] /proc/stat tidak ada (bukan Linux) — pemantauan sumber daya dinonaktifkan.')
        return
    while True:
        time.sleep(INTERVAL_SAMPEL)
        sesudah = _baca_cpu()
        d_total, d_idle = sesudah[0] - sebelum[0], sesudah[1] - sebelum[1]
        sebelum = sesudah
        cpu = 100.0 * (d_total - d_idle) / d_total if d_total else 0.0
        with _status_lock:
            kondisi = 'capture' if (_capture_aktif or _capture_terjadi) else None
            _capture_terjadi = False
        if kondisi is None:
            kondisi = 'stream' if engine.camera.is_open else 'idle'
        ram, total = _baca_ram()
        no += 1
        _tulis_baris(SUMBERDAYA_CSV, SUMBERDAYA_HEADER, [
            no, kondisi, f'{cpu:.1f}'.replace('.', ','),
            f'{ram:.0f}' if ram is not None else '', f'{total:.0f}' if total is not None else '',
            _baca_suhu() or '', datetime.now().strftime('%H:%M:%S'),
        ])


threading.Thread(target=_pantau_sumberdaya, daemon=True).start()


if __name__ == '__main__':
    print('=' * 60)
    print('  E-BGR ENGINE — MODE PENGUJIAN')
    print(f'  Kamera: {engine.CAMERA_SOURCE}')
    print(f'  Log capture    : {CAPTURE_CSV}')
    print(f'  Log sumber daya: {SUMBERDAYA_CSV}')
    print('=' * 60)
    engine.app.run(host=engine.ENGINE_HOST, port=engine.ENGINE_PORT, debug=False, threaded=True)
