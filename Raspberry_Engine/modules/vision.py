import cv2

def is_image_blurry(image, threshold=100.0):
    """
    Menghitung tingkat kekaburan gambar menggunakan metode Variance of Laplacian.
    Nilai threshold default 100 sesuai proposal Bab 3.
    Returns:
        is_blur (bool): True jika gambar kabur.
        laplacian_var (float): Nilai varians.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    is_blur = laplacian_var < threshold
    return is_blur, laplacian_var
