@echo off
chcp 65001 >nul
REM ============================================================
REM  OYTS - Simulation Modu (Synthetic Fire)
REM ============================================================
REM  Bu dosyaya cift tikla:
REM    - Eski backend/frontend process'leri temizler
REM    - Backend baslatir (synthetic kaynak, port 5050)
REM    - Frontend baslatir (static server, port 8765)
REM    - Tarayicida live.html acar
REM
REM  Kameraya gerek YOK - sentetik yangin sahnesi uretilir.
REM
REM  Durdurmak icin: stop.bat dosyasina cift tikla
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

set REPO_ROOT=%~dp0
set PYTHON_DIR=%REPO_ROOT%python
set WEB_DIR=%REPO_ROOT%web
set BACKEND_PORT=5050
set FRONTEND_PORT=8765
set LOG_DIR=%TEMP%\oyts_demo
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM --- Python tespiti ---
where python >nul 2>nul
if errorlevel 1 (
    echo [HATA] Python bulunamadi. https://www.python.org/downloads/ uzerinden 3.10+ kurun.
    echo Kurulum sirasinda "Add Python to PATH" kutusunu isaretleyin.
    pause
    exit /b 1
)

echo ============================================================
echo  OYTS Demo - SIMULATION MODE (synthetic fire)
echo ============================================================
echo.

REM --- Ilk acilis kurulumu (idempotent) ---
echo [1/6] Ortam kurulumu (eksik paket varsa otomatik kurulur)...
pushd "%PYTHON_DIR%"
python -m utils.setup_env --quiet
set SETUP_RC=%ERRORLEVEL%
popd
if not "%SETUP_RC%"=="0" (
    echo.
    echo [HATA] Kurulum tamamlanamadi. Internet baglantisini kontrol edin.
    echo        Manuel: python -m pip install -r python\requirements.txt
    pause
    exit /b 1
)

REM --- Preflight (utils.doctor; kamera testi atlanir) ---
echo [2/6] Preflight kontrolleri (Python, paketler, portlar)...
pushd "%PYTHON_DIR%"
python -m utils.doctor --source synthetic --ports %BACKEND_PORT%,%FRONTEND_PORT%
set DOCTOR_RC=%ERRORLEVEL%
popd
if not "%DOCTOR_RC%"=="0" (
    echo.
    echo [HATA] Preflight basarisiz. Yukaridaki listede isaretli sorunlari cozun.
    pause
    exit /b 1
)

REM --- Eski instanslari temizle (port catismasini onler) ---
echo [3/6] Eski process'ler temizleniyor...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%BACKEND_PORT% ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>nul
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%FRONTEND_PORT% ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>nul
)
REM Acik kalmis python web_app/serve sureclerini de oldur
wmic process where "name='python.exe' and commandline like '%%web_app.py%%'" delete >nul 2>nul
wmic process where "name='python.exe' and commandline like '%%serve.py%%'" delete >nul 2>nul
timeout /t 1 /nobreak >nul

REM --- Backend baslat ---
echo [4/6] Backend baslatiliyor (port %BACKEND_PORT%, source=synthetic)...
echo       Log: %LOG_DIR%\backend.log
start "OYTS Backend (synthetic)" /MIN cmd /c "python "%PYTHON_DIR%\web_app.py" --port %BACKEND_PORT% --source synthetic --autostart > "%LOG_DIR%\backend.log" 2>&1"

REM --- Frontend baslat ---
echo [5/6] Frontend baslatiliyor (port %FRONTEND_PORT%)...
echo       Log: %LOG_DIR%\frontend.log
start "OYTS Frontend" /MIN cmd /c "python "%WEB_DIR%\serve.py" %FRONTEND_PORT% > "%LOG_DIR%\frontend.log" 2>&1"

REM --- Backend hazir olana kadar bekle (YOLO yuklemesi 10-20 sn) ---
echo [6/6] Backend hazir olmasi bekleniyor (YOLO yukleniyor, ~10-20 sn)...
set /a attempts=0
:wait_loop
set /a attempts+=1
if %attempts% GTR 60 (
    echo.
    echo [UYARI] Backend 60 sn icinde yanit vermedi. Log'u kontrol edin:
    echo         %LOG_DIR%\backend.log
    goto open_browser
)
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 http://127.0.0.1:%BACKEND_PORT%/healthz) | Out-Null; exit 0 } catch { exit 1 }" >nul 2>nul
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    <nul set /p =.
    goto wait_loop
)
echo.
echo       Backend HAZIR (%attempts% sn).

:open_browser
echo.
echo ============================================================
echo  OYTS Demo Hazir
echo ============================================================
echo  Frontend : http://127.0.0.1:%FRONTEND_PORT%/live.html
echo  Backend  : http://127.0.0.1:%BACKEND_PORT% (source=synthetic)
echo  Loglar   : %LOG_DIR%\
echo.
echo  Durdurmak icin: stop.bat dosyasina cift tiklayin
echo ============================================================

REM --- Tarayicida ac ---
start "" "http://127.0.0.1:%FRONTEND_PORT%/live.html"

echo.
echo Bu pencereyi kapatabilirsiniz - backend/frontend arka planda calisir.
timeout /t 5
endlocal
