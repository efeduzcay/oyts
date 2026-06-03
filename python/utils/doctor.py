"""OYTS Preflight Doctor — backend açılmadan ortamı kontrol eder.

Kullanım:
    python -m utils.doctor                  # tüm kontroller
    python -m utils.doctor --source webcam  # kameraya odaklı
    python -m utils.doctor --json           # JSON çıktı (script entegrasyonu)

Çıkış kodları:
    0 → her şey yeşil (veya sadece uyarı)
    1 → bloklayıcı hata (backend başlatılmamalı)
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import socket
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

IS_MACOS   = platform.system() == "Darwin"
IS_WINDOWS = platform.system() == "Windows"

OK, WARN, FAIL = "ok", "warn", "fail"

REPO_ROOT  = Path(__file__).resolve().parents[2]
PYTHON_DIR = REPO_ROOT / "python"
DEFAULT_MODEL = PYTHON_DIR / "fire_model.pt"
REQUIRED_PKGS = [
    ("cv2",         "opencv-python"),
    ("numpy",       "numpy"),
    ("flask",       "flask"),
    ("yaml",        "PyYAML"),
    ("ultralytics", "ultralytics"),
    ("requests",    "requests"),
    ("serial",      "pyserial"),
]


def _check_python() -> Tuple[str, str]:
    major, minor = sys.version_info[:2]
    ver = f"{major}.{minor}.{sys.version_info.micro}"
    if (major, minor) < (3, 9):
        return FAIL, f"Python {ver} — 3.9+ gerekli"
    return OK, f"Python {ver}"


def _check_packages() -> List[Tuple[str, str, str]]:
    out = []
    for mod, pip_name in REQUIRED_PKGS:
        try:
            importlib.import_module(mod)
            out.append((OK, mod, "importable"))
        except Exception as e:
            out.append((FAIL, mod, f"eksik → pip install {pip_name} ({e.__class__.__name__})"))
    return out


def _check_port(port: int) -> Tuple[str, str]:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.bind(("127.0.0.1", port))
    except OSError:
        return WARN, f"port {port} dolu (eski instance? stop/durdur ile temizlenir)"
    finally:
        s.close()
    return OK, f"port {port} boş"


def _check_model() -> Tuple[str, str]:
    if DEFAULT_MODEL.exists():
        mb = DEFAULT_MODEL.stat().st_size / (1024 * 1024)
        return OK, f"fire_model.pt mevcut ({mb:.1f} MB)"
    return FAIL, f"fire_model.pt yok: {DEFAULT_MODEL}"


def _check_webcam(idx: int = 0) -> Tuple[str, str]:
    """Tek seferlik open denemesi. TCC reddi → FAIL."""
    try:
        import cv2  # noqa: WPS433
    except Exception:
        return FAIL, "opencv-python yüklü değil (paket kontrolünü gör)"

    # Background thread'de auth dialog'u tetiklenmesin
    os.environ.setdefault("OPENCV_AVFOUNDATION_SKIP_AUTH", "1")
    os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

    if IS_MACOS:
        backend = cv2.CAP_AVFOUNDATION
    elif IS_WINDOWS:
        backend = cv2.CAP_DSHOW
    else:
        backend = cv2.CAP_V4L2

    cap = None
    try:
        cap = cv2.VideoCapture(int(idx), backend)
        if not cap.isOpened():
            # Yedek: backend olmadan dene
            try:
                cap.release()
            except Exception:
                pass
            cap = cv2.VideoCapture(int(idx))

        if not cap.isOpened():
            if IS_MACOS:
                return FAIL, (
                    "kamera açılamadı — macOS izni eksik olabilir. "
                    "System Settings → Privacy & Security → Camera listesinde "
                    "bu uygulamayı açın ve Cmd+Q ile yeniden başlatın."
                )
            if IS_WINDOWS:
                return FAIL, (
                    "kamera açılamadı — Ayarlar → Gizlilik → Kamera → "
                    "Masaüstü uygulamaları AÇIK olmalı, ya da farklı index deneyin."
                )
            return FAIL, "kamera açılamadı — /dev/video ve izinleri kontrol edin"

        ok, frame = cap.read()
        if not ok or frame is None:
            return WARN, "kamera açıldı ama kare okunamadı — driver/permission tutarsızlığı"
        h, w = frame.shape[:2]
        return OK, f"kamera index={idx} hazır ({w}x{h})"
    finally:
        try:
            if cap is not None:
                cap.release()
        except Exception:
            pass


def open_camera_settings() -> bool:
    """Platforma göre kamera izin panelini açar. Sessiz; başarı/başarısızlık döner."""
    try:
        if IS_MACOS:
            subprocess.run(
                ["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Camera"],
                check=False,
            )
            return True
        if IS_WINDOWS:
            subprocess.run(
                ["cmd", "/c", "start", "ms-settings:privacy-webcam"],
                check=False,
            )
            return True
    except Exception:
        return False
    return False


def _emit_text(results: List[Tuple[str, str, str]]) -> None:
    icons = {OK: "✓", WARN: "!", FAIL: "✗"}
    width = max(len(name) for _, name, _ in results) + 2
    for status, name, msg in results:
        print(f"  {icons[status]} {name:<{width}} {msg}")


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="OYTS preflight doctor")
    ap.add_argument("--source", choices=["webcam", "synthetic", "esp32", "any"],
                    default="any", help="Kaynağa özel kontrol (webcam → kamera testi)")
    ap.add_argument("--webcam-index", type=int, default=0)
    ap.add_argument("--ports", type=str, default="5050,8765",
                    help="Virgül ayraçlı port listesi")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--skip-camera", action="store_true",
                    help="Webcam testini atla (sadece synthetic'te anlamlı)")
    ap.add_argument("--open-settings", action="store_true",
                    help="Kamera testi fail olursa OS izin panelini otomatik aç")
    args = ap.parse_args(argv)

    results: List[Tuple[str, str, str]] = []

    s, m = _check_python()
    results.append((s, "python", m))

    for s, name, msg in _check_packages():
        results.append((s, f"pkg:{name}", msg))

    s, m = _check_model()
    results.append((s, "model", m))

    for p in args.ports.split(","):
        p = p.strip()
        if not p:
            continue
        s, m = _check_port(int(p))
        results.append((s, f"port:{p}", m))

    camera_failed = False
    if args.source == "webcam" and not args.skip_camera:
        s, m = _check_webcam(args.webcam_index)
        results.append((s, "kamera", m))
        camera_failed = (s == FAIL)

    if args.json:
        print(json.dumps(
            [{"status": s, "check": n, "message": m} for s, n, m in results],
            ensure_ascii=False, indent=2,
        ))
    else:
        print(f"== OYTS Doctor — {platform.system()} {platform.release()} ==")
        _emit_text(results)
        n_fail = sum(1 for s, *_ in results if s == FAIL)
        n_warn = sum(1 for s, *_ in results if s == WARN)
        print()
        if n_fail:
            print(f"  ✗ {n_fail} bloklayıcı hata — backend başlamayacak.")
        elif n_warn:
            print(f"  ! {n_warn} uyarı — backend başlayabilir, izle.")
        else:
            print("  ✓ Tüm kontroller başarılı.")

    if camera_failed and args.open_settings:
        opened = open_camera_settings()
        if not args.json:
            if opened:
                print("\n  → Kamera izin paneli açıldı. Uygulamayı listede aç,")
                print("    sonra uygulamayı tam kapatıp (Cmd+Q) yeniden başlat.")
            else:
                print("\n  ! İzin paneli otomatik açılamadı, manuel açın:")
                print("    System Settings → Privacy & Security → Camera (macOS)")
                print("    Ayarlar → Gizlilik → Kamera (Windows)")

    return 1 if any(s == FAIL for s, *_ in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
