@echo off
chcp 65001 >nul
REM ============================================================
REM  OYTS - Backend + Frontend Durdur (Kamerayi Serbest Birak)
REM ============================================================
REM  Bu dosyaya cift tikla:
REM    - Backend (web_app.py) sonlandirilir -> kamera serbest
REM    - Frontend (serve.py) sonlandirilir
REM    - 5050 ve 8765 portlarini dinleyen ne varsa kapatilir
REM
REM  Kamera kapatilamiyorsa (driver kilidi): Bilgisayari yeniden
REM  baslatmak son care. Genelde stop.bat yeter.
REM ============================================================
setlocal
cd /d "%~dp0"

set BACKEND_PORT=5050
set FRONTEND_PORT=8765

echo ============================================================
echo  OYTS Durduruluyor
echo ============================================================
echo.

echo [1/3] Backend (web_app.py) sonlandiriliyor...
wmic process where "name='python.exe' and commandline like '%%web_app.py%%'" delete >nul 2>nul
if errorlevel 1 (
    echo       (calisan backend bulunamadi)
) else (
    echo       OK - kamera serbest birakildi
)

echo [2/3] Frontend (serve.py) sonlandiriliyor...
wmic process where "name='python.exe' and commandline like '%%serve.py%%'" delete >nul 2>nul
if errorlevel 1 (
    echo       (calisan frontend bulunamadi)
) else (
    echo       OK
)

echo [3/3] %BACKEND_PORT% ve %FRONTEND_PORT% portlarindaki artiklar temizleniyor...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%BACKEND_PORT% ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>nul
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%FRONTEND_PORT% ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>nul
)
echo       OK

echo.
echo ============================================================
echo  Hepsi durduruldu. Kamera artik baska uygulamalar tarafindan
echo  kullanilabilir.
echo ============================================================
timeout /t 3
endlocal
