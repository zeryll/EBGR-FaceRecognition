import face_recognition
import numpy as np

def detect_faces(rgb_image):
    """
    Mencari lokasi wajah pada gambar menggunakan metode HOG.
    Sesuai kesepakatan, HOG digunakan agar ringan dan realtime di CPU/Raspberry Pi.
    """
    # Mengembalikan list of tuples (top, right, bottom, left)
    return face_recognition.face_locations(rgb_image, model="hog")

def get_embeddings(rgb_image, boxes):
    """
    Mengekstrak 128-dimensional fitur wajah menggunakan model CNN ResNet Dlib.
    """
    return face_recognition.face_encodings(rgb_image, boxes)

def is_consistent(emb1, emb2, emb3, threshold=0.4):
    """
    Consistency Check (Sesuai Proposal Bab 3):
    Memastikan bahwa 3 foto yang diambil saat Check-In berasal dari wajah orang yang sama.
    Jarak Euclidean antar ketiganya harus di bawah threshold (0.4).
    """
    # Konversi ke numpy array agar perhitungan vektor lebih cepat
    emb1 = np.array(emb1)
    emb2 = np.array(emb2)
    emb3 = np.array(emb3)
    
    # Hitung jarak (Euclidean Distance)
    dist_1_2 = np.linalg.norm(emb1 - emb2)
    dist_1_3 = np.linalg.norm(emb1 - emb3)
    dist_2_3 = np.linalg.norm(emb2 - emb3)
    
    # Jika ada satu saja jarak yang melebihi 0.4, berarti TIDAK KONSISTEN
    if dist_1_2 >= threshold or dist_1_3 >= threshold or dist_2_3 >= threshold:
        return False, (dist_1_2, dist_1_3, dist_2_3)
    
    return True, (dist_1_2, dist_1_3, dist_2_3)

def find_match(target_embedding, db_records, threshold=0.6):
    """
    Face Matching (Sesuai Proposal Bab 3):
    Mencocokkan tamu yang sedang Check-Out dengan data di database.
    
    Args:
        target_embedding: 128-D vector milik tamu yang ada di depan kamera
        db_records: list of dictionaries berisi data tamu dari database, contoh:
                    [{'id_tamu': 'T001', 'nama': 'Denzel', 'embeddings': [emb1, emb2, emb3]}, ...]
        threshold: Batas toleransi jarak Euclidean (0.6)
        
    Returns:
        match_found (bool): True jika ada yang cocok, False jika tidak
        best_match (dict): Data tamu yang paling cocok
        min_distance (float): Nilai jarak terkecil
    """
    target = np.array(target_embedding)
    min_distance = float('inf')
    best_match = None
    
    for record in db_records:
        for db_emb in record['embeddings']:
            if db_emb is None:
                continue
                
            db_emb_np = np.array(db_emb)
            dist = np.linalg.norm(target - db_emb_np)
            
            if dist < min_distance:
                min_distance = dist
                best_match = record
                
    if min_distance < threshold:
        return True, best_match, min_distance
    else:
        return False, None, min_distance
