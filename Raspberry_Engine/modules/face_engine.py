import face_recognition
import numpy as np

def detect_faces(rgb_image):
    """Mendeteksi lokasi wajah menggunakan HOG (ringan, cocok untuk RPi)."""
    return face_recognition.face_locations(rgb_image, model="hog")

def get_embeddings(rgb_image, boxes):
    """Mengekstrak 128-D embedding wajah menggunakan ResNet Dlib."""
    return face_recognition.face_encodings(rgb_image, boxes)

def is_consistent(emb1, emb2, emb3, threshold=0.4):
    """
    Consistency check: memastikan 3 foto berasal dari orang yang sama.
    Jarak Euclidean antar ketiganya harus < threshold (0.4).
    """
    e1, e2, e3 = np.array(emb1), np.array(emb2), np.array(emb3)
    d12 = np.linalg.norm(e1 - e2)
    d13 = np.linalg.norm(e1 - e3)
    d23 = np.linalg.norm(e2 - e3)
    if d12 >= threshold or d13 >= threshold or d23 >= threshold:
        return False, (d12, d13, d23)
    return True, (d12, d13, d23)

def find_match(target_embedding, db_records, threshold=0.6):
    """
    Mencocokkan wajah target dengan semua embedding di database.
    db_records: list of { id_tamu, nama, status, embeddings: [[...], [...], [...]] }
    Returns: (is_match, best_match_record, min_distance)
    """
    target = np.array(target_embedding)
    min_dist = float('inf')
    best = None
    for rec in db_records:
        for emb in rec.get('embeddings', []):
            if emb is None:
                continue
            dist = np.linalg.norm(target - np.array(emb))
            if dist < min_dist:
                min_dist = dist
                best = rec
    if min_dist < threshold:
        return True, best, min_dist
    return False, None, min_dist
