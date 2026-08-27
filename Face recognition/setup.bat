@echo off
echo ========================================
echo SKRIPSI FACE RECOGNITION - SETUP
echo ========================================
echo.
echo [1/5] Creating Virtual Environment...
python -m venv venv
if %errorlevel% neq 0 (
    echo ERROR: Python not found! Install Python first.
    pause
    exit /b 1
)

echo [2/5] Activating Virtual Environment...
call venv\Scripts\activate.bat

echo [3/5] Upgrade pip...
python -m pip install --upgrade pip

echo [4/5] Installing base packages...
pip install numpy opencv-python cmake

echo [5/5] Setup COMPLETE! ✅
echo.
echo Selanjutnya jalankan: install_dlib.bat
echo.
pause