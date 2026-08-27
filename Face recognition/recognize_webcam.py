import face_recognition
import pickle
import cv2
import time

print("[INFO] memuat encodings...")
try:
    with open("encodings.pickle", "rb") as f:
        data = pickle.loads(f.read())
except FileNotFoundError:
    print("[ERROR] File encodings.pickle tidak ditemukan.")
    print("Silakan jalankan 'python encode_faces.py' terlebih dahulu setelah memasukkan foto ke folder dataset.")
    exit()

print("[INFO] memulai video stream dari webcam...")
# Membuka webcam (index 0 adalah webcam default laptop)
video_capture = cv2.VideoCapture(0)

if not video_capture.isOpened():
    print("[ERROR] Tidak dapat membuka webcam. Pastikan webcam tidak sedang digunakan oleh aplikasi lain.")
    exit()

# Tunggu sebentar agar sensor kamera menyesuaikan cahaya
time.sleep(2.0)

# Variabel untuk processing secara bergantian frame demi frame (agar tidak lag)
process_this_frame = True
face_locations = []
face_encodings = []
face_names = []

print("[INFO] Tekan 'q' pada jendela video untuk keluar.")

while True:
    # Membaca 1 frame video
    ret, frame = video_capture.read()
    if not ret:
        print("[ERROR] Gagal membaca frame dari webcam.")
        break
        
    # Perkecil ukuran frame menjadi 1/4 agar pemrosesan wajah lebih cepat
    small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
    
    # Konversi gambar dari format BGR (bawaan OpenCV) ke RGB (bawaan face_recognition)
    rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

    if process_this_frame:
        # Cari semua wajah di dalam frame saat ini menggunakan HOG
        face_locations = face_recognition.face_locations(rgb_small_frame, model="hog")
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

        face_names = []
        for face_encoding in face_encodings:
            # Cocokkan wajah yang terdeteksi dengan wajah yang sudah dikenal
            matches = face_recognition.compare_faces(data["encodings"], face_encoding, tolerance=0.5)
            name = "Unknown"

            # Jika ada yang cocok, gunakan nama yang paling banyak cocok
            if True in matches:
                matchedIdxs = [i for (i, b) in enumerate(matches) if b]
                counts = {}
                for i in matchedIdxs:
                    name = data["names"][i]
                    counts[name] = counts.get(name, 0) + 1
                name = max(counts, key=counts.get)
            
            face_names.append(name)

    # Ubah nilai kebalikannya, jika True jadi False, dst. (Skip 1 frame)
    process_this_frame = not process_this_frame

    # Tampilkan kotak di sekitar wajah yang terdeteksi
    for (top, right, bottom, left), name in zip(face_locations, face_names):
        # Kembalikan skala koordinat ke ukuran aslinya (karena tadi diperkecil 1/4)
        top *= 4
        right *= 4
        bottom *= 4
        left *= 4

        # Gambar kotak wajah (warna hijau BGR: 0, 255, 0)
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)

        # Gambar kotak label nama di bagian bawah wajah
        cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 255, 0), cv2.FILLED)
        font = cv2.FONT_HERSHEY_DUPLEX
        cv2.putText(frame, name, (left + 6, bottom - 6), font, 1.0, (255, 255, 255), 1)

    # Tampilkan video
    cv2.imshow('Face Recognition Skripsi', frame)

    # Jika tombol 'q' ditekan, keluar dari loop
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Bersihkan dan matikan kamera
video_capture.release()
cv2.destroyAllWindows()
