import sqlite3
import os
import json
import numpy as np

# Path database berada di folder data/
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'local_ebgr.db')

def get_connection():
    """Membuka koneksi ke SQLite database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Inisialisasi tabel tamu dan log_verifikasi jika belum ada"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_connection()
    cursor = conn.cursor()

    # Tabel Tamu (Penyimpanan Utama)
    # embedding disimpan sebagai JSON string dari array float (karena sqlite tidak mendukung tipe data array)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tamu (
        id_tamu TEXT PRIMARY KEY,
        nama TEXT NOT NULL,
        nik TEXT,
        periode_akses TEXT,
        status TEXT DEFAULT 'registered', -- registered, checked-in, checked-out
        foto_dir_path TEXT,
        embedding_1 TEXT,
        embedding_2 TEXT,
        embedding_3 TEXT,
        checked_in_at DATETIME,
        checked_out_at DATETIME,
        duration_visit TEXT
    )
    ''')

    # Tabel Log Verifikasi (Penyimpanan History Kehadiran)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS log_verifikasi (
        id_log INTEGER PRIMARY KEY AUTOINCREMENT,
        id_tamu TEXT,
        tipe_event TEXT, -- 'check-in' atau 'check-out'
        distance_score REAL,
        status_verifikasi TEXT, -- 'success', 'failed', 'rejected'
        foto_verifikasi_path TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (id_tamu) REFERENCES tamu(id_tamu)
    )
    ''')

    conn.commit()
    conn.close()
    print(f"[DB] Database berhasil diinisialisasi di {DB_PATH}")

def register_tamu_from_rfid(id_tamu, nama, nik, periode_akses):
    """(Simulasi) Mendaftarkan tamu baru dari hasil tap e-KTP RFID"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO tamu (id_tamu, nama, nik, periode_akses, status)
            VALUES (?, ?, ?, ?, 'registered')
        ''', (id_tamu, nama, nik, periode_akses))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        print(f"[DB ERROR] Tamu dengan ID {id_tamu} sudah ada.")
        return False
    finally:
        conn.close()

def generate_auto_id_tamu():
    """Menghasilkan ID unik otomatis berurutan (contoh: T001, T002, T003...)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_tamu FROM tamu")
    rows = cursor.fetchall()
    conn.close()
    
    max_num = 0
    for r in rows:
        id_str = r['id_tamu']
        if id_str and id_str.startswith('T'):
            num_part = id_str[1:]
            if num_part.isdigit():
                val = int(num_part)
                if val > max_num:
                    max_num = val
                    
    next_num = max_num + 1
    return f"T{next_num:03d}"

# Inisialisasi otomatis ketika modul dipanggil
init_db()
