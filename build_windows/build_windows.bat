@echo off
REM ============================================================
REM  OYTS Windows Build Script
REM ============================================================
REM  Bu .bat dosyasi Windows uzerinde:
REM    1. Python sanal ortam olusturur (varsa atlar)
REM    2. Gereksinimleri pip ile kurar
REM    3. PyInstaller ile .exe paketler
REM    4. Inno Setup varsa installer da derler
REM
REM  Kullanim:
REM    cd build_windows
REM    build_windows.bat
REM
REM  Cikti:
REM    dist\Baslat\Baslat.exe          <- cift tikla, Tkinter penceresi acilir
REM    Output\OYTS-Setup-3.1.3.exe     <- Inno Setup kurulum sihirbazi
REM ============================================================
setlocal
cd /d "%~dp0"

echo.
echo ============================================================
echo  OYTS Windows Build - Adim 1/4: Python kontrol
echo ============================================================
where python >nul 2>nul
if errorlevel 1 (
    echo [HATA] Python yok. https://www.python.org/downloads/ uzerinden 3.10+ kur.
    pause
    exit /b 1
)
python --version

echo.
echo ============================================================
echo  Adim 2/4: Sanal ortam (venv) + bagimliliklar
echo ============================================================
if not exist venv (
    python -m venv venv
    echo Venv olusturuldu.
) else (
    echo Venv zaten var.
)

call venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r ..\python\requirements.txt
python -m pip install pyinstaller

echo.
echo ============================================================
echo  Adim 3/4: PyInstaller ile .exe paketle
echo ============================================================
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
pyinstaller baslat.spec --noconfirm
if errorlevel 1 (
    echo [HATA] PyInstaller basarisiz.
    pause
    exit /b 2
)

echo.
echo .exe hazir: dist\Baslat\Baslat.exe
echo Test etmek icin: dist\Baslat\Baslat.exe (cift tikla)

echo.
echo ============================================================
echo  Adim 4/4: Inno Setup ile installer (opsiyonel)
echo ============================================================
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
    echo [BILGI] Inno Setup bulunamadi. Installer atlandi.
    echo         Inno Setup 6.3+ kurarak: https://jrsoftware.org/isdl.php
    echo         Sonra: ISCC oyts_setup.iss
    goto :done
)
%ISCC% oyts_setup.iss
if errorlevel 1 (
    echo [HATA] Inno Setup derlemesi basarisiz.
    pause
    exit /b 3
)
echo Installer hazir: Output\OYTS-Setup-3.1.3.exe

:done
echo.
echo ============================================================
echo  BITTI
echo ============================================================
echo .exe        : %CD%\dist\Baslat\Baslat.exe
echo Installer   : %CD%\Output\OYTS-Setup-3.1.3.exe (varsa)
echo.
pause
