#!/usr/bin/env python3
"""
train.py — YOLOv8 Yangın & Duman Modeli Eğitici
=================================================
Güçlü hiperparametrelerle (ağır augmentation, cosine LR, EMA, AMP)
fire/smoke için özelleştirilmiş eğitim.

Hızlı:
    python ai/train.py --data datasets/fire_v3/data.yaml

Profesyonel (300 epoch):
    python ai/train.py --data datasets/fire_v3/data.yaml \
        --model yolov8m.pt --epochs 300 --imgsz 640 --batch 32

Sonuç: runs/detect/fire_v3_<ts>/weights/best.pt
"""

import argparse
import sys
import shutil
from datetime import datetime
from pathlib import Path

try:
    import torch
    from ultralytics import YOLO
except ImportError as e:
    print(f"Eksik paket: {e}. Önce: pip install -r requirements.txt")
    sys.exit(1)


def pick_device(arg: str) -> str:
    if arg != "auto":
        return arg
    if torch.cuda.is_available():
        return "0"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


PRESETS = {
    # MacBook M4 Air (pasif soğutma, 16-24GB unified memory)
    "mac-air": {
        "model": "yolov8n.pt", "epochs": 100, "imgsz": 480,
        "batch": 16, "workers": 4, "device": "mps", "patience": 25,
    },
    # MacBook Pro M-serisi (aktif soğutma, daha çok core)
    "mac-pro": {
        "model": "yolov8s.pt", "epochs": 150, "imgsz": 640,
        "batch": 16, "workers": 6, "device": "mps", "patience": 30,
    },
    # NVIDIA mid-range (RTX 3060/4060)
    "cuda-mid": {
        "model": "yolov8s.pt", "epochs": 200, "imgsz": 640,
        "batch": 32, "workers": 8, "device": "0", "patience": 40,
    },
    # NVIDIA high-end (RTX 4080/4090)
    "cuda-hi": {
        "model": "yolov8m.pt", "epochs": 300, "imgsz": 640,
        "batch": 32, "workers": 8, "device": "0", "patience": 40,
    },
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="data.yaml yolu")
    ap.add_argument("--preset", choices=list(PRESETS.keys()),
                    help="Donanıma göre hazır preset (mac-air, mac-pro, cuda-mid, cuda-hi)")
    ap.add_argument("--model", default=None,
                    help="Başlangıç modeli: yolov8n.pt/s/m/l/x")
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument("--imgsz", type=int, default=None)
    ap.add_argument("--batch", type=int, default=None,
                    help="VRAM/bellek'e göre ayarla. -1 = otomatik")
    ap.add_argument("--device", default=None)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--patience", type=int, default=None,
                    help="Early stopping sabrı (epoch)")
    ap.add_argument("--project", default="runs/detect")
    ap.add_argument("--name", default=None)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--export-deploy", action="store_true",
                    help="Eğitim sonrası best.pt'i python/fire_model.pt'e kopyala")
    args = ap.parse_args()

    # Preset uygula → komut satırı override eder
    preset = PRESETS.get(args.preset, {})
    if args.model is None:    args.model = preset.get("model", "yolov8s.pt")
    if args.epochs is None:   args.epochs = preset.get("epochs", 200)
    if args.imgsz is None:    args.imgsz = preset.get("imgsz", 640)
    if args.batch is None:    args.batch = preset.get("batch", 16)
    if args.device is None:   args.device = preset.get("device", "auto")
    if args.workers is None:  args.workers = preset.get("workers", 8)
    if args.patience is None: args.patience = preset.get("patience", 40)

    # M4 Air uyarısı
    if args.preset and args.preset.startswith("mac"):
        print("\n⚠ MacBook M-serisi preset aktif.")
        print("  Termal throttling önlemek için:")
        print("  • Pil değil, şarjda eğit")
        print("  • Düz yüzey, hava sirkülasyonu engelli olmasın")
        print("  • Diğer ağır uygulamaları kapat\n")

    device = pick_device(args.device)
    run_name = args.name or f"fire_v3_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    print("=" * 60)
    print(" YOLOv8 Yangın Modeli Eğitimi")
    print("=" * 60)
    print(f"  data    : {args.data}")
    print(f"  model   : {args.model}")
    print(f"  epochs  : {args.epochs}")
    print(f"  imgsz   : {args.imgsz}")
    print(f"  batch   : {args.batch}")
    print(f"  device  : {device}")
    print(f"  run     : {args.project}/{run_name}")
    print("=" * 60)

    if device.startswith("0") or device.startswith("cuda"):
        # CUDA bilgilerini bas
        print(f"  CUDA    : {torch.version.cuda}")
        print(f"  GPU     : {torch.cuda.get_device_name(0)}")
        print(f"  VRAM    : {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    model = YOLO(args.model)

    # Güçlü eğitim hiperparametreleri
    # Yangın gibi parlak/saturasyonlu objelerde hsv_v ve mixup özellikle önemli
    results = model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=device,
        workers=args.workers,
        project=args.project,
        name=run_name,
        resume=args.resume,
        exist_ok=True,
        patience=args.patience,
        # Optimizer
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,           # final lr factor (cosine)
        cos_lr=True,
        momentum=0.937,
        weight_decay=0.0005,
        warmup_epochs=3.0,
        # Loss ağırlıkları (yangın küçük objeler de olabilir)
        box=7.5,
        cls=0.5,
        dfl=1.5,
        # AMP & EMA
        amp=True,
        # Ağır augmentation — yangın görüntüleri çok değişken
        hsv_h=0.015,
        hsv_s=0.70,
        hsv_v=0.50,          # parlaklık varyasyonu (gece/gündüz)
        degrees=10.0,
        translate=0.10,
        scale=0.50,
        shear=2.0,
        perspective=0.0005,
        flipud=0.0,
        fliplr=0.5,
        mosaic=1.0,
        mixup=0.15,
        copy_paste=0.10,
        # Validation
        val=True,
        save=True,
        save_period=10,
        plots=True,
        verbose=True,
        seed=42,
    )

    best = Path(args.project) / run_name / "weights" / "best.pt"
    last = Path(args.project) / run_name / "weights" / "last.pt"
    print("\n" + "=" * 60)
    print(" Eğitim tamamlandı")
    print("=" * 60)
    print(f"  best : {best}")
    print(f"  last : {last}")

    if args.export_deploy and best.exists():
        deploy_path = Path(__file__).resolve().parent.parent / "fire_model.pt"
        shutil.copy2(best, deploy_path)
        print(f"\n[DEPLOY] {best} → {deploy_path}")
        print("         pc_vision_controller.py artık yeni modeli kullanacak.")

    # Hızlı val raporu
    print("\n[VAL] Final validation metrikleri:")
    print(f"  mAP50    : {results.box.map50:.4f}")
    print(f"  mAP50-95 : {results.box.map:.4f}")
    print(f"  Precision: {results.box.mp:.4f}")
    print(f"  Recall   : {results.box.mr:.4f}")


if __name__ == "__main__":
    main()
