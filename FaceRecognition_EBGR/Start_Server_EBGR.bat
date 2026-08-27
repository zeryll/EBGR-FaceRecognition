@echo off
echo ============================================================
echo   E-BGR SERVER LOKAL  
echo   Setelah server berjalan, buka browser: http://localhost:5000
echo ============================================================
echo.
call "..\Face recognition\venv\Scripts\activate.bat"
python server.py
pause
