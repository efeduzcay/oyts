#!/usr/bin/env python3
"""
evaluate.py — Eğitilmiş YOLOv8 yangın modelinin değerlendirilmesi
==================================================================
* Validation/test seti üzerinde mAP, P, R, F1
* Confusion matrix + PR curve + F1 curve görselleri
* Tek başına FPS ölçümü (warmup + 200 inference)
* Tek bir görüntü/dizin üzerinde tahmin örnekleri

Kullanım:
    python ai/evaluate.py --weights runs/detect/.../best.pt \
        --data datasets/fire_v3/data.yaml --split test
    python ai/evaluate.py --weights fire_model.pt --fps
    python ai/evaluate.py --weights fire_model.pt --predict ornekler/
"""

import argparse
import sys
import time
from pathlib import Path

try:
    import cv2
    import numpy as np
    import torch
    from ultralytics import YOLO
except ImportError as e:
    print(f"Eksik paket: {e}")
    sys.exit(1)


def pick_device(arg: str) -> str:
    if arg != "auto":
        return arg
    if torch.cuda.is_available():
        return "0"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def run_val(weights: str, data: str, split: str, device: str, imgsz: int):
    print(f"\n[VAL] {weights} → split={split}")
    model = YOLO(weights)
    metrics = model.val(
        data=data,
        split=split,
        imgsz=imgsz,
        device=device,
        plots=True,
        verbose=True,
    )
    print("\n" + "=" * 50)
    print(" Değerlendirme Sonuçları")
    print("=" * 50)
    print(f"  mAP50      : {metrics.box.map50:.4f}")
    print(f"  mAP50-95   : {metrics.box.map:.4f}")
    print(f"  Precision  : {metrics.box.mp:.4f}")
    print(f"  Recall     : {metrics.box.mr:.4f}")
    # Sınıf bazlı
    if hasattr(metrics.box, "ap_class_index"):
        names = model.names
        for idx, cls in enumerate(metrics.box.ap_class_index):
            print(f"  [{names[int(cls)]:8}] "
                  f"mAP50={metrics.box.ap50[idx]:.4f}  "
                  f"mAP50-95={metrics.box.ap[idx]:.4f}")
    print(f"\n  Grafikler: {metrics.save_dir}")


def run_fps(weights: str, device: str, imgsz: int, iters: int = 200):
    print(f"\n[FPS] {weights} üzerinde inference hız testi")
    model = YOLO(weights)
    dummy = np.random.randint(0, 255, (imgsz, imgsz, 3), dtype=np.uint8)
    # Warmup
    for _ in range(20):
        model.predict(dummy, device=device, verbose=False, imgsz=imgsz)
    # Ölçüm
    if device.startswith("0") or device.startswith("cuda"):
        torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        model.predict(dummy, device=device, verbose=False, imgsz=imgsz)
    if device.startswith("0") or device.startswith("cuda"):
        torch.cuda.synchronize()
    dt = time.perf_counter() - t0
    fps = iters / dt
    ms = dt / iters * 1000.0
    print(f"  Iter      : {iters}")
    print(f"  Device    : {device}")
    print(f"  imgsz     : {imgsz}")
    print(f"  Avg/iter  : {ms:.2f} ms")
    print(f"  FPS       : {fps:.1f}")


def run_predict(weights: str, src: str, device: str, conf: float, out: str):
    print(f"\n[PREDICT] {weights} → {src}")
    model = YOLO(weights)
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = model.predict(
        source=src,
        device=device,
        conf=conf,
        save=True,
        project=str(out_dir.parent),
        name=out_dir.name,
        exist_ok=True,
        verbose=False,
    )
    n = 0
    for r in results:
        n += len(r.boxes) if r.boxes is not None else 0
    print(f"  {len(results)} görüntü işlendi, toplam {n} tespit")
    print(f"  Çıktılar: {out_dir}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--data", default=None, help="data.yaml — val için")
    ap.add_argument("--split", default="test", choices=["train", "val", "test"])
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--fps", action="store_true", help="FPS testini çalıştır")
    ap.add_argument("--predict", default=None, help="Görüntü/dizin/video tahmin et")
    ap.add_argument("--predict-out", default="runs/eval/predict")
    ap.add_argument("--conf", type=float, default=0.40)
    args = ap.parse_args()

    if not Path(args.weights).exists():
        print(f"[ERR] Model bulunamadı: {args.weights}")
        sys.exit(1)

    device = pick_device(args.device)

    if args.data:
        run_val(args.weights, args.data, args.split, device, args.imgsz)
    if args.fps:
        run_fps(args.weights, device, args.imgsz)
    if args.predict:
        run_predict(args.weights, args.predict, device, args.conf, args.predict_out)

    if not (args.data or args.fps or args.predict):
        ap.error("En az bir mod ver: --data | --fps | --predict")


if __name__ == "__main__":
    main()
