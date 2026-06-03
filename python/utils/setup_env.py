"""İlk açılış kurulumu — koddan anlamayan kullanıcı için.

Idempotent: her seferinde çalışır ama yalnız eksik bir şey varsa iş yapar.

Adımlar:
  1) Python sürümü 3.9+ mi?
  2) Gerekli paketler import edilebiliyor mu? Yoksa pip install -r requirements.txt
  3) fire_model.pt var mı? Yoksa ai.download_model çalıştır.

Kullanım:
    python -m utils.setup_env
    python -m utils.setup_env --quiet         # sadece eksiklik varsa konuş
    python -m utils.setup_env --no-pip        # paketleri kurma (sadece kontrol)
    python -m utils.setup_env --no-model      # modeli indirme

Çıkış kodu:
    0 → ortam hazır
    1 → kapatıcı hata (kullanıcı müdahale etmeli)
"""
from __future__ import annotations

import argparse
import importlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

REPO_ROOT  = Path(__file__).resolve().parents[2]
PYTHON_DIR = REPO_ROOT / "python"
REQUIREMENTS = PYTHON_DIR / "requirements.txt"
MODEL_FILE   = PYTHON_DIR / "fire_model.pt"

# import-name → pip-name eşlemesi. Sadece çekirdek setin import'unu test ederiz;
# kalanlar requirements.txt'den (tqdm, albumentations, vs.) zaten kuruluyor.
CORE_IMPORTS: List[Tuple[str, str]] = [
    ("cv2",         "opencv-python"),
    ("numpy",       "numpy"),
    ("flask",       "flask"),
    ("yaml",        "PyYAML"),
    ("ultralytics", "ultralytics"),
    ("requests",    "requests"),
    ("serial",      "pyserial"),
    ("PIL",         "Pillow"),
    ("torch",       "torch"),
    ("matplotlib",  "matplotlib"),
]


def _say(msg: str, quiet: bool = False, level: str = "info") -> None:
    if quiet and level == "info":
        return
    prefix = {"info": "•", "ok": "✓", "warn": "!", "err": "✗"}.get(level, "•")
    print(f"  {prefix} {msg}", flush=True)


def check_python(quiet: bool = False) -> bool:
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 9):
        _say(f"Python {major}.{minor} bulundu — 3.9+ gerekli. "
             "https://www.python.org/downloads/ adresinden güncelle.", level="err")
        return False
    _say(f"Python {major}.{minor}.{sys.version_info.micro}", quiet, level="ok")
    return True


def missing_packages() -> List[Tuple[str, str]]:
    missing = []
    for mod, pip_name in CORE_IMPORTS:
        try:
            importlib.import_module(mod)
        except Exception:
            missing.append((mod, pip_name))
    return missing


def install_requirements(quiet: bool = False) -> bool:
    if not REQUIREMENTS.exists():
        _say(f"requirements.txt yok: {REQUIREMENTS}", level="err")
        return False
    _say("Eksik paketler yükleniyor — bu birkaç dakika sürebilir...", level="info")
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
           "-r", str(REQUIREMENTS)]
    if quiet:
        cmd.insert(4, "-q")
    try:
        result = subprocess.run(cmd, cwd=str(PYTHON_DIR))
    except FileNotFoundError:
        _say("pip bulunamadı. Python kurulumu eksik olabilir.", level="err")
        return False
    if result.returncode != 0:
        _say("pip install başarısız. İnternet bağlantısı veya yetki sorunu olabilir.",
             level="err")
        _say(f"Manuel deneme: {' '.join(cmd)}", level="warn")
        return False
    return True


def ensure_packages(quiet: bool = False, do_install: bool = True) -> bool:
    missing = missing_packages()
    if not missing:
        _say("Tüm gerekli paketler hazır.", quiet, level="ok")
        return True
    names = ", ".join(m for m, _ in missing)
    _say(f"Eksik paket: {names}", level="warn")
    if not do_install:
        return False
    if not install_requirements(quiet=quiet):
        return False
    # Doğrulama
    still_missing = missing_packages()
    if still_missing:
        names = ", ".join(m for m, _ in still_missing)
        _say(f"Kurulumdan sonra hala eksik: {names}", level="err")
        return False
    _say("Paketler yüklendi.", level="ok")
    return True


def ensure_model(quiet: bool = False, do_download: bool = True) -> bool:
    if MODEL_FILE.exists():
        _say(f"fire_model.pt mevcut ({MODEL_FILE.stat().st_size // (1024*1024)} MB)",
             quiet, level="ok")
        return True
    _say(f"fire_model.pt yok: {MODEL_FILE}", level="warn")
    # Mevcut yedek modeller varsa onlardan birini kopyala (download yerine offline)
    for candidate in ("fire_model_v311_mixed.pt", "fire_model_v3_real.pt",
                      "fire_model_roboflow.pt"):
        p = PYTHON_DIR / candidate
        if p.exists():
            shutil.copy2(p, MODEL_FILE)
            _say(f"Yedek modelden kopyalandı: {candidate}", level="ok")
            return True
    if not do_download:
        return False
    _say("Model indiriliyor (ilk seferde ~25 MB)...", level="info")
    try:
        cmd = [sys.executable, "-m", "ai.download_model"]
        result = subprocess.run(cmd, cwd=str(PYTHON_DIR))
        if result.returncode != 0:
            _say("Model indirilemedi. İnternet bağlantısını kontrol edin.", level="err")
            return False
    except Exception as e:
        _say(f"Model indirme hatası: {e}", level="err")
        return False
    if not MODEL_FILE.exists():
        _say("İndirme tamamlandı görünüyor ama fire_model.pt hala yok.", level="err")
        return False
    return True


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="OYTS ilk açılış kurulumu")
    ap.add_argument("--quiet", action="store_true",
                    help="Eksiklik yoksa sessiz")
    ap.add_argument("--no-pip", action="store_true",
                    help="Eksik paketleri otomatik kurma")
    ap.add_argument("--no-model", action="store_true",
                    help="Model dosyasını otomatik indirme")
    args = ap.parse_args(argv)

    if not args.quiet:
        print("== OYTS Setup ==", flush=True)

    if not check_python(quiet=args.quiet):
        return 1
    if not ensure_packages(quiet=args.quiet, do_install=not args.no_pip):
        return 1
    if not ensure_model(quiet=args.quiet, do_download=not args.no_model):
        return 1

    if not args.quiet:
        print("\n  Kurulum tamamlandı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
