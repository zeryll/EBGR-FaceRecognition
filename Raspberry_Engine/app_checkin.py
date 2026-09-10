"""
E-BGR Check-In App -- Raspberry Pi Engine (Distributed Version)
Menerima id_tamu + nama dari argumen command-line (dikirim oleh engine.py).
Setelah 3 foto berhasil diambil, kirim ke Laptop Backend via API.
"""
import tkinter as tk
import cv2
from PIL import Image, ImageTk
import os
import json
import numpy as np
import sys
import argparse

sys.path.append(os.path.dirname(__file__))

from modules.vision      import is_image_blurry
from modules.face_engine import detect_faces, get_embeddings, is_consistent
from modules.laptop_api  import send_enrollment

# --- PARSE ARGUMEN DARI ENGINE ---
parser = argparse.ArgumentParser(description='E-BGR Check-In')
parser.add_argument('--id',   required=True, help='ID Tamu (mis. T013)')
parser.add_argument('--nama', required=True, help='Nama Tamu')
args = parser.parse_args()

ID_TAMU = args.id
NAMA    = args.nama

# --- KONSTANTA WARNA & FONT ---
C_BG     = "#0f172a"
C_BORDER = "#334155"
C_TEXT   = "#f1f5f9"
C_MUTED  = "#94a3b8"
C_GREEN  = "#10b981"
C_ORANGE = "#f59e0b"
C_RED    = "#ef4444"
C_BLUE   = "#3b82f6"
C_CYAN   = "#22d3ee"
FONT_BIG = ("Segoe UI", 15, "bold")
FONT_MED = ("Segoe UI", 12)
FONT_SM  = ("Segoe UI", 10)


class CheckInApp:
    def __init__(self, window):
        self.window = window
        self.window.title(f"E-BGR Check-In -- {NAMA} ({ID_TAMU})")
        self.window.configure(bg=C_BG)
        self.window.resizable(False, False)

        self.vid            = cv2.VideoCapture(0)
        self.captured_faces = []  # list of (frame_bgr, rgb, boxes)
        self.embeddings     = []
        self.capture_count  = 0
        self.show_flash     = False
        self.flash_counter  = 0

        self._build_ui()
        self._update_frame()

    # --- UI ---

    def _build_ui(self):
        CAM_W = int(self.vid.get(cv2.CAP_PROP_FRAME_WIDTH))
        CAM_H = int(self.vid.get(cv2.CAP_PROP_FRAME_HEIGHT))

        self.canvas = tk.Canvas(self.window, width=CAM_W, height=CAM_H,
                                bg='black', highlightthickness=0)
        self.canvas.pack()

        bottom = tk.Frame(self.window, bg=C_BG)
        bottom.pack(fill='x')

        # Progress dots
        frm_dots = tk.Frame(bottom, bg=C_BG)
        frm_dots.pack(pady=(10, 0))
        self.dots = []
        for i in range(3):
            d = tk.Label(frm_dots, text='o', font=("Segoe UI", 20), fg=C_BORDER, bg=C_BG)
            d.pack(side='left', padx=6)
            self.dots.append(d)

        # Label tamu
        tk.Label(bottom, text=f"Pendaftaran: {NAMA}  |  ID: {ID_TAMU}",
                 font=("Segoe UI", 11, "bold"), fg=C_CYAN, bg=C_BG).pack(pady=(8, 2))

        # Label status
        self.lbl_status = tk.Label(bottom, text="Posisikan wajah di dalam kotak, lalu klik Ambil Foto.",
                                   font=FONT_BIG, fg=C_TEXT, bg=C_BG, wraplength=700, justify='center')
        self.lbl_status.pack(pady=(4, 2))

        self.lbl_sub = tk.Label(bottom, text='', font=FONT_SM, fg=C_MUTED, bg=C_BG)
        self.lbl_sub.pack(pady=(0, 6))

        # Tombol
        frm_btn = tk.Frame(bottom, bg=C_BG)
        frm_btn.pack(pady=(4, 14))

        self.btn_ambil = tk.Button(frm_btn, text='Ambil Foto Sekarang', font=FONT_MED,
                                   bg=C_BLUE, fg='white', activebackground='#2563eb',
                                   relief='flat', cursor='hand2', padx=18, pady=8,
                                   command=self._manual_capture)
        self.btn_ambil.pack(side='left', padx=6)

        self.btn_ulang = tk.Button(frm_btn, text='Ulangi', font=FONT_MED,
                                   bg=C_BORDER, fg=C_TEXT, activebackground='#475569',
                                   relief='flat', cursor='hand2', padx=14, pady=8,
                                   command=self._reset)
        self.btn_ulang.pack(side='left', padx=6)

    # --- CAPTURE ---

    def _manual_capture(self):
        if self.capture_count >= 3:
            return
        self.btn_ambil.config(state='disabled')
        self._set_status(f'Mengambil foto {self.capture_count + 1} dari 3...', 'Tetap diam.', C_ORANGE)
        self.window.update()
        self.window.after(300, self._do_capture)

    def _do_capture(self):
        ret, frame = self.vid.read()
        if not ret:
            self._set_status('Kamera error!', 'Periksa koneksi webcam.', C_RED)
            self.btn_ambil.config(state='normal')
            return

        is_blur, var = is_image_blurry(frame)
        if is_blur:
            self._set_status(f'Foto GAGAL - Gambar buram (var={var:.1f})',
                             'Pastikan pencahayaan cukup, lalu coba lagi.', C_RED)
            self.btn_ambil.config(state='normal')
            return

        rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        boxes = detect_faces(rgb)

        if len(boxes) == 0:
            self._set_status(f'Foto GAGAL - Wajah tidak terdeteksi',
                             'Posisikan wajah di dalam kotak kuning.', C_RED)
            self.btn_ambil.config(state='normal')
            return

        if len(boxes) > 1:
            self._set_status(f'Foto GAGAL - Lebih dari 1 wajah terdeteksi',
                             'Hanya boleh ada 1 orang di depan kamera.', C_RED)
            self.btn_ambil.config(state='normal')
            return

        # Foto valid
        emb = get_embeddings(rgb, boxes)[0]
        self.captured_faces.append((frame, rgb, boxes))
        self.embeddings.append(emb)
        self.capture_count += 1
        self._update_dots()
        self._trigger_flash()

        if self.capture_count < 3:
            self._set_status(f'Foto {self.capture_count} dari 3 DITERIMA!',
                             f'Ubah sedikit sudut wajah, lalu klik Ambil Foto untuk foto ke-{self.capture_count + 1}.', C_GREEN)
            self.btn_ambil.config(state='normal')
        else:
            self._set_status('Semua foto terkumpul!', 'Mengirim data ke server laptop...', C_GREEN)
            self.btn_ambil.config(state='disabled')
            self.btn_ulang.config(state='disabled')
            self.window.after(600, self._process_enrollment)

    # --- ENROLLMENT ---

    def _process_enrollment(self):
        self._set_status('Memverifikasi konsistensi wajah...', 'Mohon tunggu.', C_ORANGE)
        self.window.update()

        # Consistency check
        is_cons, dists = is_consistent(self.embeddings[0], self.embeddings[1], self.embeddings[2])
        if not is_cons:
            from tkinter import messagebox
            messagebox.showwarning('Wajah Tidak Konsisten',
                                   'Sistem mendeteksi inkonsistensi antar foto.\nSilakan ulangi pendaftaran.')
            self._reset()
            return

        self._set_status('Mengirim foto + embedding ke laptop...', 'Mohon tunggu, jangan tutup jendela ini.', C_CYAN)
        self.window.update()

        # Kirim ke laptop via API
        frames_bgr = [f[0] for f in self.captured_faces]
        result = send_enrollment(ID_TAMU, frames_bgr, self.embeddings)

        from tkinter import messagebox
        if result.get('status') == 'success':
            messagebox.showinfo('Check-In Berhasil!',
                                f'Data wajah {NAMA} (ID: {ID_TAMU})\nberhasil tersimpan di database laptop!')
        else:
            messagebox.showerror('Gagal Kirim Data',
                                 f"Gagal mengirim ke laptop:\n{result.get('message', 'Unknown error')}")

        self.window.destroy()

    # --- HELPERS ---

    def _trigger_flash(self):
        self.show_flash    = True
        self.flash_counter = 6

    def _update_dots(self):
        for i, d in enumerate(self.dots):
            if i < self.capture_count:
                d.config(text='*', fg=C_GREEN)
            elif i == self.capture_count:
                d.config(text='O', fg=C_ORANGE)
            else:
                d.config(text='o', fg=C_BORDER)

    def _set_status(self, main, sub='', color=C_TEXT):
        self.lbl_status.config(text=main, fg=color)
        self.lbl_sub.config(text=sub, fg=C_MUTED)

    def _reset(self):
        self.captured_faces = []
        self.embeddings     = []
        self.capture_count  = 0
        self.show_flash     = False
        self._update_dots()
        self._set_status('Posisikan wajah di dalam kotak, lalu klik Ambil Foto.', '', C_TEXT)
        self.btn_ambil.config(state='normal')
        self.btn_ulang.config(state='normal')

    # --- CAMERA LOOP ---

    def _update_frame(self):
        ret, frame = self.vid.read()
        if ret:
            h, w  = frame.shape[:2]
            cx, cy = w // 2, h // 2

            if self.show_flash and self.flash_counter > 0:
                overlay = frame.copy()
                cv2.rectangle(overlay, (0, 0), (w, h), (0, 220, 80), -1)
                alpha = 0.35 * (self.flash_counter / 6)
                frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
                self.flash_counter -= 1
                if self.flash_counter == 0:
                    self.show_flash = False

            cv2.rectangle(frame, (cx-150, cy-195), (cx+150, cy+150), (0, 255, 100), 2)
            cv2.putText(frame, 'Posisikan Wajah Di Sini', (cx-130, cy-210),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 100), 1, cv2.LINE_AA)
            cv2.putText(frame, f'Foto: {self.capture_count}/3', (12, 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 100), 2, cv2.LINE_AA)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.photo = ImageTk.PhotoImage(image=Image.fromarray(rgb))
            self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)

        self.window.after(15, self._update_frame)


if __name__ == '__main__':
    root = tk.Tk()
    CheckInApp(root)
    root.mainloop()