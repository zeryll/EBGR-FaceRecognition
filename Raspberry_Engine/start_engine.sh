#!/bin/bash
# ============================================================
#   E-BGR ENGINE -- Raspberry Pi
#   Jalankan ini pertama kali sebelum menggunakan dashboard
#   Engine akan menerima perintah dari laptop di port 5001
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export DISPLAY=:0
echo "============================================================"
echo "  E-BGR RASPBERRY PI ENGINE"
echo "  Port: 5001"
echo "  Tekan Ctrl+C untuk menghentikan"
echo "============================================================"
source "$SCRIPT_DIR/venv/bin/activate"
python3 "$SCRIPT_DIR/engine.py"