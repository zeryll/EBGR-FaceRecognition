# ============================================================
#   KONFIGURASI ENGINE — Raspberry Pi
#   Sesuaikan IP_LAPTOP dengan IP laptop Anda di jaringan lokal
#   Cek IP laptop: ipconfig (Windows) → IPv4 Address
# ============================================================

# IP Laptop yang menjalankan server Flask (port 5000)
LAPTOP_URL = "http://192.168.1.10:5000"   # ← GANTI dengan IP laptop Anda

# Port engine Raspberry Pi
ENGINE_HOST = "0.0.0.0"
ENGINE_PORT = 5001
