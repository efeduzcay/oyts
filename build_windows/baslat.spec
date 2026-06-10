# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — Baslat.exe (Tkinter launcher) Windows paketi
==================================================================
Entry: build_windows/baslat.py — çift tıklandığında Tkinter penceresi
açar (Baslat.command'in Windows karşılığı).

Bundle içeriği:
  • baslat.py (multi-mode entry: launcher / webapp / serve)
  • python/launcher.py + ai/ + utils/ + sim/ + configs/ + web_app.py
  • python/*.pt → YOLO model dosyaları
  • web/ → index.html, live.html, photo/, screenshots/, serve.py

Build (Windows üzerinde):
    cd build_windows
    pyinstaller baslat.spec --noconfirm

Çıktı:
    dist/Baslat/Baslat.exe + bağımlılıklar (~400-600 MB)
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os

# SPECPATH zaten spec dosyasının bulunduğu dizin (build_windows/).
# dirname(SPECPATH) bir üst dizine çıkar — yanlış.
ROOT = os.path.abspath(SPECPATH)
PROJECT = os.path.abspath(os.path.join(ROOT, os.pardir))


# Bundle'a kopyalanacak data dosyaları
datas = []
# Python kaynak ağacı
for sub in ("python/configs", "python/ai", "python/utils", "python/sim"):
    datas.append((os.path.join(PROJECT, sub), sub))
# Python kök seviyesi modüller (launcher + web_app + controller)
for f in ("launcher.py", "web_app.py", "pc_vision_controller.py"):
    p = os.path.join(PROJECT, "python", f)
    if os.path.exists(p):
        datas.append((p, "python"))
# Model dosyaları (binary)
for pt in ("fire_model.pt", "fire_model_roboflow.pt",
           "fire_model_v3_real.pt", "fire_model_v311_mixed.pt"):
    p = os.path.join(PROJECT, "python", pt)
    if os.path.exists(p):
        datas.append((p, "python"))
# Web frontend (serve.py dahil)
datas.append((os.path.join(PROJECT, "web"), "web"))


# Hidden imports
hiddenimports = []
hiddenimports += collect_submodules("ultralytics")
hiddenimports += collect_submodules("torch")
hiddenimports += collect_submodules("torchvision")
hiddenimports += collect_submodules("cv2")
hiddenimports += collect_submodules("flask")
hiddenimports += [
    "yaml", "numpy", "scipy", "matplotlib",
    "matplotlib.backends.backend_agg",
    "PIL", "pyserial", "serial",
    # Tkinter (launcher UI) — embedded Python'da eksik olabilir
    "tkinter", "tkinter.ttk", "tkinter.font",
    # Proje modülleri
    "launcher", "web_app", "pc_vision_controller",
    "ai.tracker", "ai.heatmap", "ai.distance",
    "ai.webhook", "ai.sim_detector",
    "ai.fire_validator", "ai.bright_flame_detector",
    "utils.config_loader", "utils.csv_logger", "utils.dashboard",
    "sim.fire_scene_generator",
]


a = Analysis(
    ["baslat.py"],
    pathex=[
        ROOT,
        os.path.join(PROJECT, "python"),
        os.path.join(PROJECT, "web"),
    ],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib.tests",
        "torch.distributions",
        "torch.testing",
        "scipy.spatial.tests",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Baslat",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                   # UPX bazen Windows Defender'ı yanıltır
    console=True,                # Tkinter UI + arka plan log konsolu
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, "icon.ico") if os.path.exists(
        os.path.join(ROOT, "icon.ico")) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Baslat",
)
