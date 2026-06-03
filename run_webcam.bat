@echo off
chcp 65001 >nul
REM ============================================================
REM  OYTS - Webcam Modu (Gercek Kamera)
REM ============================================================
REM  Bu dosyaya cift tikla:
REM    - Eski backend/frontend process'leri temizler
REM    - Backend baslatir (webcam kaynak, config_webcam.yaml)
REM    - Frontend baslatir
REM    - Tarayicida live.html acar
REM
REM  GEREKSINIM: Bilgisayara takili calisir bir webcam.
REM  - Windows Ayarlar > Gizlilik > Kamera > "Masaustu uygulamalari"
REM    secenegi ACIK olmali
REM  - Baska bir uygulama (Zoom/Teams/tarayici sekmesi) kamerayi
REM    kullaniyor olmamali
REM
REM  Farkli kamera index'i (0, 1, 2...) kullanmak icin:
REM    python\configs\config_webcam.yaml -> mode.webcam_index degistir
REM
REM  Durdurmak icin: stop.bat dosyasina cift tikla
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

set REPO_ROOT=%~dp0
set PYTHON_DIR=%REPO_ROOT%python
set WEB_DIR=%REPO_ROOT%web
set CONFIG=%PYTHON_DIR%\configs\config_webcam.yaml
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

REM --- Config dosyasi var mi? ---
if not exist "%CONFIG%" (
    echo [HATA] Config bulunamadi: %CONFIG%
    echo Proje klasor yapisi bozulmus olabilir.
    pause
    exit /b 1
)

echo ============================================================
echo  OYTS Demo - WEBCAM MODE (gercek kamera)
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

REM --- Preflight (utils.doctor) ---
echo [2/6] Preflight kontrolleri (Python, paketler, kamera, portlar)...
pushd "%PYTHON_DIR%"
python -m utils.doctor --source webcam --ports %BACKEND_PORT%,%FRONTEND_PORT% --open-settings
set DOCTOR_RC=%ERRORLEVEL%
popd
if not "%DOCTOR_RC%"=="0" (
    echo.
    echo [HATA] Preflight basarisiz. Kamera izin paneli otomatik acilmis
    echo        olabilir. Listede uygulamayi acin, sonra bu pencereyi
    echo        kapatip tekrar baslatin. Kamera olmadan: run_sim.bat
    pause
    exit /b 1
)

REM --- Eski instanslari temizle ---
echo [3/6] Eski process'ler + kamera kilidini temizle...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%BACKEND_PORT% ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>nul
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%FRONTEND_PORT% ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>nul
)
wmic process where "name='python.exe' and commandline like '%%web_app.py%%'" delete >nul 2>nul
wmic process where "name='python.exe' and commandline like '%%serve.py%%'" delete >nul 2>nul
REM Kamera handle'in driver'da release olmasi icin biraz bekle
timeout /t 2 /nobreak >nul

REM --- Backend baslat ---
echo [4/6] Backend baslatiliyor (port %BACKEND_PORT%, source=webcam)...
echo       Config: config_webcam.yaml (HSV filter + fire_validator)
echo       Log: %LOG_DIR%\backend.log
start "OYTS Backend (webcam)" /MIN cmd /c "python "%PYTHON_DIR%\web_app.py" --config "%CONFIG%" --port %BACKEND_PORT% --source webcam --autostart > "%LOG_DIR%\backend.log" 2>&1"

REM --- Frontend baslat ---
echo [5/6] Frontend baslatiliyor (port %FRONTEND_PORT%)...
echo       Log: %LOG_DIR%\frontend.log
start "OYTS Frontend" /MIN cmd /c "python "%WEB_DIR%\serve.py" %FRONTEND_PORT% > "%LOG_DIR%\frontend.log" 2>&1"

REM --- Backend hazir olana kadar bekle ---
echo [6/6] Backend hazir olmasi bekleniyor (YOLO + kamera, ~15-30 sn)...
set /a attempts=0
:wait_loop
set /a attempts+=1
if %attempts% GTR 60 (
    echo.
    echo [UYARI] Backend 60 sn icinde yanit vermedi. Log'u kontrol edin:
    echo         %LOG_DIR%\backend.log
    echo.
    echo  En sik gorulen sebepler:
    echo   - Kamera baska bir uygulama tarafindan kullaniliyor (Zoom/Teams)
    echo   - Ayarlar ^> Gizlilik ^> Kamera ^> Masaustu uygulamalari KAPALI
    echo   - Yanlis kamera index'i (config_webcam.yaml -^> mode.webcam_index)
    echo   - Kameradan dogru kare gelmiyor (USB'yi cikar/tak)
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
echo  Backend  : http://127.0.0.1:%BACKEND_PORT% (source=webcam)
echo  Loglar   : %LOG_DIR%\
echo.
echo  Kamera goruntusu gelmiyor mu? Tarayicida sayfayi yenileyin.
echo  Durdurmak icin: stop.bat dosyasina cift tiklayin
echo ============================================================

start "" "http://127.0.0.1:%FRONTEND_PORT%/live.html"

echo.
echo Bu pencereyi kapatabilirsiniz - backend/frontend arka planda calisir.
timeout /t 5
endlocal
