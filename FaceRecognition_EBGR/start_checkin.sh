#!/bin/bash
# ============================================================
#   E-BGR PENDAFTARAN (Check-In) — Raspberry Pi OS
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/venv/bin/activate"
python3 "$SCRIPT_DIR/app_checkin.py"
