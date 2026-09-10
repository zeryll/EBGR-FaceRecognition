#!/bin/bash
# ============================================================
#   E-BGR ENGINE -- Script Instalasi untuk Raspberry Pi
#   Jalankan sekali: bash install_raspberry.sh
# ============================================================
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "[1/6] Update package list..."
sudo apt-get update -y
echo "[2/6] Install dependensi sistem..."
sudo apt-get install -y python3 python3-pip python3-venv python3-tk cmake build-essential \
    libopenblas-dev liblapack-dev libx11-dev libjpeg-dev libpng-dev \
    libavcodec-dev libavformat-dev libswscale-dev libv4l-dev xterm git
echo "[3/6] Buat virtual environment..."
cd "$SCRIPT_DIR"
python3 -m venv venv
source venv/bin/activate
echo "[4/6] Install library Python..."
pip install --upgrade pip setuptools wheel
pip install flask requests Pillow numpy opencv-python
echo "[5/6] Install dlib (30-60 menit, harap sabar)..."
pip install dlib
echo "[6/6] Install face_recognition..."
pip install face_recognition
chmod +x "$SCRIPT_DIR/start_engine.sh"
echo ""
echo "Instalasi selesai! Jalankan: bash start_engine.sh"