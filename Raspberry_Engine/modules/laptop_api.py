"""
Helper modul: Komunikasi dari Raspberry Pi Engine → Laptop Backend API
"""
import requests
import base64
import sys
import os

# Import konfigurasi (path relatif dari root RPi)
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from engine_config import LAPTOP_URL

TIMEOUT = 30  # detik


def send_enrollment(id_tamu: str, frame_list: list, embeddings: list) -> dict:
    """
    Kirim foto (numpy BGR frames) + embeddings ke laptop setelah check-in berhasil.
    Args:
        id_tamu    : ID tamu (mis. 'T013')
        frame_list : list numpy array (BGR) hasil tangkapan kamera
        embeddings : list numpy array 128-D
    Returns:
        dict respons dari laptop API
    """
    import cv2
    import numpy as np

    photos_b64 = []
    for frame in frame_list:
        _, buf = cv2.imencode('.jpg', frame)
        photos_b64.append(base64.b64encode(buf.tobytes()).decode('utf-8'))

    emb_list = [e.tolist() if hasattr(e, 'tolist') else list(e) for e in embeddings]

    payload = {
        'id_tamu':    id_tamu,
        'photos':     photos_b64,
        'embeddings': emb_list,
    }
    try:
        res = requests.post(f"{LAPTOP_URL}/api/receive-enrollment", json=payload, timeout=TIMEOUT)
        return res.json()
    except requests.exceptions.ConnectionError:
        return {'status': 'error', 'message': 'Tidak bisa terhubung ke laptop. Pastikan server.py berjalan.'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def send_verification_result(id_tamu: str, status: str, distance: float) -> dict:
    """
    Kirim hasil pencocokan wajah (check-out) ke laptop.
    Args:
        id_tamu  : ID tamu yang cocok (None jika tidak ada)
        status   : 'success' atau 'failed'
        distance : jarak Euclidean hasil matching
    """
    payload = {
        'id_tamu':  id_tamu,
        'status':   status,
        'distance': float(distance) if distance is not None else None,
    }
    try:
        res = requests.post(f"{LAPTOP_URL}/api/receive-verification", json=payload, timeout=10)
        return res.json()
    except requests.exceptions.ConnectionError:
        return {'status': 'error', 'message': 'Tidak bisa terhubung ke laptop.'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def get_embeddings_from_laptop() -> list:
    """
    Ambil semua embedding tamu yang sedang checked-in dari database laptop.
    Returns:
        list of { id_tamu, nama, status, embeddings: [[...], ...] }
    """
    try:
        res = requests.get(f"{LAPTOP_URL}/api/embeddings", timeout=10)
        if res.status_code == 200:
            return res.json().get('records', [])
        return []
    except Exception as e:
        print(f"[LAPTOP API] Gagal ambil embeddings: {e}")
        return []
