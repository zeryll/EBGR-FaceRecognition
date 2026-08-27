import tkinter as tk
from tkinter import messagebox
import cv2
from PIL import Image, ImageTk
import os
import json
import numpy as np
import sys

sys.path.append(os.path.dirname(__file__))

from modules.database import get_connection
from modules.vision import is_image_blurry
from modules.face_engine import detect_faces, get_embeddings, find_match
from modules.mqtt_client import publish_checkout

# ─────────────────────────────────────────────
#  Warna & Font (sama dengan app_checkin.py)
# ─────────────────────────────────────────────
C_BG     = "#0f172a"
C_PANEL  = "#1e293b"
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


# ─────────────────────────────────────────────────────────────────
#  State mesin
#  idle → mode_pilih → scanning → result_checkout / result_verify
# ─────────────────────────────────────────────────────────────────
STATE_IDLE    = "idle"
STATE_SCAN    = "scanning"
STATE_RESULT  = "result"


class VerifikasiApp:
    def __init__(self, window):
        self.window = window
        self.window.title("E-BGR — Verifikasi & Check-Out")
        self.window.configure(bg=C_BG)
        self.window.resizable(False, False)

        # State
        self.vid           = cv2.VideoCapture(0)
        self.state         = STATE_IDLE
        self.mode          = None          # 'checkout' | 'verify'
        self.matched_tamu  = None
        self.show_flash    = False
        self.flash_counter = 0
        self.flash_color   = (0, 220, 80)  # green by default

        self._build_ui()
        self._update_frame()

    # ─────────────── BUILD UI ───────────────

    def _build_ui(self):
        CAM_W = int(self.vid.get(cv2.CAP_PROP_FRAME_WIDTH))
        CAM_H = int(self.vid.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Canvas kamera
        self.canvas = tk.Canvas(
            self.window, width=CAM_W, height=CAM_H,
            bg="black", highlightthickness=0
        )
        self.canvas.pack()

        # Panel bawah
        self.bottom = tk.Frame(self.window, bg=C_BG)
        self.bottom.pack(fill="x", padx=0, pady=0)

        # Label status utama
        self.lbl_status = tk.Label(
            self.bottom,
            text="Pilih mode operasi untuk memulai.",
            font=FONT_BIG, fg=C_TEXT, bg=C_BG,
            wraplength=700, justify="center"
        )
        self.lbl_status.pack(pady=(10, 2))

        # Label sub-status
        self.lbl_sub = tk.Label(
            self.bottom, text="",
            font=FONT_SM, fg=C_MUTED, bg=C_BG
        )
        self.lbl_sub.pack(pady=(0, 6))

        # ── Baris tombol ──
        self.frm_btn = tk.Frame(self.bottom, bg=C_BG)
        self.frm_btn.pack(pady=(4, 14))

        # Tombol 1: Check-Out
        self.btn_checkout = tk.Button(
            self.frm_btn,
            text="🚪  Mode Check-Out",
            font=FONT_MED,
            bg=C_ORANGE, fg="white",
            activebackground="#d97706", activeforeground="white",
            relief="flat", cursor="hand2",
            padx=18, pady=8,
            command=lambda: self._pilih_mode("checkout")
        )
        self.btn_checkout.pack(side="left", padx=6)

        # Tombol 2: Verifikasi Wajah
        self.btn_verify = tk.Button(
            self.frm_btn,
            text="🔍  Mode Verifikasi Wajah",
            font=FONT_MED,
            bg=C_PURPLE, fg="white",
            activebackground="#9333ea", activeforeground="white",
            relief="flat", cursor="hand2",
            padx=18, pady=8,
            command=lambda: self._pilih_mode("verify")
        )
        self.btn_verify.pack(side="left", padx=6)

        # Tombol 3: Scan Wajah (muncul saat mode sudah dipilih)
        self.btn_scan = tk.Button(
            self.frm_btn,
            text="📷  Scan Wajah Sekarang",
            font=FONT_MED,
            bg=C_BLUE, fg="white",
            activebackground="#2563eb", activeforeground="white",
            relief="flat", cursor="hand2",
            padx=18, pady=8,
            state="disabled",
            command=self._do_scan
        )
        self.btn_scan.pack(side="left", padx=6)

        # Tombol 4: Konfirmasi YA (checkout)
        self.btn_ya = tk.Button(
            self.frm_btn,
            text="✅  Ya, Benar",
            font=FONT_MED,
            bg=C_GREEN, fg="white",
            activebackground="#059669", activeforeground="white",
            relief="flat", cursor="hand2",
            padx=18, pady=8,
            command=self._konfirmasi_ya
        )

        # Tombol 5: Konfirmasi TIDAK (checkout)
        self.btn_tidak = tk.Button(
            self.frm_btn,
            text="❌  Bukan Saya",
            font=FONT_MED,
            bg=C_RED, fg="white",
            activebackground="#dc2626", activeforeground="white",
            relief="flat", cursor="hand2",
            padx=18, pady=8,
            command=self._konfirmasi_tidak
        )

        # Tombol 6: Ulangi / Scan Lagi
        self.btn_ulang = tk.Button(
            self.frm_btn,
            text="🔄  Ulangi",
            font=FONT_MED,
            bg=C_BORDER, fg=C_TEXT,
            activebackground="#475569", activeforeground="white",
            relief="flat", cursor="hand2",
            padx=14, pady=8,
            command=self._reset_ke_scan
        )

        # Tombol 7: Selesai / Kembali ke mode pilih
        self.btn_selesai = tk.Button(
            self.frm_btn,
            text="↩  Kembali",
            font=FONT_MED,
            bg=C_BORDER, fg=C_TEXT,
            activebackground="#475569", activeforeground="white",
            relief="flat", cursor="hand2",
            padx=14, pady=8,
            command=self._reset_ui
        )

    # ─────────────── PILIH MODE ───────────────

    def _pilih_mode(self, mode):
        self.mode  = mode
        self.state = STATE_SCAN

        self._hide_all_action_btns()
        self.btn_checkout.config(state="disabled")
        self.btn_verify.config(state="disabled")
        self.btn_scan.config(state="normal")
        self.btn_ulang.pack(side="left", padx=6)
        self.btn_selesai.pack(side="left", padx=6)

        if mode == "checkout":
            self._set_status(
                "🚪  Mode Check-Out Aktif",
                "Posisikan wajah Anda di dalam kotak, lalu klik  📷 Scan Wajah Sekarang.",
                C_ORANGE
            )
        else:
            self._set_status(
                "🔍  Mode Verifikasi Wajah Aktif",
                "Posisikan wajah di dalam kotak, lalu klik  📷 Scan Wajah Sekarang.",
                C_PURPLE
            )

    # ─────────────── SCAN MANUAL ───────────────

    def _do_scan(self):
        self.btn_scan.config(state="disabled")
        self._set_status("📷  Mengambil gambar...", "Tetap diam sejenak.", C_CYAN)
        self.window.update()
        self.window.after(350, self._capture_and_verify)

    def _capture_and_verify(self):
        ret, frame = self.vid.read()
        if not ret:
            self._set_status("❌  Kamera tidak terbaca!", "Periksa koneksi kamera.", C_RED)
            self.btn_scan.config(state="normal")
            return

        # Validasi blur
        is_blur, var = is_image_blurry(frame)
        if is_blur:
            self._set_status(
                f"❌  Gambar terlalu buram (var={var:.1f})",
                "Pastikan pencahayaan cukup dan kamera tidak bergerak. Coba lagi.",
                C_RED
            )
            self.btn_scan.config(state="normal")
            return

        rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        boxes = detect_faces(rgb)

        if len(boxes) == 0:
            self._set_status(
                "❌  Wajah tidak terdeteksi",
                "Pastikan wajah Anda berada di dalam kotak panduan.",
                C_RED
            )
            self.btn_scan.config(state="normal")
            return

        if len(boxes) > 1:
            self._set_status(
                "❌  Terdeteksi lebih dari 1 wajah",
                "Pastikan hanya ada 1 orang di depan kamera.",
                C_RED
            )
            self.btn_scan.config(state="normal")
            return

        # Wajah valid — proses pengenalan
        self._set_status("⚙️  Memverifikasi identitas (ResNet-29)...", "Mohon tunggu...", C_CYAN)
        self.window.update()

        target_emb = get_embeddings(rgb, boxes)[0]

        conn = get_connection()
        c    = conn.cursor()
        if self.mode == "checkout":
            c.execute(
                "SELECT id_tamu, nama, status, embedding_1, embedding_2, embedding_3 "
                "FROM tamu WHERE status='checked-in'"
            )
        else:
            c.execute(
                "SELECT id_tamu, nama, status, embedding_1, embedding_2, embedding_3 FROM tamu"
            )
        rows = c.fetchall()
        conn.close()

        db_records = []
        for r in rows:
            embs = []
            for col in (r[3], r[4], r[5]):
                if col:
                    embs.append(json.loads(col))
            db_records.append({"id_tamu": r[0], "nama": r[1], "status": r[2], "embeddings": embs})

        is_match, best_match, min_dist = find_match(target_emb, db_records, threshold=0.6)

        self.state = STATE_RESULT
        self._show_result(is_match, best_match, min_dist)

    # ─────────────── TAMPILKAN HASIL ───────────────

    def _show_result(self, is_match, best_match, min_dist):
        self._hide_all_action_btns()
        # Sembunyikan scan button
        self.btn_scan.config(state="disabled")

        if is_match:
            self.matched_tamu = best_match
            dist_pct          = max(0, int((1 - min_dist) * 100))

            # Efek flash hijau
            self._trigger_flash((0, 220, 80))

            if self.mode == "checkout":
                self._set_status(
                    f"✅  Wajah Dikenali:  {best_match['nama']}",
                    f"ID: {best_match['id_tamu']}  ·  Tingkat kecocokan: {dist_pct}%  ·  Konfirmasi identitas Anda:",
                    C_GREEN
                )
                self.btn_ya.pack(side="left", padx=6)
                self.btn_tidak.pack(side="left", padx=6)

            else:  # verify
                status_str = best_match.get("status", "-").replace("-", " ").title()
                self._set_status(
                    f"✅  Identitas Dikenali:  {best_match['nama']}",
                    f"ID: {best_match['id_tamu']}  ·  Status: {status_str}  ·  Kecocokan: {dist_pct}%",
                    C_GREEN
                )
                self.btn_selesai.pack(side="left", padx=6)
                self.btn_ulang.pack(side="left", padx=6)

        else:
            # Efek flash merah
            self._trigger_flash((200, 30, 30))
            self._set_status(
                "❌  Wajah Tidak Dikenali",
                "Wajah Anda tidak ditemukan di dalam database E-BGR." if self.mode == "verify"
                else "Tidak ditemukan tamu yang sedang check-in dengan wajah tersebut.",
                C_RED
            )
            self.btn_ulang.pack(side="left", padx=6)
            self.btn_selesai.pack(side="left", padx=6)

    # ─────────────── KONFIRMASI CHECK-OUT ───────────────

    def _konfirmasi_ya(self):
        if not self.matched_tamu:
            return

        conn = get_connection()
        c    = conn.cursor()
        c.execute(
            "UPDATE tamu SET status='checked-out', checked_out_at=CURRENT_TIMESTAMP WHERE id_tamu=?",
            (self.matched_tamu["id_tamu"],)
        )
        c.execute(
            "INSERT INTO log_verifikasi (id_tamu, tipe_event, status_verifikasi) VALUES (?, 'check-out', 'success')",
            (self.matched_tamu["id_tamu"],)
        )
        conn.commit()
        conn.close()

        publish_checkout(self.matched_tamu["id_tamu"], self.matched_tamu["nama"])

        self._hide_all_action_btns()
        self._trigger_flash((0, 220, 80))
        self._set_status(
            f"✅  Check-Out Berhasil!  Terima kasih, {self.matched_tamu['nama']} 👋",
            f"ID: {self.matched_tamu['id_tamu']}  ·  Data telah diperbarui di database.",
            C_GREEN
        )
        self.window.after(3000, self._reset_ui)

    def _konfirmasi_tidak(self):
        self._hide_all_action_btns()
        self._set_status(
            "⚠️  Check-Out Dibatalkan",
            "Identitas tidak dikonfirmasi. Silakan coba scan ulang.",
            C_RED
        )
        self.window.after(1800, self._reset_ke_scan)

    # ─────────────── HELPERS ───────────────

    def _trigger_flash(self, color=(0, 220, 80)):
        self.flash_color   = color
        self.show_flash    = True
        self.flash_counter = 8

    def _set_status(self, main, sub="", color=C_TEXT):
        self.lbl_status.config(text=main, fg=color)
        self.lbl_sub.config(text=sub, fg=C_MUTED)

    def _hide_all_action_btns(self):
        for btn in (self.btn_ya, self.btn_tidak, self.btn_ulang, self.btn_selesai):
            btn.pack_forget()

    def _reset_ke_scan(self):
        """Kembali ke state scan dalam mode yang sama (tidak ganti mode)."""
        self.state        = STATE_SCAN
        self.matched_tamu = None
        self._hide_all_action_btns()

        if self.mode == "checkout":
            self.btn_ulang.pack(side="left", padx=6)
            self.btn_selesai.pack(side="left", padx=6)
            self._set_status(
                "🚪  Mode Check-Out — Siap Scan",
                "Posisikan wajah di dalam kotak, lalu klik  📷 Scan Wajah Sekarang.",
                C_ORANGE
            )
        else:
            self.btn_ulang.pack(side="left", padx=6)
            self.btn_selesai.pack(side="left", padx=6)
            self._set_status(
                "🔍  Mode Verifikasi — Siap Scan",
                "Posisikan wajah di dalam kotak, lalu klik  📷 Scan Wajah Sekarang.",
                C_PURPLE
            )
        self.btn_scan.config(state="normal")

    def _reset_ui(self):
        """Kembali ke layar pilih mode."""
        self.state        = STATE_IDLE
        self.mode         = None
        self.matched_tamu = None

        self._hide_all_action_btns()
        self.btn_checkout.config(state="normal")
        self.btn_verify.config(state="normal")
        self.btn_scan.config(state="disabled")

        self._set_status("Pilih mode operasi untuk memulai.", "", C_TEXT)

    # ─────────────── CAMERA LOOP ───────────────

    def _update_frame(self):
        ret, frame = self.vid.read()
        if ret:
            h, w  = frame.shape[:2]
            cx, cy = w // 2, h // 2

            # Flash effect
            if self.show_flash and self.flash_counter > 0:
                overlay = frame.copy()
                r, g, b = self.flash_color
                cv2.rectangle(overlay, (0, 0), (w, h), (b, g, r), -1)  # BGR
                alpha = 0.4 * (self.flash_counter / 8)
                frame = cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)
                self.flash_counter -= 1
                if self.flash_counter == 0:
                    self.show_flash = False

            # Kotak panduan wajah
            if self.state != STATE_IDLE:
                if self.mode == "checkout":
                    box_color = (30, 165, 255)   # oranye BGR
                elif self.mode == "verify":
                    box_color = (200, 100, 255)  # ungu BGR
                else:
                    box_color = (0, 220, 255)

                cv2.rectangle(frame,
                              (cx - 150, cy - 195), (cx + 150, cy + 150),
                              box_color, 2)
                cv2.putText(frame, "Posisikan Wajah Di Sini",
                            (cx - 130, cy - 210),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, box_color, 1, cv2.LINE_AA)

                # Label mode di sudut kiri atas
                mode_label = "CHECK-OUT" if self.mode == "checkout" else "VERIFIKASI"
                cv2.putText(frame, mode_label, (12, 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, box_color, 2, cv2.LINE_AA)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.photo = ImageTk.PhotoImage(image=Image.fromarray(rgb))
            self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)

        self.window.after(15, self._update_frame)


if __name__ == "__main__":
    root = tk.Tk()
    app  = VerifikasiApp(root)
    root.mainloop()
