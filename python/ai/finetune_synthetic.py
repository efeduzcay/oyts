#!/usr/bin/env python3
"""
ai/finetune_synthetic.py — Mevcut fire_model.pt'i sentetik veride fine-tune et
==============================================================================
Sentetik FireSceneGenerator'den N frame + GT etiket üretir, train/val'a böler,
data.yaml yazar ve `ai/train.py` benzeri konfig ile fine-tune başlatır.

Catastrophic forgetting'i azaltmak için:
  * Backbone'un çoğu freeze (yalnız head + son C2f bloğu eğitilir)
  * Düşük LR (1e-4), kısa epoch (30 varsayılan)
  * Hafif augmentation (HSV varyasyonu zaten sentetikte yüksek)

Kullanım:
    python ai/finetune_synthetic.py
    python ai/finetune_synthetic.py --frames 5000 --epochs 30 \\
        --base fire_model.pt --out fire_model_v311_mixed.pt
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

try:
    import torch
    import yaml
    from ultralytics import YOLO
except ImportError as e:
    print(f"Eksik paket: {e}")
    sys.exit(1)

THIS_DIR = Path(__file__).resolve().parent
ROOT = THIS_DIR.parent
sys.path.insert(0, str(ROOT))

from sim.fire_scene_generator import dump_synthetic_dataset  # noqa: E402


def pick_device(arg: str) -> str:
    if arg != "auto":
        return arg
    if torch.cuda.is_available():
        return "0"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def make_dataset(out: Path, n_frames: int, width: int, height: int,
                 val_ratio: float, seed: int) -> Path:
    """Sentetik dataset üret + data.yaml yaz. data.yaml yolunu döner.

    Düzen:
      out/
        images/train/*.jpg
        images/val/*.jpg
        labels/train/*.txt
        labels/val/*.txt
        data.yaml
    """
    n_val = max(50, int(n_frames * val_ratio))
    n_train = n_frames - n_val
    train_dir = out / "_tmp_train"
    val_dir = out / "_tmp_val"

    print(f"\n[DATA] Sentetik üretim: train={n_train}, val={n_val} → {out}")
    t0 = time.perf_counter()
    dump_synthetic_dataset(str(train_dir), n_frames=n_train,
                           width=width, height=height, seed=seed)
    dump_synthetic_dataset(str(val_dir), n_frames=n_val,
                           width=width, height=height, seed=seed + 9999)
    dt = time.perf_counter() - t0
    print(f"[DATA] Üretim {dt:.0f} s sürdü")

    # YOLO yapısına yeniden organize et
    img_tr = out / "images" / "train"; img_tr.mkdir(parents=True, exist_ok=True)
    img_va = out / "images" / "val";   img_va.mkdir(parents=True, exist_ok=True)
    lbl_tr = out / "labels" / "train"; lbl_tr.mkdir(parents=True, exist_ok=True)
    lbl_va = out / "labels" / "val";   lbl_va.mkdir(parents=True, exist_ok=True)

    for src_root, img_dst, lbl_dst in (
        (train_dir, img_tr, lbl_tr),
        (val_dir,   img_va, lbl_va),
    ):
        for img in (src_root / "images").iterdir():
            shutil.move(str(img), str(img_dst / img.name))
        for lbl in (src_root / "labels").iterdir():
            shutil.move(str(lbl), str(lbl_dst / lbl.name))
        shutil.rmtree(src_root, ignore_errors=True)

    yaml_path = out / "data.yaml"
    data = {
        "path": str(out.resolve()),
        "train": "images/train",
        "val": "images/val",
        "names": {0: "fire", 1: "smoke"},
    }
    yaml_path.write_text(yaml.safe_dump(data, sort_keys=False))
    print(f"[DATA] data.yaml → {yaml_path}")
    return yaml_path


def fine_tune(base_weights: Path, data_yaml: Path, out_model: Path,
              epochs: int, imgsz: int, batch: int, device: str,
              freeze: int, lr0: float, project: Path) -> None:
    """Fine-tune ve best.pt'i out_model olarak kopyala."""
    print(f"\n[TUNE] base={base_weights} epochs={epochs} freeze={freeze}")
    print(f"[TUNE] data={data_yaml} device={device} imgsz={imgsz} batch={batch}")

    model = YOLO(str(base_weights))
    run_name = f"synfinetune_{int(time.time())}"
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
        freeze=freeze,                  # backbone katmanlarını dondur
        optimizer="AdamW",
        lr0=lr0,                        # düşük → catastrophic forgetting az
        lrf=0.1,
        cos_lr=True,
        patience=15,
        # Sentetik zaten varyatif → hafif augmentation
        hsv_h=0.010, hsv_s=0.40, hsv_v=0.30,
        degrees=5.0, translate=0.05, scale=0.30,
        mosaic=0.5, mixup=0.0, copy_paste=0.0,
        amp=True,
        plots=True,
        verbose=True,
        seed=42,
    )

    best = project / run_name / "weights" / "best.pt"
    if not best.exists():
        print(f"[ERR] best.pt bulunamadı: {best}")
        sys.exit(2)
    shutil.copy2(best, out_model)
    print("\n" + "=" * 60)
    print(" FINE-TUNE TAMAMLANDI")
    print("=" * 60)
    print(f"  best.pt  : {best}")
    print(f"  deploy   : {out_model}")
    try:
        print(f"  mAP50    : {results.box.map50:.4f}")
        print(f"  mAP50-95 : {results.box.map:.4f}")
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=5000)
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--val-ratio", type=float, default=0.15)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--freeze", type=int, default=10,
                    help="İlk N katmanı dondur (yolov8: backbone 0-9)")
    ap.add_argument("--lr0", type=float, default=1e-4)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--base", default=str(ROOT / "fire_model.pt"))
    ap.add_argument("--out", default=str(ROOT / "fire_model_v311_mixed.pt"))
    ap.add_argument("--dataset-dir",
                    default=str(ROOT / "datasets" / "synthetic_v311"))
    ap.add_argument("--project", default=str(ROOT / "runs" / "finetune"))
    ap.add_argument("--skip-dataset", action="store_true",
                    help="Dataset zaten var, tekrar üretme")
    args = ap.parse_args()

    base = Path(args.base)
    out = Path(args.out)
    ds_dir = Path(args.dataset_dir)
    project = Path(args.project)

    if not base.exists():
        print(f"[ERR] Base model yok: {base}")
        sys.exit(1)

    device = pick_device(args.device)

    if args.skip_dataset and (ds_dir / "data.yaml").exists():
        data_yaml = ds_dir / "data.yaml"
        print(f"[DATA] Mevcut dataset kullanılıyor: {data_yaml}")
    else:
        ds_dir.mkdir(parents=True, exist_ok=True)
        data_yaml = make_dataset(ds_dir, args.frames, args.width, args.height,
                                 args.val_ratio, args.seed)

    fine_tune(base, data_yaml, out,
              epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
              device=device, freeze=args.freeze, lr0=args.lr0,
              project=project)


if __name__ == "__main__":
    main()
