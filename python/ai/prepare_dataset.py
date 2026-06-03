#!/usr/bin/env python3
"""
prepare_dataset.py — D-Fire + FASDD birleşik YOLO dataset hazırlayıcı
======================================================================
Çıktı yapısı:
    datasets/
      fire_v3/
        images/{train,val,test}/*.jpg
        labels/{train,val,test}/*.txt   (YOLO format: cls cx cy w h)
        data.yaml

Sınıflar:
    0: fire
    1: smoke

Kullanım:
    python ai/prepare_dataset.py --root datasets/fire_v3
    python ai/prepare_dataset.py --root datasets/fire_v3 --skip-download
    python ai/prepare_dataset.py --root datasets/fire_v3 --only dfire
"""

import argparse
import os
import random
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Optional

try:
    import requests
    from tqdm import tqdm
    import yaml
except ImportError as e:
    print(f"Eksik paket: {e}. Önce: pip install -r requirements.txt")
    sys.exit(1)


# D-Fire: Andre Pimenta — fire/smoke YOLO formatında zaten hazır
# Repo: github.com/gaiasd/DFireDataset
DFIRE_URLS = [
    "https://github.com/gaiasd/DFireDataset/releases/download/v1.0/D-Fire.zip",
]

# FASDD-CV: Fire And Smoke Detection Dataset (Computer Vision)
# Kaggle ya da Zenodo'dan indirilebilir; burada Zenodo doi
FASDD_URLS = [
    "https://zenodo.org/records/12790165/files/FASDD_CV.zip",
]

CLASSES = ["fire", "smoke"]


def download(url: str, dst: Path, chunk: int = 1 << 16) -> bool:
    """Tek dosya indirici, tqdm ile."""
    if dst.exists() and dst.stat().st_size > 1024:
        print(f"[SKIP] Zaten var: {dst.name}")
        return True
    try:
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            dst.parent.mkdir(parents=True, exist_ok=True)
            with open(dst, "wb") as f, tqdm(
                total=total, unit="B", unit_scale=True, desc=dst.name
            ) as bar:
                for buf in r.iter_content(chunk_size=chunk):
                    f.write(buf)
                    bar.update(len(buf))
        return True
    except Exception as e:
        print(f"[ERR] İndirme başarısız {url}: {e}")
        if dst.exists():
            dst.unlink()
        return False


def extract(archive: Path, dst_dir: Path) -> bool:
    dst_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive, "r") as zf:
            names = zf.namelist()
            for n in tqdm(names, desc=f"Açılıyor {archive.name}"):
                zf.extract(n, dst_dir)
        return True
    except Exception as e:
        print(f"[ERR] Arşiv açma hatası: {e}")
        return False


def find_yolo_pairs(root: Path):
    """root altında image/label çiftlerini bulur (recursive)."""
    image_exts = {".jpg", ".jpeg", ".png", ".bmp"}
    pairs = []
    for img in root.rglob("*"):
        if img.suffix.lower() not in image_exts:
            continue
        # YOLO etiket dosyası: aynı isim, .txt uzantı
        # Önce kardeş labels/ dizini, sonra aynı dizinde dener
        candidates = [
            img.with_suffix(".txt"),
            img.parent.parent / "labels" / (img.stem + ".txt"),
            img.parent / "labels" / (img.stem + ".txt"),
        ]
        lbl = next((c for c in candidates if c.exists()), None)
        if lbl is not None:
            pairs.append((img, lbl))
    return pairs


def remap_label(src_lbl: Path, dst_lbl: Path, class_map: dict):
    """Etiket dosyasını okuyup sınıf id'lerini yeniden eşler.
    Geçersiz/atılması gereken satırlar yok sayılır."""
    out_lines = []
    for line in src_lbl.read_text().splitlines():
        parts = line.strip().split()
        if len(parts) < 5:
            continue
        try:
            cls = int(parts[0])
        except ValueError:
            continue
        if cls not in class_map:
            continue
        new_cls = class_map[cls]
        out_lines.append(" ".join([str(new_cls)] + parts[1:5]))
    if not out_lines:
        return False
    dst_lbl.parent.mkdir(parents=True, exist_ok=True)
    dst_lbl.write_text("\n".join(out_lines) + "\n")
    return True


def split_pairs(pairs, ratios=(0.8, 0.1, 0.1), seed=42):
    random.seed(seed)
    pairs = list(pairs)
    random.shuffle(pairs)
    n = len(pairs)
    n_tr = int(n * ratios[0])
    n_va = int(n * ratios[1])
    return {
        "train": pairs[:n_tr],
        "val":   pairs[n_tr:n_tr + n_va],
        "test":  pairs[n_tr + n_va:],
    }


def materialize(splits, dst_root: Path, class_map: dict):
    """Image+label dosyalarını YOLO yapısına kopyalar."""
    counts = {"train": 0, "val": 0, "test": 0}
    for split, items in splits.items():
        img_dir = dst_root / "images" / split
        lbl_dir = dst_root / "labels" / split
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)
        for img, lbl in tqdm(items, desc=f"{split} kopyalanıyor"):
            stem = f"{img.parent.name}_{img.stem}"
            new_img = img_dir / (stem + img.suffix.lower())
            new_lbl = lbl_dir / (stem + ".txt")
            if not remap_label(lbl, new_lbl, class_map):
                continue
            shutil.copy2(img, new_img)
            counts[split] += 1
    return counts


def write_data_yaml(root: Path, counts: dict):
    data = {
        "path": str(root.resolve()),
        "train": "images/train",
        "val":   "images/val",
        "test":  "images/test",
        "names": {i: n for i, n in enumerate(CLASSES)},
    }
    yaml_path = root / "data.yaml"
    yaml_path.write_text(yaml.safe_dump(data, sort_keys=False))
    print(f"\n[OK] data.yaml yazıldı: {yaml_path}")
    print(f"     train={counts['train']}  val={counts['val']}  test={counts['test']}")
    return yaml_path


# Dataset bazlı sınıf eşlemeleri
# D-Fire orijinal: 0=smoke, 1=fire  → bizde 0=fire, 1=smoke
DFIRE_MAP = {0: 1, 1: 0}
# FASDD CV: 0=fire, 1=smoke
FASDD_MAP = {0: 0, 1: 1}


def prepare_dfire(raw_dir: Path, dst: Path):
    print("\n[D-Fire] yerel pair'lar aranıyor...")
    pairs = find_yolo_pairs(raw_dir)
    if not pairs:
        print(f"[WARN] D-Fire altında pair bulunamadı: {raw_dir}")
        return {}
    print(f"[D-Fire] {len(pairs)} image/label pair bulundu")
    splits = split_pairs(pairs)
    return materialize(splits, dst, DFIRE_MAP)


def prepare_fasdd(raw_dir: Path, dst: Path):
    print("\n[FASDD] yerel pair'lar aranıyor...")
    pairs = find_yolo_pairs(raw_dir)
    if not pairs:
        print(f"[WARN] FASDD altında pair bulunamadı: {raw_dir}")
        return {}
    print(f"[FASDD] {len(pairs)} image/label pair bulundu")
    splits = split_pairs(pairs)
    return materialize(splits, dst, FASDD_MAP)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="datasets/fire_v3",
                    help="Çıktı dataset dizini")
    ap.add_argument("--raw-dir", default="datasets/_raw",
                    help="İndirilen arşivler/açılan ham dosyalar")
    ap.add_argument("--skip-download", action="store_true",
                    help="İndirme atla, sadece _raw altındakini işle")
    ap.add_argument("--only", choices=["dfire", "fasdd"], default=None)
    args = ap.parse_args()

    dst_root = Path(args.root).resolve()
    raw_root = Path(args.raw_dir).resolve()
    raw_root.mkdir(parents=True, exist_ok=True)

    # 1) İndirme aşaması
    if not args.skip_download:
        if args.only in (None, "dfire"):
            for u in DFIRE_URLS:
                archive = raw_root / "dfire.zip"
                if download(u, archive):
                    extract(archive, raw_root / "dfire")
                    break
        if args.only in (None, "fasdd"):
            for u in FASDD_URLS:
                archive = raw_root / "fasdd.zip"
                if download(u, archive):
                    extract(archive, raw_root / "fasdd")
                    break

    # 2) Eski çıktıyı temizle
    if dst_root.exists():
        print(f"[CLEAN] Eski çıktı siliniyor: {dst_root}")
        shutil.rmtree(dst_root)

    # 3) Topla & dönüştür
    total_counts = {"train": 0, "val": 0, "test": 0}
    if args.only in (None, "dfire"):
        c = prepare_dfire(raw_root / "dfire", dst_root)
        for k, v in c.items():
            total_counts[k] += v
    if args.only in (None, "fasdd"):
        c = prepare_fasdd(raw_root / "fasdd", dst_root)
        for k, v in c.items():
            total_counts[k] += v

    if sum(total_counts.values()) == 0:
        print("[ERR] Hiç örnek hazırlanamadı. --raw-dir altına dataset'i manuel yerleştir.")
        sys.exit(1)

    # 4) data.yaml
    yaml_path = write_data_yaml(dst_root, total_counts)
    print(f"\n[OK] Eğitime hazır. Şimdi:")
    print(f"     python ai/train.py --data {yaml_path}")


if __name__ == "__main__":
    main()
