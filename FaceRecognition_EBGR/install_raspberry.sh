#!/bin/bash
# ============================================================
#   E-BGR — Script Instalasi Otomatis untuk Raspberry Pi OS
#   Jalankan sekali saja dengan: bash install_raspberry.sh
# ============================================================

set -e  # Hentikan jika ada error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo ""
echo "================================================================"
echo "  E-BGR — Instalasi Dependensi untuk Raspberry Pi OS"
echo "  Folder Proyek: $SCRIPT_DIR"
echo "================================================================"
echo ""

# ── 1. Update sistem ─────────────────────────────────────────────
echo "[1/8] Mengupdate package list..."
sudo apt-get update -y

# ── 2. Instalasi dependensi sistem ───────────────────────────────
echo "[2/8] Menginstal dependensi sistem..."
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-tk \
    cmake \
    build-essential \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libatlas-base-dev \
    libboost-python-dev \
    libboost-system-dev \
    libboost-filesystem-dev \
    libboost-thread-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    lxterminal \
    xterm \
    git

# ── 3. Buat Virtual Environment ───────────────────────────────────
echo "[3/8] Membuat virtual environment Python di $SCRIPT_DIR/venv ..."
cd "$SCRIPT_DIR"
python3 -m venv venv
source venv/bin/activate

# ── 4. Update pip ─────────────────────────────────────────────────
echo "[4/8] Mengupdate pip..."
pip install --upgrade pip setuptools wheel

# ── 5. Instalasi library Python umum ─────────────────────────────
echo "[5/8] Menginstal Flask, MQTT, Pillow, OpenCV..."
pip install \
    flask \
    paho-mqtt \
    Pillow \
    numpy \
    opencv-python \
    requests

# ── 6. Instalasi dlib (proses paling lama, ~30-60 menit di RPi) ──
echo "[6/8] Menginstal dlib (kompilasi dari source, harap tunggu ~30-60 menit)..."
echo "      CATATAN: Pastikan Raspberry Pi dalam kondisi berventilasi baik."
pip install dlib

# ── 7. Instalasi face_recognition ────────────────────────────────
echo "[7/8] Menginstal face_recognition..."
pip install face_recognition

# ── 8. Set permission executable untuk shell scripts ─────────────
echo "[8/8] Mengatur permission file .sh..."
chmod +x "$SCRIPT_DIR/start_server.sh"
chmod +x "$SCRIPT_DIR/start_checkin.sh"
chmod +x "$SCRIPT_DIR/start_checkout.sh"
chmod +x "$SCRIPT_DIR/install_raspberry.sh"

echo ""
echo "================================================================"
echo "  ✅  Instalasi SELESAI!"
echo ""
echo "  Cara menjalankan sistem E-BGR di Raspberry Pi:"
echo ""
echo "  1. Jalankan Server:"
echo "     bash $SCRIPT_DIR/start_server.sh"
echo ""
echo "  2. Buka browser di Raspberry Pi atau HP/Laptop:"
echo "     http://localhost:5000  (dari RPi)"
echo "     http://<IP-RPi>:5000  (dari perangkat lain)"
echo ""
echo "  3. Login:"
echo "     Admin  →  admin  / ebgr2025"
echo "     User   →  denzel / ta2025"
echo "================================================================"
echo ""
