#!/usr/bin/env python3
"""
Kalibrasi ambang blur (Variance of Laplacian) untuk webcam yang dipakai engine.
Headless: berjalan di terminal Raspberry Pi tanpa monitor.

Jalankan (engine.py boleh menyala, asal tidak ada sesi check-in/check-out aktif):
    venv/bin/python kalibrasi_blur.py

Langkah:
  1. TAJAM  : duduk diam ~1 m di depan kamera, wajah di tengah.
  2. GERAK  : gerakkan/goyangkan kepala dengan cepat (meniru foto buram karena gerak).
Skrip mengukur nilai var pada setiap frame, menyarankan BLUR_THRESHOLD,
dan menyimpan data mentah + contoh frame di folder kalibrasi_hasil/.
"""
import csv
import os
import sys
import time
from datetime import datetime

import cv2
import numpy as np

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from engine_config import CAMERA_SOURCE
except ImportError:
    CAMERA_SOURCE = 0
try:
    from engine_config import BLUR_THRESHOLD
except ImportError:
    BLUR_THRESHOLD = 100.0

N_FRAME = 40           # frame per tahap
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kalibrasi_hasil')


def buka_kamera(src):
    """Buka kamera dengan pengaturan yang sama seperti engine.py (V4L2, MJPG, 640x480)."""
    if isinstance(src, str) and src.strip().isdigit():
        src = int(src.strip())
    cap = None
    if isinstance(src, int) and hasattr(cv2, 'CAP_V4L2') and sys.platform.startswith('linux'):
        cap = cv2.VideoCapture(src, cv2.CAP_V4L2)
    if cap is None or not cap.isOpened():
        cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        return None
    if isinstance(src, int):
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def nilai_var(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def rekam(cap, label):
    input(f"\n[{label}] Tekan Enter untuk mulai merekam {N_FRAME} frame...")
    for _ in range(5):          # buang frame lama di buffer
        cap.read()
    hasil = []
    for i in range(N_FRAME):
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        hasil.append((nilai_var(frame), frame))
        time.sleep(0.05)
    vals = [v for v, _ in hasil]
    if not vals:
        print("    [!] Tidak ada frame terbaca.")
        return hasil
    print(f"    {len(vals)} frame | min {min(vals):.1f} | median {np.median(vals):.1f} | max {max(vals):.1f}")
    return hasil


def main():
    print("=" * 60)
    print("  KALIBRASI AMBANG BLUR — E-BGR ENGINE")
    print(f"  Kamera: {CAMERA_SOURCE} | Ambang saat ini: {BLUR_THRESHOLD:g}")
    print("=" * 60)

    cap = buka_kamera(CAMERA_SOURCE)
    if cap is None:
        print("[!] Kamera tidak bisa dibuka. Pastikan tidak ada sesi aktif di engine.")
        sys.exit(1)
    # Pemanasan: frame awal masih gelap/buram karena auto-exposure & fokus belum stabil
    ok, f = False, None
    for _ in range(30):
        ok, f = cap.read()
    if ok:
        print(f"Resolusi aktual: {f.shape[1]}x{f.shape[0]}")

    print("\nTahap 1 — TAJAM: duduk diam ~1 m di depan kamera, wajah di tengah,")
    print("pencahayaan seperti saat pemakaian normal.")
    tajam = rekam(cap, "TAJAM")

    print("\nTahap 2 — GERAK: saat merekam, goyangkan kepala ke kiri-kanan dengan cepat.")
    gerak = rekam(cap, "GERAK")
    cap.release()

    v_tajam = np.array([v for v, _ in tajam])
    v_gerak = np.array([v for v, _ in gerak])
    if len(v_tajam) == 0 or len(v_gerak) == 0:
        print("[!] Data tidak lengkap, kalibrasi dibatalkan.")
        sys.exit(1)

    p10_tajam = float(np.percentile(v_tajam, 10))
    p90_gerak = float(np.percentile(v_gerak, 90))
    if p10_tajam > p90_gerak:
        saran = (p10_tajam + p90_gerak) / 2
        catatan = "terpisah jelas; ambang = titik tengah P10 tajam dan P90 gerak"
    else:
        saran = 0.8 * p10_tajam
        catatan = ("nilai tajam dan gerak TUMPANG TINDIH; ambang = 0,8 x P10 tajam "
                   "(sebagian frame bergerak akan lolos). Ulangi tahap GERAK dengan "
                   "gerakan lebih cepat, atau periksa contoh frame yang disimpan")
    saran = float(round(saran))

    def persen(arr, cond):
        return 100.0 * np.count_nonzero(cond(arr)) / len(arr)

    print("\n" + "=" * 60)
    print("  HASIL")
    print(f"  Tajam : P10 {p10_tajam:.1f} | median {np.median(v_tajam):.1f}")
    print(f"  Gerak : P90 {p90_gerak:.1f} | median {np.median(v_gerak):.1f}")
    print(f"  Catatan: {catatan}")
    print(f"\n  SARAN BLUR_THRESHOLD = {saran:g}")
    print(f"    -> frame tajam lolos    : {persen(v_tajam, lambda a: a >= saran):.0f}%")
    print(f"    -> frame gerak ditolak  : {persen(v_gerak, lambda a: a < saran):.0f}%")
    print(f"  (Ambang saat ini {BLUR_THRESHOLD:g}: tajam lolos "
          f"{persen(v_tajam, lambda a: a >= BLUR_THRESHOLD):.0f}%, gerak ditolak "
          f"{persen(v_gerak, lambda a: a < BLUR_THRESHOLD):.0f}%)")
    print("\n  Ubah nilai BLUR_THRESHOLD di engine_config.py, lalu jalankan ulang engine.py.")
    print("=" * 60)

    # Simpan data mentah dan contoh frame sebagai bukti kalibrasi
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs(OUT_DIR, exist_ok=True)
    csv_path = os.path.join(OUT_DIR, f'kalibrasi_{stamp}.csv')
    with open(csv_path, 'w', newline='') as fh:
        w = csv.writer(fh, delimiter=';')
        w.writerow(['tahap', 'frame', 'var'])
        for i, (v, _) in enumerate(tajam):
            w.writerow(['tajam', i + 1, f'{v:.2f}'])
        for i, (v, _) in enumerate(gerak):
            w.writerow(['gerak', i + 1, f'{v:.2f}'])
        w.writerow([])
        w.writerow(['saran_ambang', '', f'{saran:g}'])
    for nama, data in (('tajam', tajam), ('gerak', gerak)):
        terurut = sorted(data, key=lambda x: x[0])
        cv2.imwrite(os.path.join(OUT_DIR, f'{stamp}_{nama}_min.jpg'), terurut[0][1])
        cv2.imwrite(os.path.join(OUT_DIR, f'{stamp}_{nama}_max.jpg'), terurut[-1][1])
    print(f"Data mentah & contoh frame disimpan di: {OUT_DIR}")


if __name__ == '__main__':
    main()
