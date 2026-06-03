#!/usr/bin/env python3
"""
ai/download_model.py — Pre-trained yangın modelini indir ve aktif et
=====================================================================
HuggingFace / direkt URL üzerinden YOLOv8 fire model .pt dosyasını
çeker ve fire_model.pt'in yerine koyar (eski yedeklenir).

Önerilen modeller:
  keremberke/yolov8m-fire-detection   ← popüler, fire+smoke (varsayılan)
  keremberke/yolov8n-fire-detection   ← küçük/hızlı versiyon (varsa)

Kullanım:
  python ai/download_model.py                          # varsayılan model
  python ai/download_model.py --hf USER/MODEL_NAME    # başka HF modeli
  python ai/download_model.py --url https://...best.pt  # direkt URL
  python ai/download_model.py --restore                 # yedeği geri yükle

Eski model otomatik fire_model_backup_<tarih>.pt olarak yedeklenir.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "fire_model.pt"
BACKUPS_DIR = ROOT

# HuggingFace direkt indirme URL şablonu (auth gerektirmeyen public modeller)
HF_URL_TEMPLATE = "https://huggingface.co/{repo}/resolve/main/{filename}"


def download(url: str, dst: Path, chunk: int = 1 << 16) -> None:
    print(f"[DL] {url}")
    req = Request(url, headers={"User-Agent": "OYTS-downloader/1.0"})
    with urlopen(req, timeout=120) as r, open(dst, "wb") as f:
        total = int(r.headers.get("Content-Length", 0))
        got = 0
        while True:
            buf = r.read(chunk)
            if not buf:
                break
            f.write(buf)
            got += len(buf)
            if total:
                pct = got * 100 / total
                bar = "█" * int(pct / 4) + "─" * (25 - int(pct / 4))
                sys.stdout.write(f"\r  [{bar}] {pct:5.1f}%  "
                                  f"{got/1e6:.1f}/{total/1e6:.1f} MB")
                sys.stdout.flush()
        sys.stdout.write("\n")


def download_hf(repo: str, filename: str, dst: Path) -> bool:
    """huggingface_hub ile indir — auth/redirect doğru handle eder.
    Yoksa False döner (raw URL fallback'a düş)."""
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("[INFO] huggingface_hub yok — kuruluyor (gerek pip)...")
        import subprocess
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install",
                                   "-q", "--user", "huggingface_hub"])
            from huggingface_hub import hf_hub_download
        except Exception as e:
            print(f"[ERR] huggingface_hub kurulamadı: {e}")
            return False
    try:
        print(f"[HF] {repo} / {filename}")
        path = hf_hub_download(repo_id=repo, filename=filename)
        shutil.copy2(path, dst)
        print(f"[HF] Kopyalandı: {path} → {dst}")
        return True
    except Exception as e:
        print(f"[HF ERR] {e}")
        return False


def backup_current() -> Path:
    if not TARGET.exists():
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = BACKUPS_DIR / f"fire_model_backup_{ts}.pt"
    shutil.copy2(TARGET, bak)
    print(f"[BACKUP] {TARGET.name} → {bak.name}")
    return bak


def list_backups() -> list[Path]:
    return sorted(BACKUPS_DIR.glob("fire_model_backup_*.pt"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hf", default="keremberke/yolov8m-fire-detection",
                    help="HuggingFace repo (user/model)")
    ap.add_argument("--hf-file", default="best.pt",
                    help="HF reposundaki dosya adı (genelde best.pt)")
    ap.add_argument("--url", default=None,
                    help="Direkt .pt URL — HF dışı kaynak için")
    ap.add_argument("--out", default=str(TARGET),
                    help="Hedef dosya (varsayılan fire_model.pt)")
    ap.add_argument("--restore", action="store_true",
                    help="En son yedeği geri yükle")
    ap.add_argument("--list", action="store_true",
                    help="Mevcut yedekleri listele")
    args = ap.parse_args()

    if args.list:
        for b in list_backups():
            sz = b.stat().st_size / 1e6
            print(f"  {b.name:50s}  {sz:6.1f} MB")
        return

    if args.restore:
        backups = list_backups()
        if not backups:
            print("[ERR] Yedek bulunamadı")
            sys.exit(1)
        latest = backups[-1]
        shutil.copy2(latest, TARGET)
        print(f"[RESTORE] {latest.name} → {TARGET.name}")
        return

    out = Path(args.out)
    backup_current()
    tmp = out.with_suffix(".downloading")

    # 1) URL verildiyse direkt indir
    if args.url:
        try:
            download(args.url, tmp)
        except Exception as e:
            print(f"[ERR] URL indirme başarısız: {e}")
            if tmp.exists():
                tmp.unlink()
            sys.exit(2)
    else:
        # 2) HF üzerinden indir (auth/redirect handler)
        if not download_hf(args.hf, args.hf_file, tmp):
            print("\nManuel indir:")
            print(f"  1) Tarayıcı: https://huggingface.co/{args.hf}/tree/main")
            print(f"  2) {args.hf_file} dosyasını indir")
            print(f"  3) mv ~/Downloads/{args.hf_file} {TARGET}")
            if tmp.exists():
                tmp.unlink()
            sys.exit(2)

    # Boyut kontrolü — 5 MB altı muhtemelen hata sayfası
    if tmp.stat().st_size < 5 * 1024 * 1024:
        print(f"[ERR] İndirilen dosya çok küçük ({tmp.stat().st_size} byte)")
        print("    Muhtemelen 404 veya HTML hata sayfası geldi.")
        tmp.unlink()
        sys.exit(3)

    tmp.replace(out)
    print(f"\n[OK] {out.name}  ({out.stat().st_size/1e6:.1f} MB)")
    print(f"\nŞimdi: ./run_demo.sh webcam   (yeni modeli kullanır)")
    print(f"Eski modele dönmek için: python ai/download_model.py --restore")


if __name__ == "__main__":
    main()
