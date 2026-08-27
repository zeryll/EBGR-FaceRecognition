#!/bin/bash
# ============================================================
#   E-BGR SERVER LOKAL — Raspberry Pi OS
#   Setelah berjalan, buka browser: http://localhost:5000
#   Atau dari perangkat lain: http://<IP-RPi>:5000
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/venv/bin/python3"

echo "============================================================"
echo "  E-BGR SERVER LOKAL"
echo "  Dashboard: http://localhost:5000"
echo "  Tekan Ctrl+C untuk menghentikan server"
echo "============================================================"

# Aktifkan virtual environment dan jalankan server
source "$SCRIPT_DIR/venv/bin/activate"
python3 "$SCRIPT_DIR/server.py"
