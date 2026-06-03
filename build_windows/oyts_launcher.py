#!/usr/bin/env python3
"""
oyts_launcher.py — Windows .exe için tek giriş noktası
========================================================
İçeride 3 iş yapar:
  1. Flask backend (web_app.py) → port 5050
  2. Statik HTTP server (serve.py)  → port 8765
  3. Varsayılan tarayıcıyı http://127.0.0.1:8765/index.html'e açar

PyInstaller ile tek .exe'ye paketlenir.

Bayraklar:
  --source synthetic|webcam|esp32     (default: synthetic)
  --no-browser                        (tarayıcı açma)
  --backend-port 5050  --frontend-port 8765
"""
from __future__ import annotations

import argparse
import functools
import logging
import os
import sys
import threading
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


# PyInstaller bundle path resolution
# .exe içinde sys._MEIPASS bundled dosyaların geçici çıkarma dizinidir.
def resource_path(rel: str) -> Path:
    """Bundle içindeki bir dosyanın gerçek yolunu döner."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / rel
    # Geliştirme modu (dosyalar normal yerlerde)
    return Path(__file__).resolve().parent.parent / rel


# Statik HTTP server (web/ klasörü)
class StaticHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path in ("/", ""):
            self.path = "/index.html"
        return super().do_GET()

    def log_message(self, *a, **k):
        return  # gürültü olmasın


def start_static_server(port: int, web_dir: Path) -> threading.Thread:
    handler = functools.partial(StaticHandler, directory=str(web_dir))
    srv = ThreadingHTTPServer(("127.0.0.1", port), handler)

    def _serve():
        try:
            srv.serve_forever()
        except Exception:
            pass

    th = threading.Thread(target=_serve, daemon=True, name="static")
    th.start()
    return th


# Flask backend (web_app.py)
def start_backend(port: int, source: str, config: Path) -> None:
    """web_app.py içeriğini import ederek aynı process'te başlat."""
    # PyInstaller bundle'da python/ python path'inde değil — manuel ekle
    python_dir = resource_path("python")
    if str(python_dir) not in sys.path:
        sys.path.insert(0, str(python_dir))

    # macOS özel — Windows'ta no-op
    os.environ.setdefault("OPENCV_AVFOUNDATION_SKIP_AUTH", "1")

    # web_app.py'nin Flask app'ini ve VisionService'ini al
    import web_app
    from utils.config_loader import load_config

    cfg = load_config(str(config))
    logger = logging.getLogger("oyts")
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    web_app.service = web_app.VisionService(cfg, logger)
    web_app.service.set_source(source)
    web_app.service.start()

    logger.info("Backend başlıyor → http://127.0.0.1:%d  (source=%s)", port, source)
    # Flask development server — threaded, debug kapalı
    web_app.app.run(host="127.0.0.1", port=port, debug=False,
                    threaded=True, use_reloader=False)


# Main
def main():
    ap = argparse.ArgumentParser(description="OYTS Otonom Yangın Tespit Sistemi")
    ap.add_argument("--source", default="synthetic",
                    choices=["synthetic", "webcam", "esp32"])
    ap.add_argument("--backend-port", type=int, default=5050)
    ap.add_argument("--frontend-port", type=int, default=8765)
    ap.add_argument("--config", default=None,
                    help="config.yaml yolu (varsayılan: webcam ise config_webcam.yaml)")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    web_dir = resource_path("web")
    python_dir = resource_path("python")
    cfg_default = ("config_webcam.yaml" if args.source in ("webcam", "esp32")
                   else "config.yaml")
    cfg_path = Path(args.config) if args.config else (
        python_dir / "configs" / cfg_default)

    if not cfg_path.exists():
        print(f"[ERR] Config bulunamadı: {cfg_path}", file=sys.stderr)
        sys.exit(1)
    if not web_dir.exists():
        print(f"[ERR] Web dizini yok: {web_dir}", file=sys.stderr)
        sys.exit(1)

    print("=" * 60)
    print(" OYTS Otonom Yangın Tespit Sistemi — Windows Edition")
    print("=" * 60)
    print(f"  Backend  : http://127.0.0.1:{args.backend_port}")
    print(f"  Frontend : http://127.0.0.1:{args.frontend_port}")
    print(f"  Kaynak   : {args.source}")
    print(f"  Config   : {cfg_path}")
    print("  Durdurmak için: bu pencereyi kapat (Ctrl+C)")
    print("=" * 60)

    # Statik server (arka plan)
    start_static_server(args.frontend_port, web_dir)

    # Tarayıcıyı 3 sn sonra aç (backend hazır olsun)
    if not args.no_browser:
        url = f"http://127.0.0.1:{args.frontend_port}/index.html"

        def _open():
            time.sleep(3)
            try:
                webbrowser.open(url)
            except Exception as e:
                print(f"[WARN] Tarayıcı açılamadı: {e}")

        threading.Thread(target=_open, daemon=True).start()

    # Backend (ana thread — blokli, Ctrl+C ile sonlanır)
    try:
        start_backend(args.backend_port, args.source, cfg_path)
    except KeyboardInterrupt:
        print("\n[STOP] Kapanış...")


if __name__ == "__main__":
    main()
