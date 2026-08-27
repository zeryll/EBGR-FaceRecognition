import tkinter as tk
from tkinter import messagebox, simpledialog
import cv2
from PIL import Image, ImageTk
import os
import json
import time
import numpy as np

import sys
sys.path.append(os.path.dirname(__file__))

from modules.database import get_connection, register_tamu_from_rfid, generate_auto_id_tamu
from modules.vision import is_image_blurry
from modules.face_engine import detect_faces, get_embeddings, is_consistent
from modules.mqtt_client import publish_checkin

# ─────────────────────────────────────────────
#  Warna & Font
# ─────────────────────────────────────────────
C_BG      = "#0f172a"   # dark navy
C_PANEL   = "#1e293b"
C_BORDER  = "#334155"
C_TEXT    = "#f1f5f9"
C_MUTED   = "#94a3b8"
C_GREEN   = "#10b981"
C_ORANGE  = "#f59e0b"
C_RED     = "#ef4444"
C_BLUE    = "#3b82f6"
C_CYAN    = "#22d3ee"
FONT_BIG  = ("Segoe UI", 15, "bold")
FONT_MED  = ("Segoe UI", 12)
FONT_SM   = ("Segoe UI", 10)
FONT_MONO = ("Consolas", 11)


class CheckInApp:
    def __init__(self, window):
        self.window = window
        self.window.title("E-BGR — Pendaftaran Tamu (Check-In)")
        self.window.configure(bg=C_BG)
        self.window.resizable(False, False)

        # State
        self.vid            = cv2.VideoCapture(0)
        self.is_processing  = False
        self.current_tamu   = None
        self.captured_faces = []
        self.capture_count  = 0
        self.countdown_val  = 0          # nilai hitung mundur aktif
        self.show_flash     = False      # efek flash setelah foto diambil
        self.flash_counter  = 0
        self.last_status_color = C_TEXT

        self._build_ui()
        self._update_frame()

    # ──────────────── BUILD UI ────────────────

    def _build_ui(self):
        CAM_W = int(self.vid.get(cv2.CAP_PROP_FRAME_WIDTH))
        CAM_H = int(self.vid.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # ── Canvas kamera ──
        self.canvas = tk.Canvas(
            self.window, width=CAM_W, height=CAM_H,
            bg="black", highlightthickness=0
        )
        self.canvas.pack()

        # ── Panel bawah ──
        self.bottom = tk.Frame(self.window, bg=C_BG)
        self.bottom.pack(fill="x", padx=0, pady=0)

        # Progress bar foto
        self.frm_progress = tk.Frame(self.bottom, bg=C_BG)
        self.frm_progress.pack(pady=(10, 0))
        self.dot_labels = []
        for i in range(3):
            dot = tk.Label(
                self.frm_progress,
                text="○", font=("Segoe UI", 20),
                fg=C_BORDER, bg=C_BG
            )
            dot.pack(side="left", padx=6)
            self.dot_labels.append(dot)

        # Label status
        self.lbl_status = tk.Label(
            self.bottom,
            text="Masukkan nama tamu untuk memulai pendaftaran.",
            font=FONT_BIG, fg=C_TEXT, bg=C_BG,
            wraplength=700, justify="center"
        )
        self.lbl_status.pack(pady=(8, 4))

        # Label sub-status (notifikasi kecil)
        self.lbl_sub = tk.Label(
            self.bottom,
            text="",
            font=FONT_SM, fg=C_MUTED, bg=C_BG
        )
        self.lbl_sub.pack(pady=(0, 6))

        # ── Tombol ──
        self.frm_btn = tk.Frame(self.bottom, bg=C_BG)
        self.frm_btn.pack(pady=(4, 14))

        self.btn_input = tk.Button(
            self.frm_btn,
            text="➕  Tambah Tamu Baru",
            font=FONT_MED,
            bg=C_GREEN, fg="white",
            activebackground="#059669", activeforeground="white",
            relief="flat", cursor="hand2",
            padx=18, pady=8,
            command=self._input_nama
        )
        self.btn_input.pack(side="left", padx=6)

        self.btn_ambil = tk.Button(
            self.frm_btn,
            text="📸  Ambil Foto Sekarang",
            font=FONT_MED,
            bg=C_BLUE, fg="white",
            activebackground="#2563eb", activeforeground="white",
            relief="flat", cursor="hand2",
            padx=18, pady=8,
            state="disabled",
            command=self._manual_capture
        )
        self.btn_ambil.pack(side="left", padx=6)

        self.btn_ulang = tk.Button(
            self.frm_btn,
            text="🔄  Ulangi",
            font=FONT_MED,
            bg=C_BORDER, fg=C_TEXT,
            activebackground="#475569", activeforeground="white",
            relief="flat", cursor="hand2",
            padx=14, pady=8,
            state="disabled",
            command=self._reset_ui
        )
        self.btn_ulang.pack(side="left", padx=6)

    # ──────────────── INPUT NAMA ────────────────

    def _input_nama(self):
        nama = simpledialog.askstring(
            "Pendaftaran Tamu Baru",
            "Masukkan Nama Lengkap Tamu:",
            parent=self.window
        )
        if not nama or not nama.strip():
            return

        nama = nama.strip()
        id_tamu = generate_auto_id_tamu()

        ok = register_tamu_from_rfid(id_tamu, nama, "327123456789", "1 Hari")
        if not ok:
            messagebox.showerror("Error", "Gagal mendaftarkan ID tamu. Coba lagi.")
            return

        self.current_tamu   = {"id": id_tamu, "nama": nama}
        self.captured_faces = []
        self.capture_count  = 0
        self.is_processing  = True

        self._update_dots()
        self._set_status(
            f"Halo, {nama}!  (ID: {id_tamu})",
            f"Posisikan wajah di dalam kotak kuning, lalu klik  📸 Ambil Foto  saat siap.",
            C_CYAN
        )
        self._set_buttons(input_ok=False, ambil_ok=True, ulang_ok=True)

    # ──────────────── CAPTURE MANUAL ────────────────

    def _manual_capture(self):
        if self.capture_count >= 3:
            return

        # Nonaktifkan tombol selama validasi
        self.btn_ambil.config(state="disabled")
        self._set_status(
            f"📷  Mengambil foto {self.capture_count + 1} dari 3...",
            "Tetap diam sejenak.",
            C_ORANGE
        )
        self.window.update()

        # Beri jeda kecil agar kamera stabil
        self.window.after(300, self._do_capture)

    def _do_capture(self):
        ret, frame = self.vid.read()
        if not ret:
            self._set_status("Kamera tidak terbaca! Periksa koneksi.", "", C_RED)
            self.btn_ambil.config(state="normal")
            return

        # Validasi blur
        is_blur, var = is_image_blurry(frame)
        if is_blur:
            self._set_status(
                f"❌  Foto {self.capture_count + 1} GAGAL — Gambar terlalu buram (var={var:.1f})",
                "Pastikan pencahayaan cukup dan kamera tidak bergerak, lalu coba lagi.",
                C_RED
            )
            self.btn_ambil.config(state="normal")
            return

        # Validasi deteksi wajah
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        boxes = detect_faces(rgb)

        if len(boxes) == 0:
            self._set_status(
                f"❌  Foto {self.capture_count + 1} GAGAL — Wajah tidak terdeteksi",
                "Pastikan wajah Anda berada di dalam kotak kuning.",
                C_RED
            )
            self.btn_ambil.config(state="normal")
            return

        if len(boxes) > 1:
            self._set_status(
                f"❌  Foto {self.capture_count + 1} GAGAL — Terdeteksi lebih dari 1 wajah",
                "Pastikan hanya ada 1 orang di depan kamera.",
                C_RED
            )
            self.btn_ambil.config(state="normal")
            return

        # ✅ Foto diterima
        self.captured_faces.append((frame, rgb, boxes))
        self.capture_count += 1
        self._update_dots()

        # Efek flash hijau di layar
        self._trigger_flash()

        if self.capture_count < 3:
            self._set_status(
                f"✅  Foto {self.capture_count} dari 3 DITERIMA!",
                f"Bagus! Ubah sedikit sudut wajah Anda, lalu klik  📸 Ambil Foto  untuk foto ke-{self.capture_count + 1}.",
                C_GREEN
            )
            self.btn_ambil.config(state="normal")
        else:
            self._set_status(
                "✅  Foto ke-3 DITERIMA!  Semua foto terkumpul.",
                "Memproses data biometrik... Mohon tunggu.",
                C_GREEN
            )
            self.btn_ambil.config(state="disabled")
            self.window.after(800, self._process_enrollment)

    # ──────────────── FLASH EFFECT ────────────────

    def _trigger_flash(self):
        self.show_flash   = True
        self.flash_counter = 6   # 6 frame × 15ms ≈ 90ms flash hijau

    # ──────────────── ENROLLMENT ────────────────

    def _process_enrollment(self):
        self._set_status(
            "⚙️  Mengekstraksi fitur wajah (ResNet-29)...",
            "Proses ini berlangsung beberapa detik. Jangan tutup jendela ini.",
            C_ORANGE
        )
        self.window.update()

        embeddings = []
        for _, rgb, boxes in self.captured_faces:
            emb = get_embeddings(rgb, boxes)[0]
            embeddings.append(emb)

        # Cek konsistensi 3 foto
        is_cons, dists = is_consistent(
            embeddings[0], embeddings[1], embeddings[2], threshold=0.4
        )
        if not is_cons:
            messagebox.showwarning(
                "Wajah Tidak Konsisten",
                f"Sistem mendeteksi inkonsistensi antar foto.\n"
                f"Kemungkinan wajah bergerak terlalu banyak.\n\n"
                f"Silakan ulangi pendaftaran."
            )
            self._reset_ui()
            return

        # Simpan foto ke disk
        tamu_dir = os.path.join(
            os.path.dirname(__file__), 'data', 'tamu', self.current_tamu['id']
        )
        os.makedirs(tamu_dir, exist_ok=True)
        for i, (frame, _, _) in enumerate(self.captured_faces):
            cv2.imwrite(os.path.join(tamu_dir, f"foto_{i+1}.jpg"), frame)

        # Update database
        conn = get_connection()
        c    = conn.cursor()
        c.execute('''
            UPDATE tamu SET
                status           = 'checked-in',
                foto_dir_path    = ?,
                embedding_1      = ?,
                embedding_2      = ?,
                embedding_3      = ?,
                checked_in_at    = CURRENT_TIMESTAMP
            WHERE id_tamu = ?
        ''', (
            tamu_dir,
            json.dumps(embeddings[0].tolist()),
            json.dumps(embeddings[1].tolist()),
            json.dumps(embeddings[2].tolist()),
            self.current_tamu['id']
        ))
        c.execute('''
            INSERT INTO log_verifikasi (id_tamu, tipe_event, status_verifikasi)
            VALUES (?, 'check-in', 'success')
        ''', (self.current_tamu['id'],))
        conn.commit()
        conn.close()

        # Kirim notifikasi MQTT
        publish_checkin(self.current_tamu['id'], self.current_tamu['nama'])

        messagebox.showinfo(
            "✅  Check-In Berhasil!",
            f"Data wajah  {self.current_tamu['nama']}  (ID: {self.current_tamu['id']})\n"
            f"berhasil disimpan ke database E-BGR.\n\n"
            f"3 foto biometrik tersimpan di:\n{tamu_dir}"
        )
        self._reset_ui()

    # ──────────────── HELPERS ────────────────

    def _update_dots(self):
        for i, dot in enumerate(self.dot_labels):
            if i < self.capture_count:
                dot.config(text="●", fg=C_GREEN)
            elif i == self.capture_count and self.is_processing:
                dot.config(text="◉", fg=C_ORANGE)
            else:
                dot.config(text="○", fg=C_BORDER)

    def _set_status(self, main_text, sub_text="", color=C_TEXT):
        self.lbl_status.config(text=main_text, fg=color)
        self.lbl_sub.config(text=sub_text, fg=C_MUTED)

    def _set_buttons(self, input_ok, ambil_ok, ulang_ok):
        self.btn_input.config(state="normal" if input_ok else "disabled")
        self.btn_ambil.config(state="normal" if ambil_ok else "disabled")
        self.btn_ulang.config(state="normal" if ulang_ok else "disabled")

    def _reset_ui(self):
        self.is_processing  = False
        self.current_tamu   = None
        self.captured_faces = []
        self.capture_count  = 0
        self.show_flash     = False
        self._update_dots()
        self._set_status("Masukkan nama tamu untuk memulai pendaftaran.", "", C_TEXT)
        self._set_buttons(input_ok=True, ambil_ok=False, ulang_ok=False)

    # ──────────────── CAMERA LOOP ────────────────

    def _update_frame(self):
        ret, frame = self.vid.read()
        if ret:
            h, w = frame.shape[:2]
            cx, cy = w // 2, h // 2

            # Flash hijau setelah foto diterima
            if self.show_flash and self.flash_counter > 0:
                overlay = frame.copy()
                cv2.rectangle(overlay, (0, 0), (w, h), (0, 220, 80), -1)
                alpha = 0.35 * (self.flash_counter / 6)
                frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
                self.flash_counter -= 1
                if self.flash_counter == 0:
                    self.show_flash = False

            # Kotak panduan wajah
            box_color = (0, 255, 100) if self.is_processing else (0, 220, 255)
            cv2.rectangle(frame,
                          (cx - 150, cy - 195), (cx + 150, cy + 150),
                          box_color, 2)
            cv2.putText(frame,
                        "Posisikan Wajah Di Sini",
                        (cx - 130, cy - 210),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, box_color, 1, cv2.LINE_AA)

            # Indikator jumlah foto di sudut kiri atas
            if self.is_processing:
                cv2.putText(frame,
                            f"Foto: {self.capture_count}/3",
                            (12, 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 100), 2, cv2.LINE_AA)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.photo = ImageTk.PhotoImage(image=Image.fromarray(rgb))
            self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)

        self.window.after(15, self._update_frame)


if __name__ == '__main__':
    root = tk.Tk()
    app  = CheckInApp(root)
    root.mainloop()
