@echo off
chcp 65001 >nul
REM ============================================================
REM  OYTS Launcher — tek pencere arayuzu (cift tikla)
REM  Tkinter penceresi acilir; oradan webcam/simulasyon/durdur sec.
REM ============================================================
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo ============================================================
    echo  Python bulunamadi.
    echo  Lutfen Python 3.9+ kurun: https://www.python.org/downloads/
    echo  Kurulumda "Add Python to PATH" kutusunu isaretleyin.
    echo ============================================================
    pause
    exit /b 1
)

REM Tkinter kontrolu (Windows resmi Python'a dahildir, embedded'da olmaz)
python -c "import tkinter" >nul 2>nul
if errorlevel 1 (
    echo Tkinter bulunamadi. Python'u python.org'dan resmi installer ile
    echo kurun (embedded Python paketi tkinter icermez).
    pause
    exit /b 1
)

REM Konsol penceresi gozukmesin diye pythonw kullan
where pythonw >nul 2>nul
if errorlevel 1 (
    python python\launcher.py
) else (
    start "" pythonw python\launcher.py
)
