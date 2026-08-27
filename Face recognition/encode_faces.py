import face_recognition
import pickle
import cv2
import os

print("[INFO] mengkuantifikasi wajah...")
imagePaths = []
dataset_path = "dataset"

if not os.path.exists(dataset_path):
    print(f"[ERROR] Folder {dataset_path} tidak ditemukan!")
    exit()

for filename in os.listdir(dataset_path):
    if filename.endswith(".jpg") or filename.endswith(".png") or filename.endswith(".jpeg"):
        imagePaths.append(os.path.join(dataset_path, filename))

if len(imagePaths) == 0:
    print(f"[ERROR] Tidak ada gambar (jpg/png) di dalam folder {dataset_path}.")
    print("Masukkan setidaknya 1 foto wajah Anda ke dalam folder tersebut dengan format nama Anda, contoh: denzel.jpg")
    exit()

knownEncodings = []
knownNames = []

for (i, imagePath) in enumerate(imagePaths):
    print(f"[INFO] memproses gambar {i + 1}/{len(imagePaths)}: {imagePath}")
    # Ambil nama orang dari nama file (misal: denzel.jpg -> denzel)
    name = imagePath.split(os.path.sep)[-1].rsplit(".", 1)[0]
    
    image = cv2.imread(imagePath)
    if image is None:
        print(f"[WARNING] Tidak dapat membaca {imagePath}")
        continue
        
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    # Deteksi letak wajah menggunakan HOG
    boxes = face_recognition.face_locations(rgb, model="hog")
    
    # Ekstrak fitur wajah
    encodings = face_recognition.face_encodings(rgb, boxes)
    
    for encoding in encodings:
        knownEncodings.append(encoding)
        knownNames.append(name)

if len(knownEncodings) == 0:
    print("[WARNING] Tidak ada wajah yang terdeteksi di foto-foto tersebut.")
else:
    print("[INFO] serialisasi encodings...")
    data = {"encodings": knownEncodings, "names": knownNames}
    with open("encodings.pickle", "wb") as f:
        f.write(pickle.dumps(data))
    print(f"[INFO] selesai. {len(knownEncodings)} wajah terdaftar.")
