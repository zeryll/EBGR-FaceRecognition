@echo off
echo ========================================
echo INSTALLING DLIB DAN FACE_RECOGNITION
echo ========================================
echo.
call venv\Scripts\activate.bat
echo Installing dlib (ini akan memakan waktu cukup lama karena sedang di-compile)...
pip install dlib
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Gagal menginstal dlib! Pastikan Visual Studio C++ Build Tools sudah terinstal.
    pause
    exit /b 1
)
echo Installing face_recognition...
pip install face_recognition imutils pillow matplotlib
echo.
echo ========================================
echo SEMUA LIBRARY BERHASIL DIINSTAL! ✅
echo ========================================
pause
