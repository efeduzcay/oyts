#!/usr/bin/env python3
"""
ai/train_roboflow.py — Roboflow dataset'i indirip mevcut modele fine-tune
===========================================================================
Roboflow Universe'dan dataset çeker, YOLO formatında hazırlar, mevcut
fire_model.pt'ye fine-tune eder, sonucu fire_model_roboflow.pt olarak yazar.

İlk kullanım için: pip install roboflow ultralytics (zaten var olabilir)

Kullanım:
    python ai/train_roboflow.py --api-key KEY \\
        --workspace fire-detection --project fire-detection-data-pre \\
        --version 4 --epochs 15

    # Sadece dataset indir, eğitime başlama:
    python ai/train_roboflow.py --api-key KEY ... --download-only

    # Eski dataset varsa yeniden indirme:
    python ai/train_roboflow.py --epochs 15 --skip-download \\
        --data datasets/fire-detection-data-pre-4/data.yaml
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THIS_DIR = Path(__file__).resolve().parent


def ensure_packages() -> None:
    """roboflow + ultralytics zaten yoksa kur."""
    needed = []
    try:
        import roboflow  # noqa
    except ImportError:
        needed.append("roboflow")
    try:
        import ultralytics  # noqa
    except ImportError:
        needed.append("ultralytics")
    if needed:
        print(f"[PIP] kuruluyor: {needed}")
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               "-q", "--user"] + needed)


def download_dataset(api_key: str, workspace: str, project: str,
                     version: int, out_dir: Path) -> Path:
    """Roboflow snippet'ini çalıştır → datasets/PROJECT-VERSION/data.yaml döner."""
    from roboflow import Roboflow
    print(f"[ROBOFLOW] {workspace}/{project} v{version}")
    rf = Roboflow(api_key=api_key)
    proj = rf.workspace(workspace).project(project)
    ver = proj.version(version)
    # Roboflow datasetleri cwd'ye iner; cwd'yi datasets/ yapalım
    out_dir.mkdir(parents=True, exist_ok=True)
    cwd = Path.cwd()
    try:
        import os
        os.chdir(out_dir)
        dataset = ver.download("yolov8")
        ds_path = Path(dataset.location) / "data.yaml"
    finally:
        os.chdir(cwd)
    if not ds_path.exists():
        # Bazen iç path farklı — recursive ara
        cands = list(out_dir.rglob("data.yaml"))
        if not cands:
            raise FileNotFoundError(f"data.yaml bulunamadı: {out_dir}")
        ds_path = cands[0]
    print(f"[ROBOFLOW] data.yaml: {ds_path}")
    return ds_path


def fine_tune(base: Path, data_yaml: Path, out: Path,
              epochs: int, imgsz: int, batch: int, device: str,
              freeze: int, lr0: float, project: Path) -> None:
    """Mevcut ağırlıkları base alıp yeni veri üstünde fine-tune."""
    import torch
    from ultralytics import YOLO

    if device == "auto":
        if torch.cuda.is_available():
            device = "0"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"

    print(f"[TUNE] base={base.name} epochs={epochs} device={device}")
    model = YOLO(str(base))
    run_name = f"roboflow_{int(time.time())}"
    results = model.train(
        data=str(data_yaml),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        workers=4,
        project=str(project),
        name=run_name,
        exist_ok=True,
        freeze=freeze,
        optimizer="AdamW",
        lr0=lr0,
        lrf=0.1,
        cos_lr=True,
        patience=10,
        # Gerçek dünya görüntüleri zaten varyatif → orta augmentation
        hsv_h=0.015, hsv_s=0.50, hsv_v=0.40,
        degrees=8.0, translate=0.08, scale=0.40,
        mosaic=0.7, mixup=0.05, copy_paste=0.0,
        amp=True,
        plots=True,
        verbose=True,
        seed=42,
    )
    best = project / run_name / "weights" / "best.pt"
    if not best.exists():
        print(f"[ERR] best.pt bulunamadı: {best}")
        sys.exit(2)
    # Eski model yedekle, yenisini koy
    if out.exists():
        bak = out.with_name(f"{out.stem}_bak_{int(time.time())}.pt")
        shutil.copy2(out, bak)
        print(f"[BACKUP] {out.name} → {bak.name}")
    shutil.copy2(best, out)
    print("\n" + "=" * 60)
    print(" EĞİTİM BİTTİ — model swap edildi")
    print("=" * 60)
    print(f"  best.pt → {out}")
    try:
        print(f"  mAP50 : {results.box.map50:.4f}")
        print(f"  mAP   : {results.box.map:.4f}")
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--workspace", default="fire-detection")
    ap.add_argument("--project", default="fire-detection-data-pre")
    ap.add_argument("--version", type=int, default=4)
    ap.add_argument("--datasets-root",
                    default=str(ROOT / "datasets"),
                    help="Roboflow indirme kök dizini")
    ap.add_argument("--data", default=None,
                    help="data.yaml yolu (--skip-download ile)")
    ap.add_argument("--skip-download", action="store_true")
    ap.add_argument("--download-only", action="store_true")
    ap.add_argument("--base", default=str(ROOT / "fire_model_v3_real.pt"),
                    help="Fine-tune base ağırlığı")
    ap.add_argument("--out", default=str(ROOT / "fire_model_roboflow.pt"),
                    help="Yeni model çıktısı")
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--freeze", type=int, default=10)
    ap.add_argument("--lr0", type=float, default=2e-4)
    ap.add_argument("--project-runs", default=str(ROOT / "runs" / "roboflow"))
    args = ap.parse_args()

    ensure_packages()

    if args.skip_download:
        if not args.data:
            print("[ERR] --skip-download için --data PATH gerek")
            sys.exit(1)
        data_yaml = Path(args.data)
    else:
        if not args.api_key:
            print("[ERR] --api-key gerek (Roboflow API key)")
            sys.exit(1)
        data_yaml = download_dataset(
            args.api_key, args.workspace, args.project, args.version,
            Path(args.datasets_root))

    if args.download_only:
        print(f"\n[OK] Dataset hazır: {data_yaml}")
        return

    base = Path(args.base)
    # yolov8n.pt, yolov8s.pt, yolov8m.pt gibi ultralytics standart adları
    # dosyada yoksa ultralytics auto-download eder — OK say.
    ULTRA_AUTO = {"yolov8n.pt", "yolov8s.pt", "yolov8m.pt",
                  "yolov8l.pt", "yolov8x.pt"}
    if not base.exists() and base.name not in ULTRA_AUTO:
        print(f"[ERR] Base model yok: {base}")
        sys.exit(1)
    out = Path(args.out)
    project = Path(args.project_runs)

    fine_tune(base, data_yaml, out,
              epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
              device=args.device, freeze=args.freeze, lr0=args.lr0,
              project=project)

    print("\n  Şimdi config'i yeni modele yönlendir:")
    print(f"  sed -i '' 's|fire_model.*\\.pt|{out.name}|' python/configs/config_webcam.yaml")
    print(f"  ./run_demo.sh stop && ./run_demo.sh webcam")


if __name__ == "__main__":
    main()
