# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — OYTS Windows .exe paketi
=============================================
Bundle içeriği:
  • oyts_launcher.py (entry point)
  • python/ → tüm Python kaynak + ai/ + utils/ + sim/ + configs/
  • python/*.pt → YOLO model dosyaları
  • web/ → index.html, live.html, photo/, screenshots/

Build:
    pyinstaller oyts_launcher.spec --noconfirm

Çıktı:
    dist/OYTS/OYTS.exe + tüm bağımlılıklar

Tek dosya istersen (--onefile, daha yavaş başlangıç):
    pyinstaller --onefile oyts_launcher.spec --noconfirm
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os

ROOT = os.path.abspath(os.path.dirname(SPECPATH))
PROJECT = os.path.abspath(os.path.join(ROOT, os.pardir))


# ── Bundle'a kopyalanacak data dosyaları ──────────────────────────────
datas = []
# Python kaynak ağacı (configs, ai, sim, utils, web_app, pc_vision_controller)
for sub in ("python/configs", "python/ai", "python/utils", "python/sim"):
    datas.append((os.path.join(PROJECT, sub), sub))
# Python kök seviyesi *.py
for f in ("web_app.py", "pc_vision_controller.py"):
    datas.append((os.path.join(PROJECT, "python", f), "python"))
# Model dosyaları (binary)
for pt in ("fire_model.pt", "fire_model_roboflow.pt",
           "fire_model_v3_real.pt", "fire_model_v311_mixed.pt"):
    p = os.path.join(PROJECT, "python", pt)
    if os.path.exists(p):
        datas.append((p, "python"))
# Web frontend
datas.append((os.path.join(PROJECT, "web"), "web"))


# ── Hidden imports (PyInstaller'ın bulamayabileceği modüller) ─────────
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
    "ai.tracker", "ai.heatmap", "ai.distance",
    "ai.webhook", "ai.sim_detector",
    "ai.fire_validator", "ai.bright_flame_detector",
    "utils.config_loader", "utils.csv_logger", "utils.dashboard",
    "sim.fire_scene_generator",
]


# ── Analysis ──────────────────────────────────────────────────────────
a = Analysis(
    ["oyts_launcher.py"],
    pathex=[
        ROOT,
        os.path.join(PROJECT, "python"),
    ],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Boyutu azaltmak için (sertifika)
        "tkinter",
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
    name="OYTS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                   # UPX bazen Windows Defender'ı yanıltır
    console=True,                # konsol penceresi (logları gör)
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
    name="OYTS",
)
