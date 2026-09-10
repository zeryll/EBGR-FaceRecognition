"""
E-BGR Check-Out / Verifikasi App -- Raspberry Pi Engine (Distributed Version)
Mengambil embedding dari Laptop Backend, melakukan pencocokan lokal di RPi,
lalu mengirim hasil ke Laptop Backend.
"""
import tkinter as tk
import cv2
from PIL import Image, ImageTk
import os
import sys

sys.path.append(os.path.dirname(__file__))

from modules.vision      import is_image_blurry
from modules.face_engine import detect_faces, get_embeddings, find_match
from modules.laptop_api  import get_embeddings_from_laptop, send_verification_result

# --- KONSTANTA ---
C_BG     = "#0f172a"
C_BORDER = "#334155"
C_TEXT   = "#f1f5f9"
C_MUTED  = "#94a3b8"
C_GREEN  = "#10b981"
C_ORANGE = "#f59e0b"
C_RED    = "#ef4444"
C_BLUE   = "#3b82f6"
C_CYAN   = "#22d3ee"
C_PURPLE = "#a855f7"
FONT_BIG = ("Segoe UI", 15, "bold")
FONT_MED = ("Segoe UI", 12)
FONT_SM  = ("Segoe UI", 10)

STATE_IDLE   = 'idle'
STATE_SCAN   = 'scanning'
STATE_RESULT = 'result'


class VerifikasiApp:
    def __init__(self, window):
        self.window = window
        self.window.title("E-BGR -- Verifikasi & Check-Out")
        self.window.configure(bg=C_BG)
        self.window.resizable(False, False)

        self.vid          = cv2.VideoCapture(0)
        self.state        = STATE_IDLE
        self.mode         = None
        self.matched_tamu = None
        self.show_flash   = False
        self.flash_counter = 0
        self.flash_color  = (0, 220, 80)

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

        self.lbl_status = tk.Label(bottom, text='Pilih mode operasi untuk memulai.',
                                   font=FONT_BIG, fg=C_TEXT, bg=C_BG, wraplength=700, justify='center')
        self.lbl_status.pack(pady=(10, 2))

        self.lbl_sub = tk.Label(bottom, text='', font=FONT_SM, fg=C_MUTED, bg=C_BG)
        self.lbl_sub.pack(pady=(0, 6))

        self.frm_btn = tk.Frame(bottom, bg=C_BG)
        self.frm_btn.pack(pady=(4, 14))

        self.btn_checkout = tk.Button(self.frm_btn, text='Mode Check-Out', font=FONT_MED,
                                      bg=C_ORANGE, fg='white', activebackground='#d97706',
                                      relief='flat', cursor='hand2', padx=18, pady=8,
                                      command=lambda: self._pilih_mode('checkout'))
        self.btn_checkout.pack(side='left', padx=6)

        self.btn_verify = tk.Button(self.frm_btn, text='Mode Verifikasi', font=FONT_MED,
                                    bg=C_PURPLE, fg='white', activebackground='#9333ea',
                                    relief='flat', cursor='hand2', padx=18, pady=8,
                                    command=lambda: self._pilih_mode('verify'))
        self.btn_verify.pack(side='left', padx=6)

        self.btn_scan = tk.Button(self.frm_btn, text='Scan Wajah', font=FONT_MED,
                                  bg=C_BLUE, fg='white', activebackground='#2563eb',
                                  relief='flat', cursor='hand2', padx=18, pady=8,
                                  state='disabled', command=self._do_scan)
        self.btn_scan.pack(side='left', padx=6)

        self.btn_ya = tk.Button(self.frm_btn, text='Ya, Benar', font=FONT_MED,
                                bg=C_GREEN, fg='white', activebackground='#059669',
                                relief='flat', cursor='hand2', padx=18, pady=8,
                                command=self._konfirmasi_ya)

        self.btn_tidak = tk.Button(self.frm_btn, text='Bukan Saya', font=FONT_MED,
                                   bg=C_RED, fg='white', activebackground='#dc2626',
                                   relief='flat', cursor='hand2', padx=18, pady=8,
                                   command=self._konfirmasi_tidak)

        self.btn_ulang = tk.Button(self.frm_btn, text='Ulangi', font=FONT_MED,
                                   bg=C_BORDER, fg=C_TEXT, activebackground='#475569',
                                   relief='flat', cursor='hand2', padx=14, pady=8,
                                   command=self._reset_ke_scan)

        self.btn_selesai = tk.Button(self.frm_btn, text='Kembali', font=FONT_MED,
                                     bg=C_BORDER, fg=C_TEXT, activebackground='#475569',
                                     relief='flat', cursor='hand2', padx=14, pady=8,
                                     command=self._reset_ui)

    # --- MODE ---

    def _pilih_mode(self, mode):
        self.mode  = mode
        self.state = STATE_SCAN
        self._hide_action_btns()
        self.btn_checkout.config(state='disabled')
        self.btn_verify.config(state='disabled')
        self.btn_scan.config(state='normal')
        self.btn_ulang.pack(side='left', padx=6)
        self.btn_selesai.pack(side='left', padx=6)

        if mode == 'checkout':
            self._set_status('Mode Check-Out', 'Posisikan wajah di kotak oranye, lalu klik Scan Wajah.', C_ORANGE)
        else:
            self._set_status('Mode Verifikasi', 'Posisikan wajah di kotak ungu, lalu klik Scan Wajah.', C_PURPLE)

    # --- SCAN ---

    def _do_scan(self):
        self.btn_scan.config(state='disabled')
        self._set_status('Mengambil gambar...', 'Tetap diam.', C_CYAN)
        self.window.update()
        self.window.after(350, self._capture_and_verify)

    def _capture_and_verify(self):
        ret, frame = self.vid.read()
        if not ret:
            self._set_status('Kamera error!', '', C_RED)
            self.btn_scan.config(state='normal')
            return

        is_blur, var = is_image_blurry(frame)
        if is_blur:
            self._set_status(f'Gambar buram (var={var:.1f})', 'Pastikan pencahayaan cukup.', C_RED)
            self.btn_scan.config(state='normal')
            return

        rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        boxes = detect_faces(rgb)

        if len(boxes) == 0:
            self._set_status('Wajah tidak terdeteksi', 'Posisikan wajah di dalam kotak.', C_RED)
            self.btn_scan.config(state='normal')
            return
        if len(boxes) > 1:
            self._set_status('Lebih dari 1 wajah', 'Hanya 1 orang di depan kamera.', C_RED)
            self.btn_scan.config(state='normal')
            return

        self._set_status('Memverifikasi identitas...', 'Mengambil data embedding dari laptop...', C_CYAN)
        self.window.update()

        target_emb = get_embeddings(rgb, boxes)[0]

        # Ambil embedding dari laptop
        db_records = get_embeddings_from_laptop()
        if not db_records:
            self._set_status('Tidak ada data embedding dari laptop',
                             'Pastikan laptop server berjalan dan ada tamu yang check-in.', C_ORANGE)
            self.btn_scan.config(state='normal')
            return

        is_match, best_match, min_dist = find_match(target_emb, db_records, threshold=0.6)

        self.state = STATE_RESULT
        self._show_result(is_match, best_match, min_dist)

    # --- RESULT ---

    def _show_result(self, is_match, best_match, min_dist):
        self._hide_action_btns()
        self.btn_scan.config(state='disabled')

        if is_match:
            self.matched_tamu = best_match
            pct = max(0, int((1 - min_dist) * 100))
            self._trigger_flash((0, 220, 80))

            if self.mode == 'checkout':
                self._set_status(f'Wajah Dikenali: {best_match["nama"]}',
                                 f'ID: {best_match["id_tamu"]}  Kecocokan: {pct}%  Konfirmasi identitas:', C_GREEN)
                self.btn_ya.pack(side='left', padx=6)
                self.btn_tidak.pack(side='left', padx=6)
            else:
                status_str = best_match.get('status', '-').replace('-', ' ').title()
                self._set_status(f'Identitas Dikenali: {best_match["nama"]}',
                                 f'ID: {best_match["id_tamu"]}  Status: {status_str}  Kecocokan: {pct}%', C_GREEN)
                self.btn_ulang.pack(side='left', padx=6)
                self.btn_selesai.pack(side='left', padx=6)
        else:
            self._trigger_flash((200, 30, 30))
            self._set_status('Wajah Tidak Dikenali',
                             'Tidak ditemukan wajah yang cocok di database.', C_RED)
            self.btn_ulang.pack(side='left', padx=6)
            self.btn_selesai.pack(side='left', padx=6)

    # --- KONFIRMASI CHECKOUT ---

    def _konfirmasi_ya(self):
        if not self.matched_tamu:
            return
        self._hide_action_btns()
        self._set_status('Mengirim hasil ke server laptop...', 'Mohon tunggu.', C_CYAN)
        self.window.update()

        result = send_verification_result(self.matched_tamu['id_tamu'], 'success',
                                          self.matched_tamu.get('min_dist', 0))
        self._trigger_flash((0, 220, 80))

        if result.get('status') == 'success':
            self._set_status(f'Check-Out Berhasil! Terima kasih, {self.matched_tamu["nama"]}',
                             f'ID: {self.matched_tamu["id_tamu"]}  Data diperbarui di server.', C_GREEN)
        else:
            self._set_status('Terhubung gagal ke laptop',
                             f"Error: {result.get('message')}", C_ORANGE)

        self.window.after(3000, self._reset_ui)

    def _konfirmasi_tidak(self):
        self._hide_action_btns()
        self._set_status('Check-Out Dibatalkan', 'Identitas tidak dikonfirmasi.', C_RED)
        self.window.after(1800, self._reset_ke_scan)

    # --- HELPERS ---

    def _trigger_flash(self, color=(0, 220, 80)):
        self.flash_color   = color
        self.show_flash    = True
        self.flash_counter = 8

    def _set_status(self, main, sub='', color=C_TEXT):
        self.lbl_status.config(text=main, fg=color)
        self.lbl_sub.config(text=sub, fg=C_MUTED)

    def _hide_action_btns(self):
        for b in (self.btn_ya, self.btn_tidak, self.btn_ulang, self.btn_selesai):
            b.pack_forget()

    def _reset_ke_scan(self):
        self.state = STATE_SCAN
        self.matched_tamu = None
        self._hide_action_btns()
        self.btn_ulang.pack(side='left', padx=6)
        self.btn_selesai.pack(side='left', padx=6)
        self.btn_scan.config(state='normal')
        if self.mode == 'checkout':
            self._set_status('Siap Scan Ulang', 'Klik Scan Wajah untuk mencoba lagi.', C_ORANGE)
        else:
            self._set_status('Siap Scan Ulang', 'Klik Scan Wajah untuk mencoba lagi.', C_PURPLE)

    def _reset_ui(self):
        self.state = STATE_IDLE
        self.mode  = None
        self.matched_tamu = None
        self._hide_action_btns()
        self.btn_checkout.config(state='normal')
        self.btn_verify.config(state='normal')
        self.btn_scan.config(state='disabled')
        self._set_status('Pilih mode operasi untuk memulai.', '', C_TEXT)

    # --- CAMERA LOOP ---

    def _update_frame(self):
        ret, frame = self.vid.read()
        if ret:
            h, w   = frame.shape[:2]
            cx, cy = w // 2, h // 2

            if self.show_flash and self.flash_counter > 0:
                overlay = frame.copy()
                r, g, b = self.flash_color
                cv2.rectangle(overlay, (0, 0), (w, h), (b, g, r), -1)
                alpha = 0.4 * (self.flash_counter / 8)
                frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
                self.flash_counter -= 1
                if self.flash_counter == 0:
                    self.show_flash = False

            if self.state != STATE_IDLE:
                col = (30, 165, 255) if self.mode == 'checkout' else (200, 100, 255)
                cv2.rectangle(frame, (cx-150, cy-195), (cx+150, cy+150), col, 2)
                cv2.putText(frame, 'Posisikan Wajah Di Sini', (cx-130, cy-210),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 1, cv2.LINE_AA)
                label = 'CHECK-OUT' if self.mode == 'checkout' else 'VERIFIKASI'
                cv2.putText(frame, label, (12, 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2, cv2.LINE_AA)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.photo = ImageTk.PhotoImage(image=Image.fromarray(rgb))
            self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)

        self.window.after(15, self._update_frame)


if __name__ == '__main__':
    root = tk.Tk()
    VerifikasiApp(root)
    root.mainloop()