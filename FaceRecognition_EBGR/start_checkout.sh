#!/bin/bash
# ============================================================
#   E-BGR VERIFIKASI & CHECK-OUT — Raspberry Pi OS
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/venv/bin/activate"
python3 "$SCRIPT_DIR/app_checkout.py"
