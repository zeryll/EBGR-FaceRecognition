import cv2

def is_image_blurry(image, threshold=100.0):
    """
    Menghitung tingkat kekaburan gambar menggunakan metode Variance of Laplacian.
    Sesuai dengan proposal Bab 3, nilai threshold default adalah 100.
    
    Args:
        image: Frame gambar dari OpenCV (numpy array BGR)
        threshold: Batas bawah nilai varians (default 100.0). Jika di bawah ini, dianggap blur.
        
    Returns:
        is_blur (bool): True jika gambar kabur, False jika fokus.
        laplacian_var (float): Nilai varians yang dihitung.
    """
    # Ubah gambar ke grayscale untuk perhitungan Laplacian
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Hitung varians dari hasil operasi Laplacian
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    # Jika nilai varians lebih kecil dari threshold, gambar dianggap kabur (blur)
    is_blur = laplacian_var < threshold
    
    return is_blur, laplacian_var
