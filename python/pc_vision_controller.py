#!/usr/bin/env python3
"""
pc_vision_controller.py — Yangın Tespit Robotu / PC Kontrol
============================================================
PROFESYONEL SÜRÜM v5.0.0
    * YOLOv8 entegrasyonu
    * YAML tabanlı merkezi konfigürasyon (configs/config.yaml)
    * IoU tabanlı çoklu hedef takipçisi (titreme önler)
    * Bulanık Mantık (Mamdani) öncelik skorlaması
    * Simulated Annealing rota optimizasyonu
    * Sentetik yangın sahnesi (sim/) ile simülasyon desteği
    * CSV telemetri logu + video kaydı
    * Komut yumuşatma (oy çokluğu) → motor titremesini önler
    * Smoke vs Fire ayrımı + öncelik çarpanı
    * Thread-safe seri haberleşme + otomatik yeniden bağlanma

Kullanım:
    python pc_vision_controller.py
    python pc_vision_controller.py --config configs/config.yaml
    python pc_vision_controller.py --config configs/config.yaml --sim synthetic
"""

from __future__ import annotations

import argparse
import logging
import math
import os
import platform
import random
import sys

# macOS AVFoundation: cv2.VideoCapture'ı background thread'de açtığımız için
# izin sorgusu "can not spin main run loop" hatası verir. İzin zaten verildiyse
# auth sorgusunu atla — kamera direkt açılır.
os.environ.setdefault("OPENCV_AVFOUNDATION_SKIP_AUTH", "1")
# Windows MSMF backend bazı USB webcam'lerde 30+ sn donuyor → DSHOW kullanıyoruz.
# Bu env var MSMF HW transformations'ı atlar (yan etkisi yok).
os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")
import threading
import time

# Platform tespit: webcam backend seçimi
_IS_WINDOWS = platform.system() == "Windows"
_IS_MACOS   = platform.system() == "Darwin"
import urllib.request
from collections import Counter, deque
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
import requests
import serial
import serial.tools.list_ports


def _webcam_backend() -> int:
    """Platforma göre en sağlam VideoCapture backend'i.
    Windows: DSHOW (MSMF yavaş ve bazen kilitleniyor).
    macOS:   AVFoundation. Linux: V4L2."""
    if _IS_WINDOWS:
        return cv2.CAP_DSHOW
    if _IS_MACOS:
        return cv2.CAP_AVFOUNDATION
    return cv2.CAP_V4L2


def webcam_failure_hint(idx: int = 0) -> str:
    """Platforma göre kamera açılamama nedeni rehberi (tek kaynak).

    web_app.py ve pc_vision_controller.py ortak kullanır → mesaj tutarlı kalır.
    """
    if _IS_MACOS:
        return (
            f"Webcam açılamadı (index={idx}). macOS izin sorunu olabilir.\n"
            "  • System Settings → Privacy & Security → Camera listesinde\n"
            "    bu uygulamayı (Terminal / iTerm vs.) AÇIK yapın.\n"
            "  • Uygulamayı Cmd+Q ile tam kapatıp yeniden başlatın.\n"
            "  • Başka uygulama kamerayı kullanıyor olabilir (Zoom/Teams/tarayıcı).\n"
            "  • Continuity Camera (iPhone) varsa farklı index deneyin\n"
            "    (configs/config_webcam.yaml → mode.webcam_index: 1)."
        )
    if _IS_WINDOWS:
        return (
            f"Webcam açılamadı (index={idx}). Windows izin/sürücü sorunu olabilir.\n"
            "  • Ayarlar → Gizlilik ve Güvenlik → Kamera → 'Masaüstü\n"
            "    uygulamalarının kameraya erişmesine izin ver' AÇIK olmalı.\n"
            "  • Başka uygulama (Zoom/Teams/tarayıcı sekmeleri) kamerayı\n"
            "    kullanıyor olabilir.\n"
            "  • Farklı index deneyin: configs/config_webcam.yaml →\n"
            "    mode.webcam_index: 1 (0, 1, 2…).\n"
            "  • USB kamerayı çıkarıp yeniden takın."
        )
    return (
        f"Webcam açılamadı (index={idx}). Linux V4L2 sorunu olabilir.\n"
        "  • Kullanıcı 'video' grubunda mı? (usermod -a -G video $USER)\n"
        "  • /dev/video{idx} mevcut mu? (ls /dev/video*)\n"
        "  • Başka uygulama kamerayı kullanıyor olabilir (fuser /dev/video0).\n"
        "  • Farklı index deneyin: configs/config_webcam.yaml →\n"
        "    mode.webcam_index: 1."
    )


def _open_esp32_stream(url: str, logger: logging.Logger,
                       timeout_sec: float = 8.0):
    """ESP32-CAM (veya başka uzak MJPEG) stream'ini açar.

    Açma + okuma için ms-cinsinden timeout uygular ki ölü/durmuş stream'de
    main loop'ta sonsuz beklemeyiz. Bazı driver'lar bu property'leri reddeder
    → set hatasını yutuyoruz (yan etkisiz, sadece timeout devre dışı kalır).
    """
    logger.info("ESP32-CAM stream açılıyor: %s", url)
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        logger.error(
            "ESP32-CAM stream açılamadı: %s — tarayıcıdan URL'yi deneyin, "
            "WiFi/IP doğru mu?", url)
        try:
            cap.release()
        except Exception:
            pass
        return None
    ms = int(max(0.1, float(timeout_sec)) * 1000)
    for prop in (cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
                 cv2.CAP_PROP_READ_TIMEOUT_MSEC):
        try:
            cap.set(prop, ms)
        except Exception:
            # Eski OpenCV / driver bu property'yi tanımıyor → sessiz geç
            pass
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass
    return cap


def _probe_webcam(idx: int) -> dict:
    """Bir webcam index'inin açılıp açılmadığını hızlıca test eder.

    Kamera kilidini tutmamak için anında release eder. Read denemiyoruz —
    salt isOpened() yeterince hızlı + güvenli (warmup yapmıyoruz, çünkü
    bu sadece "var mı yok mu" kontrolü).
    """
    backend = _webcam_backend()
    info = {"index": int(idx), "available": False, "width": 0, "height": 0}
    try:
        cap = cv2.VideoCapture(int(idx), backend)
    except Exception:
        return info
    try:
        if cap.isOpened():
            info["available"] = True
            try:
                info["width"]  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                info["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            except Exception:
                pass
    finally:
        try:
            cap.release()
        except Exception:
            pass
    return info


def list_webcams(max_index: int = 4) -> list:
    """0..max_index-1 aralığını tarar, her index için probe sonucunu döner."""
    return [_probe_webcam(i) for i in range(max(0, int(max_index)))]


def _open_webcam_with_fallback(idx: int, logger: logging.Logger):
    """Webcam açar; backend, warmup, çözünürlük dahil tüm hassas adımları
    tek yerde toplar. None döner → çağıran reconnect mantığına geçer."""
    backend = _webcam_backend()
    backend_name = {cv2.CAP_DSHOW: "DSHOW",
                    cv2.CAP_AVFOUNDATION: "AVFoundation",
                    cv2.CAP_V4L2: "V4L2"}.get(backend, str(backend))
    logger.info("webcam açılıyor: index=%d backend=%s", idx, backend_name)
    cap = cv2.VideoCapture(idx, backend)
    if not cap.isOpened():
        logger.warning("%s backend ile açılamadı, varsayılan deneniyor...",
                       backend_name)
        try:
            cap.release()
        except Exception:
            pass
        cap = cv2.VideoCapture(idx)
        if not cap.isOpened():
            logger.error("WEBCAM AÇILAMADI:\n%s", webcam_failure_hint(idx))
            try:
                cap.release()
            except Exception:
                pass
            return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass
    # Warmup: ilk birkaç kare DSHOW'da bazen siyah/boş geliyor
    for _ in range(10):
        ok, fr = cap.read()
        if ok and fr is not None and fr.size > 0:
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            f = cap.get(cv2.CAP_PROP_FPS)
            logger.info("✓ webcam hazır: %dx%d @ %.0f fps", w, h, f)
            return cap
        time.sleep(0.1)
    logger.error("webcam açıldı ama kare okunamadı — driver donmuş olabilir")
    try:
        cap.release()
    except Exception:
        pass
    return None

try:
    # Eski ultralytics namespace (ultralytics.yolo.*) ile eğitilmiş .pt dosyaları
    # için modül takma adları — yeni ultralytics modülünü görür.
    import ultralytics.models.yolo as _u_yolo
    import ultralytics.utils as _u_utils
    sys.modules.setdefault("ultralytics.yolo", _u_yolo)
    sys.modules.setdefault("ultralytics.yolo.utils", _u_utils)
    from ultralytics import YOLO
except ImportError:
    print("Ultralytics kurulu değil. `pip install -r requirements.txt`")
    sys.exit(1)

# Lokal modüller
THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
from ai.tracker import IoUTracker, Track                 # noqa: E402
from ai.heatmap import FireHeatmap                        # noqa: E402
from ai.distance import DistanceEstimator                 # noqa: E402
from ai.webhook import WebhookNotifier                    # noqa: E402
from ai.sim_detector import SimDetectionInjector         # noqa: E402
from ai.fire_validator import FireValidator               # noqa: E402
from ai.bright_flame_detector import BrightFlameDetector  # noqa: E402
from sim.fire_scene_generator import (                   # noqa: E402
    FireSceneGenerator, SceneConfig,
)
from utils.config_loader import load_config, ConfigDict   # noqa: E402
from utils.csv_logger import CSVLogger                    # noqa: E402
from utils.dashboard import Dashboard, DashboardContext   # noqa: E402


# 1. LOGGING
class _ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\x1b[38;20m",
        logging.INFO: "\x1b[37m",
        logging.WARNING: "\x1b[33;20m",
        logging.ERROR: "\x1b[31;20m",
        logging.CRITICAL: "\x1b[31;1m",
    }
    RESET = "\x1b[0m"
    FMT = "[%(asctime)s] [%(levelname)s] %(message)s"

    def format(self, record):
        c = self.COLORS.get(record.levelno, "")
        return logging.Formatter(c + self.FMT + self.RESET, "%H:%M:%S").format(record)


def setup_logger(out_dir: Path) -> logging.Logger:
    out_dir.mkdir(parents=True, exist_ok=True)
    lg = logging.getLogger("RobotController")
    if lg.handlers:
        return lg
    lg.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(_ColorFormatter())
    fh = logging.FileHandler(out_dir / "system.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s"))
    lg.addHandler(ch)
    lg.addHandler(fh)
    return lg


# 2. DURUM & VERİ
class State(Enum):
    SEARCHING = auto()
    APPROACHING = auto()
    TOO_CLOSE = auto()
    HEAT_ACTION = auto()
    MANUAL = auto()


class Target:
    __slots__ = ("cx", "cy", "area", "priority", "label",
                 "track_id", "conf", "bbox", "hits", "missed")

    def __init__(self, cx, cy, area, priority, label,
                 track_id=0, conf=0.0, bbox=None, hits=0, missed=0):
        self.cx = cx
        self.cy = cy
        self.area = area
        self.priority = priority
        self.label = label
        self.track_id = track_id
        self.conf = conf
        # (x1, y1, x2, y2) — real bbox from tracker, used for overlays.
        # None = no bbox (legacy) → consumers fall back to sqrt(area) square.
        self.bbox = bbox
        self.hits = hits
        self.missed = missed


# 2.b HSV bbox refinement
# Model bazen alevi içeren ama 5-10 katı büyüklükte bir bbox üretir.
# Bu fonksiyon ROI içindeki parlak turuncu/sarı/kırmızı (alev rengi)
# bölgeyi HSV maskesi ile bulup gerçek bbox'ı döndürür.
# Bulamazsa (None, None, None, None) döner — çağıran orijinal bbox'ı korur.
def _refine_flame_bbox(frame, x1, y1, x2, y2):
    roi = frame[y1:y2, x1:x2]
    if roi.size == 0:
        return None, None, None, None
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    # Alev rengi: sıcak hue, YÜKSEK S + YÜKSEK V (ten rengi V<200 olur, eler).
    # Çakmak/mum alevleri V≈255'e kadar parlar, ten rengi nadiren V>220.
    # Alev: yüksek S + çok yüksek V. Ten/dudak ÇOK saturated değildir (S<170)
    # ve sürekli V>230 olmaz. Çakmak/mum alevi her ikisini de aşar.
    m1 = cv2.inRange(hsv, (5,   180, 230), (30,  255, 255))   # turuncu-sarı parlak
    # Kırmızının HSV wrap'i
    m2 = cv2.inRange(hsv, (160, 200, 230), (180, 255, 255))
    # Alev çekirdeği — beyaza yakın sarımsı, V çok yüksek (ten asla V>240 olmaz)
    m3 = cv2.inRange(hsv, (15,  40,  248), (55,  255, 255))
    mask = m1 | m2 | m3
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=2)

    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None, None, None, None
    c = max(cnts, key=cv2.contourArea)
    if cv2.contourArea(c) < 300:   # küçük dudak/ten parlamaları elensin
        return None, None, None, None
    rx, ry, rw, rh = cv2.boundingRect(c)
    # ROI koordinatından frame koordinatına çevir, biraz pad bırak
    pad = 6
    nx1 = max(0, x1 + rx - pad)
    ny1 = max(0, y1 + ry - pad)
    nx2 = min(frame.shape[1] - 1, x1 + rx + rw + pad)
    ny2 = min(frame.shape[0] - 1, y1 + ry + rh + pad)
    if nx2 <= nx1 or ny2 <= ny1:
        return None, None, None, None
    return nx1, ny1, nx2, ny2


# 3. GÖRÜNTÜ İŞLEME & AI
class VisionProcessor:
    def __init__(self, cfg: ConfigDict, logger: logging.Logger):
        self.cfg = cfg
        self.logger = logger

        self._fuzzy_sets = {k: list(v) for k, v in cfg.fuzzy.sets.items()}
        self._fuzzy_out = dict(cfg.fuzzy.outputs)
        self._area_history = deque(maxlen=5)

        self.last_raw_count = 0
        self.last_raw_max_conf = 0.0
        self.last_class_breakdown = {}  # {label: (count, max_conf)}
        self.model = self._load_model()
        self.tracker = IoUTracker(
            iou_threshold=cfg.tracking.iou_match_threshold,
            max_missed=cfg.tracking.max_missed_frames,
            min_hits=cfg.tracking.min_consecutive_hits,
            stable_grace_frames=getattr(
                cfg.tracking, "stable_grace_frames", 2),
        )
        self.classes_of_interest = set(
            (cfg.ai.classes_of_interest or [])
        ) if cfg.ai.get("classes_of_interest") else None

        # Opsiyonel: harici detector (sim ground-truth injector). Set edildiğinde
        # YOLO çağrısını atlar, doğrudan bu kaynağı tracker'a verir.
        self.external_detector = None

        # Multi-signal yangın doğrulayıcı (false positive eler: statik foto,
        # ten, kırmızı duvar vb). config.fire_validator yoksa enable=False.
        fv_cfg = (cfg.get("fire_validator")
                  if hasattr(cfg, "get") else None) or {}
        self.validator_enabled = bool(fv_cfg.get("enabled", False))
        if self.validator_enabled:
            self.validator = FireValidator(
                history_size=int(fv_cfg.get("history_size", 8)),
                min_score=float(fv_cfg.get("min_score", 0.45)),
            )
            self.logger.info("FireValidator aktif (min_score=%.2f)",
                             self.validator.min_score)
        else:
            self.validator = None

        # BrightFlameDetector — çakmak/mum gibi küçük alevler için klasik CV
        # YOLO + bu paralel çalışır, validator ikisini de filtreler.
        bfd_cfg = (cfg.get("bright_flame_detector")
                   if hasattr(cfg, "get") else None) or {}
        if bool(bfd_cfg.get("enabled", False)):
            self.bright_detector = BrightFlameDetector(
                min_area=int(bfd_cfg.get("min_area", 30)),
                max_area=int(bfd_cfg.get("max_area", 4000)),
                min_dark_ratio=float(bfd_cfg.get("min_dark_ratio", 0.30)),
                fake_conf=float(bfd_cfg.get("fake_conf", 0.50)),
            )
            self.logger.info("BrightFlameDetector aktif")
        else:
            self.bright_detector = None

    def set_external_detector(self, detector) -> None:
        """SimDetectionInjector veya benzer .detect(frame)→detections çağırı.

        Tracker'ı sıfırlar (kaynak değiştiği için id'ler karışmasın)."""
        self.external_detector = detector
        self.tracker.reset()

    def _pick_device(self) -> str:
        import torch
        d = self.cfg.ai.device
        if d != "auto":
            return d
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _load_model(self):
        model_path = Path(self.cfg.ai.model_path)
        if not model_path.is_absolute():
            model_path = THIS_DIR / model_path
        if not model_path.exists():
            msg = (f"Model yok: {model_path}. Önce `python ai/train.py` ile eğitin "
                   "veya geçici olarak hazır bir model dosyası koyun.")
            self.logger.error(msg)
            raise FileNotFoundError(msg)
        self.logger.info(f"YOLOv8 yükleniyor: {model_path}")
        model = YOLO(str(model_path))
        self.device = self._pick_device()
        self.logger.info(f"Device: {self.device}  |  Sınıflar: {model.names}")
        return model

    # Fuzzy
    @staticmethod
    def _trap(x: float, abcd: list) -> float:
        a, b, c, d = abcd
        if x <= a or x >= d:
            return 0.0
        if x <= b:
            return (x - a) / (b - a) if b != a else 1.0
        if x <= c:
            return 1.0
        return (d - x) / (d - c) if d != c else 1.0

    def get_memberships(self, area: float) -> dict:
        """Dashboard için her bulanık küme üyeliğini döner."""
        return {label: self._trap(area, abcd)
                for label, abcd in self._fuzzy_sets.items()}

    def fuzzy_priority(self, area: float) -> float:
        ws, vs = [], []
        for label, abcd in self._fuzzy_sets.items():
            mu = self._trap(area, abcd)
            if mu > 0:
                ws.append(mu)
                vs.append(self._fuzzy_out[label])
        if not ws:
            return 0.0 if area <= 0 else 1.0
        return sum(w * v for w, v in zip(ws, vs)) / sum(ws)

    # Simulated Annealing
    def sa_order(self, targets: List[Target],
                 robot_pos: Tuple[int, int]) -> List[int]:
        n = len(targets)
        if n <= 1:
            return list(range(n))

        def cost(order):
            rx, ry = robot_pos
            c = math.hypot(targets[order[0]].cx - rx, targets[order[0]].cy - ry)
            for i in range(1, len(order)):
                c += math.hypot(
                    targets[order[i]].cx - targets[order[i - 1]].cx,
                    targets[order[i]].cy - targets[order[i - 1]].cy,
                )
            return c

        current = sorted(range(n), key=lambda i: targets[i].priority, reverse=True)
        best = current[:]
        cur_c = best_c = cost(current)
        T = self.cfg.sa.t_start
        for _ in range(int(self.cfg.sa.max_iter)):
            if T < self.cfg.sa.t_end:
                break
            i, j = random.sample(range(n), 2)
            nb = current[:]
            nb[i], nb[j] = nb[j], nb[i]
            n_c = cost(nb)
            d = n_c - cur_c
            if d < 0 or random.random() < math.exp(-d / T):
                current, cur_c = nb, n_c
                if cur_c < best_c:
                    best, best_c = current[:], cur_c
            T *= self.cfg.sa.alpha
        return best

    # Frame işleme
    def process(self, frame) -> Tuple[List[Target], float]:
        fh, fw = frame.shape[:2]
        frame_area = fh * fw
        max_area_ratio = getattr(self.cfg.ai, "max_bbox_area_ratio", 0.5)
        use_hsv_refine = getattr(self.cfg.ai, "hsv_refine", True)
        hsv_required = getattr(self.cfg.ai, "hsv_required", False)

        # FireValidator: frame'i kaydet (her tespitte ROI üzerinde çalışacak)
        if self.validator is not None:
            self.validator.begin_frame(frame)

        detections: List[Tuple[Tuple[int, int, int, int], str, float]] = []

        # Harici detector (örn. sim ground-truth) varsa YOLO'yu atla
        if self.external_detector is not None:
            ext = self.external_detector.detect(frame) or []
            for (bbox, label, conf) in ext:
                x1, y1, x2, y2 = bbox
                x1 = max(0, int(x1)); y1 = max(0, int(y1))
                x2 = min(fw - 1, int(x2)); y2 = min(fh - 1, int(y2))
                if x2 <= x1 or y2 <= y1:
                    continue
                if self.classes_of_interest and not any(
                    k in label.lower() for k in self.classes_of_interest
                ):
                    continue
                detections.append(((x1, y1, x2, y2), label.lower(), float(conf)))
            return self._finalize(detections)

        results = self.model.predict(
            frame,
            conf=self.cfg.ai.conf_threshold,
            iou=self.cfg.ai.iou_threshold,
            imgsz=self.cfg.ai.imgsz,
            device=self.device,
            half=getattr(self.cfg.ai, "half_precision", True),
            verbose=False,
        )[0]

        for box in results.boxes:
            cls_id = int(box.cls[0])
            label = self.model.names[cls_id].lower()
            if self.classes_of_interest and not any(
                k in label for k in self.classes_of_interest
            ):
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
            x1 = max(0, x1); y1 = max(0, y1)
            x2 = min(fw - 1, x2); y2 = min(fh - 1, y2)
            if x2 <= x1 or y2 <= y1:
                continue

            # HSV refinement: model bbox'ı genellikle alevden çok daha büyük.
            # Bu ROI içinde parlak turuncu/sarı/kırmızı (alev rengi) bölgenin
            # gerçek bbox'ını bul ve onu kullan. Konum (angle_deg) ve overlay
            # için kritik. Bölge bulunamazsa orijinal bbox'ı koru.
            if use_hsv_refine:
                rx1, ry1, rx2, ry2 = _refine_flame_bbox(frame, x1, y1, x2, y2)
                if rx1 is not None:
                    x1, y1, x2, y2 = rx1, ry1, rx2, ry2
                elif hsv_required:
                    # HSV alev rengi bulamadı → model false positive → düşür
                    continue

            # Sahnenin tamamını kaplayan dev bbox'lar (duvar/oda yanıltıcıları)
            # gerçek yangın olamaz → ele. (HSV sonrası → eğer alev rengi
            # bulunamadıysa ve bbox hala devasaysa elenir.)
            bbox_area = max(0, (x2 - x1)) * max(0, (y2 - y1))
            if bbox_area > frame_area * max_area_ratio:
                continue
            conf = float(box.conf[0])

            # Validator bypass — model çok eminse (conf >= 0.65) doğrudan kabul
            # Bu çözüm: sabit duran gerçek alev validator'a takılmasın.
            confident = conf >= getattr(
                self.cfg.ai, "validator_bypass_conf", 0.65)

            # Multi-signal validator — statik foto/ten/kırmızı duvar elenir
            if self.validator is not None and not confident:
                ok, _scores = self.validator.validate(frame, (x1, y1, x2, y2))
                if not ok:
                    continue
            elif self.validator is not None:
                # bypass etsek bile history için frame'i besle
                self.validator.validate(frame, (x1, y1, x2, y2))

            detections.append(((x1, y1, x2, y2), label, conf))

        # BrightFlameDetector — küçük alev adayları ekle (validator yine eleyecek)
        if self.bright_detector is not None:
            for bb, lbl, c in self.bright_detector.detect(frame):
                bx1, by1, bx2, by2 = bb
                # Validator'dan geçir
                if self.validator is not None:
                    ok, _ = self.validator.validate(frame, (bx1, by1, bx2, by2))
                    if not ok:
                        continue
                # YOLO ile çakışan bbox varsa atla (NMS gibi)
                duplicate = False
                for (yb, _, _) in detections:
                    yx1, yy1, yx2, yy2 = yb
                    ix = max(0, min(bx2, yx2) - max(bx1, yx1))
                    iy = max(0, min(by2, yy2) - max(by1, yy1))
                    inter = ix * iy
                    a = (bx2 - bx1) * (by2 - by1)
                    if a > 0 and inter / a > 0.4:
                        duplicate = True
                        break
                if not duplicate:
                    detections.append((bb, lbl, c))

        # Frame sonu — validator history rotate
        if self.validator is not None:
            self.validator.end_frame()

        return self._finalize(detections)

    def _finalize(self, detections) -> Tuple[List[Target], float]:
        """Detections → tracker → Target listesi + smoothed area.
        process() ve harici detector path'i bu ortak yola düşer."""
        self.last_raw_count = len(detections)
        self.last_raw_max_conf = max((d[2] for d in detections), default=0.0)
        cb = {}
        for _, lbl, c in detections:
            n, mx = cb.get(lbl, (0, 0.0))
            cb[lbl] = (n + 1, max(mx, c))
        self.last_class_breakdown = cb
        stable: List[Track] = self.tracker.update(detections)

        targets: List[Target] = []
        smoke_factor = self.cfg.ai.smoke_priority_factor
        for trk in stable:
            base = self.fuzzy_priority(trk.area)
            pri = base * (smoke_factor if "smoke" in trk.label else 1.0)
            targets.append(Target(
                cx=trk.cx, cy=trk.cy, area=trk.area,
                priority=pri, label=trk.label,
                track_id=trk.track_id, conf=trk.conf,
                bbox=trk.bbox, hits=trk.hits, missed=trk.missed,
            ))

        if targets:
            max_a = max(t.area for t in targets)
            self._area_history.append(max_a)
            smoothed = sum(self._area_history) / len(self._area_history)
        else:
            self._area_history.clear()
            smoothed = 0.0

        return targets, smoothed


# 4. DONANIM HABERLEŞMESİ
class HardwareLink:
    def __init__(self, cfg: ConfigDict, logger: logging.Logger):
        self.cfg = cfg
        self.logger = logger
        self.ser: Optional[serial.Serial] = None
        self.heat_c = 25.0
        self.voltage = 0.0
        self.last_status: dict = {}        # Arduino STATUS heartbeat çıktısı
        self.arduino_ready: bool = False    # READY handshake alındı mı
        self._lock = threading.Lock()
        self._running = True
        # Fire-alert sinyal rate-limit state
        self._last_fire_signal = ""        # "F" | "N" | ""
        self._last_signal_ts   = 0.0
        self._signal_min_gap   = 0.7        # saniye
        self._fire_refresh_sec = 3.0        # 5sn auto-off'tan önce tazele

    def _find_port(self) -> Optional[str]:
        for p in serial.tools.list_ports.comports():
            tag = (p.description + " " + p.device).lower()
            if any(k in tag for k in
                   ["arduino", "ch340", "ttyusb", "usbserial", "wchusb", "com"]):
                return p.device
        return None

    def connect(self):
        if self.cfg.mode.simulation:
            return
        port = self.cfg.connection.serial_port or self._find_port()
        if not port:
            return
        try:
            self.ser = serial.Serial(port, self.cfg.connection.baud_rate, timeout=1)
            time.sleep(2)
            self.logger.info(f"Seri port: {port} açıldı")
        except Exception as e:
            self.logger.error(f"Seri port hatası: {e}")
            self.ser = None
            # Reset handshake/state so PC waits for READY again when port returns.
            self.arduino_ready = False
            self.last_status = {}
            self._last_fire_signal = ""

    def send(self, cmd_char: str, spd: int = 180, arm: str = ""):
        if self.cfg.mode.simulation or not self.ser or not self.ser.is_open:
            return
        try:
            if self.cfg.mode.use_structured_protocol:
                # Bilinmeyen kontrol karakteri → motor durdur (STOP fallback)
                name = {"W": "FORWARD", "S": "BACK",
                        "A": "LEFT", "D": "RIGHT", "X": "STOP"}.get(cmd_char, "STOP")
                msg = f"CMD:{name};SPD:{spd}"
                if arm:
                    msg += f";ARM:{arm}"
                msg += "\n"
            else:
                msg = cmd_char + "\n"
            self.ser.write(msg.encode("utf-8"))
        except Exception as e:
            self.logger.warning(f"Seri yazma hatası, port kapandı: {e}")
            try:
                self.ser.close()
            finally:
                self.ser = None
                self.arduino_ready = False
                self._last_fire_signal = ""

    def thread_reader(self):
        while self._running:
            if self.cfg.mode.simulation:
                time.sleep(1)
                continue
            if not self.ser or not self.ser.is_open:
                self.connect()
                time.sleep(self.cfg.connection.reconnect_delay)
                continue
            try:
                line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    pass
                elif line.startswith("VOLT:"):
                    try:
                        with self._lock:
                            self.voltage = float(line.split(":", 1)[1])
                    except ValueError:
                        pass
                elif line.startswith("WARN:"):
                    self.logger.warning(line)
                elif line.startswith("STATUS:"):
                    # STATUS:state=RUN,cmd=FORWARD,spd=180,arm=160,volt=11.7,alert=0
                    try:
                        payload = line.split(":", 1)[1]
                        kv = {}
                        for tok in payload.split(","):
                            if "=" in tok:
                                k, v = tok.split("=", 1)
                                kv[k.strip()] = v.strip()
                        with self._lock:
                            self.last_status = kv
                            if "volt" in kv:
                                try:
                                    self.voltage = float(kv["volt"])
                                except ValueError:
                                    pass
                    except Exception:
                        pass
                elif line == "READY":
                    self.arduino_ready = True
                    self.logger.info("Arduino READY (handshake)")
                elif line.startswith("ACK:"):
                    self.logger.debug(line)
            except Exception:
                try:
                    self.ser.close()
                finally:
                    self.ser = None
            time.sleep(0.02)

    def thread_telemetry(self):
        while self._running:
            if self.cfg.mode.simulation or not self.cfg.mode.use_telemetry_heat:
                time.sleep(1)
                continue
            try:
                r = requests.get(self.cfg.connection.telemetry_url, timeout=1.0)
                with self._lock:
                    self.heat_c = float(r.json().get("heat_c", 25.0))
            except Exception:
                pass
            time.sleep(self.cfg.connection.telemetry_interval)

    def sensors(self) -> Tuple[float, float]:
        with self._lock:
            return self.heat_c, self.voltage

    def get_status(self) -> dict:
        """Arduino heartbeat STATUS satırının son kopyası (kv map)."""
        with self._lock:
            return dict(self.last_status)

    def signal_fire(self, stable_fire: bool):
        """Stable-fire bilgisini Arduino'ya iletir (F/N), rate-limited.

        F → fire alert LED + buzzer pattern aç
        N → alarmı söndür
        Arduino tarafında 5sn auto-off var → fire devam ediyorsa
        ~3sn'de bir F tazelenir.
        """
        # config.yaml ile devre dışı bırakılabilir
        if not getattr(self.cfg.robot, "fire_alert_enable", True):
            return
        if self.cfg.mode.simulation and not self.ser:
            return
        now = time.time()
        signal = "F" if stable_fire else "N"
        if signal == self._last_fire_signal:
            if signal == "F" and (now - self._last_signal_ts) > self._fire_refresh_sec:
                self.send("F")
                self._last_signal_ts = now
            return
        if (now - self._last_signal_ts) < self._signal_min_gap:
            return
        self.send(signal)
        self._last_fire_signal = signal
        self._last_signal_ts   = now

    def stop(self):
        self._running = False
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass


# 5. HUD / KULLANICI ARAYÜZÜ
class HUD:
    """Frame üstüne yalın AR-style overlay; ayrıntılı analitik Dashboard'da."""

    STATE_COLOR = {
        State.SEARCHING:   (230, 190, 70),
        State.APPROACHING: (110, 220, 130),
        State.TOO_CLOSE:   (75, 75, 240),
        State.HEAT_ACTION: (40, 60, 240),
        State.MANUAL:      (220, 130, 240),
    }

    def __init__(self):
        self.angle = 0
        self.pulse = 0.0

    @staticmethod
    def _overlay_rect(img, p1, p2, color, alpha=0.55):
        ov = img.copy()
        cv2.rectangle(ov, p1, p2, color, -1)
        cv2.addWeighted(ov, alpha, img, 1 - alpha, 0, img)

    @staticmethod
    def _corner_box(img, x1, y1, x2, y2, color, thick=2, L=14):
        # Modern AR-style köşeli bracket
        for (cx, cy, dx, dy) in (
            (x1, y1, +1, +1), (x2, y1, -1, +1),
            (x1, y2, +1, -1), (x2, y2, -1, -1),
        ):
            cv2.line(img, (cx, cy), (cx + dx * L, cy), color, thick, cv2.LINE_AA)
            cv2.line(img, (cx, cy), (cx, cy + dy * L), color, thick, cv2.LINE_AA)

    def draw(self, frame, state, targets, fps, area_stop,
             heat, heat_thresh, recording, sim_mode=False):
        self.pulse = (self.pulse + 0.12) % (2 * math.pi)
        fh, fw = frame.shape[:2]
        base = self.STATE_COLOR.get(state, (200, 200, 200))

        # Sol üst kompakt rozet
        self._overlay_rect(frame, (10, 10), (220, 46), (12, 12, 14), 0.72)
        cv2.rectangle(frame, (10, 10), (12, 46), base, -1)
        cv2.putText(frame, state.name, (22, 27),
                    cv2.FONT_HERSHEY_DUPLEX, 0.55, base, 1, cv2.LINE_AA)
        cv2.putText(frame, f"YOLOv8  •  {fps:5.1f} fps", (22, 42),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 185), 1, cv2.LINE_AA)

        # Sağ üst SIM / LIVE etiketi
        mode_txt = "SIMULATION" if sim_mode else "LIVE"
        mode_col = (110, 220, 130) if sim_mode else (75, 75, 240)
        (tw, _), _ = cv2.getTextSize(mode_txt, cv2.FONT_HERSHEY_DUPLEX, 0.5, 1)
        self._overlay_rect(frame, (fw - tw - 26, 10),
                           (fw - 10, 36), (12, 12, 14), 0.72)
        cv2.putText(frame, mode_txt, (fw - tw - 18, 28),
                    cv2.FONT_HERSHEY_DUPLEX, 0.5, mode_col, 1, cv2.LINE_AA)

        # REC göstergesi
        if recording:
            alpha = 0.5 + 0.5 * math.sin(self.pulse * 4)
            col = (int(40 * alpha) + 40, int(40 * alpha) + 40,
                   int(255 * alpha))
            cv2.circle(frame, (fw - 22, 58), 7, col, -1)
            cv2.putText(frame, "REC", (fw - 60, 62),
                        cv2.FONT_HERSHEY_DUPLEX, 0.45,
                        (75, 75, 240), 1, cv2.LINE_AA)

        # Hedefler — gerçek bbox tracker'dan geliyorsa kullan, yoksa
        # sqrt(area) tabanlı kare fallback (sentetik etiket vb. için).
        for i, t in enumerate(targets):
            primary = (i == 0)
            color = (75, 75, 240) if primary else (90, 180, 255)
            if t.bbox is not None:
                bx1, by1, bx2, by2 = t.bbox
                x1 = max(0, min(fw - 1, int(bx1)))
                y1 = max(0, min(fh - 1, int(by1)))
                x2 = max(0, min(fw - 1, int(bx2)))
                y2 = max(0, min(fh - 1, int(by2)))
            else:
                fallback = max(40, int(math.sqrt(max(1, t.area))))
                x1 = max(0, t.cx - fallback // 2)
                y1 = max(0, t.cy - fallback // 2)
                x2 = min(fw - 1, t.cx + fallback // 2)
                y2 = min(fh - 1, t.cy + fallback // 2)
            # Reticle/label boyutlandırma için bbox kenar uzunluğu
            side = max(x2 - x1, y2 - y1)

            if primary:
                # Animasyonlu reticle
                self.angle = (self.angle + 4) % 360
                rr = side // 2 + 10
                for a in range(0, 360, 90):
                    rad = math.radians(self.angle + a)
                    px = int(t.cx + rr * math.cos(rad))
                    py = int(t.cy + rr * math.sin(rad))
                    cv2.line(frame, (t.cx, t.cy), (px, py), color, 1, cv2.LINE_AA)
                # Köşeli bracket
                self._corner_box(frame, x1, y1, x2, y2, color, 2, 16)
                # Etiket
                lbl = f"★ {t.label.upper()}  P {t.priority:.2f}  C {t.conf:.2f}"
                (lw, lh), _ = cv2.getTextSize(
                    lbl, cv2.FONT_HERSHEY_DUPLEX, 0.45, 1)
                lp1 = (x1, max(0, y1 - lh - 8))
                lp2 = (x1 + lw + 14, y1)
                self._overlay_rect(frame, lp1, lp2, (15, 15, 18), 0.75)
                cv2.rectangle(frame, lp1, lp2, color, 1, cv2.LINE_AA)
                cv2.putText(frame, lbl, (x1 + 7, y1 - 6),
                            cv2.FONT_HERSHEY_DUPLEX, 0.45,
                            color, 1, cv2.LINE_AA)
            else:
                self._corner_box(frame, x1, y1, x2, y2, color, 1, 8)
                lbl = f"#{i+1} {t.label[:1].upper()}  {t.conf:.2f}"
                cv2.putText(frame, lbl, (x1, max(12, y1 - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                            color, 1, cv2.LINE_AA)

        # Merkez uyarılar
        cx, cy = fw // 2, fh - 60
        if targets and targets[0].area >= area_stop * 0.7:
            txt = "TOO CLOSE"
            (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_DUPLEX, 0.7, 2)
            p1 = (cx - tw // 2 - 14, cy - th - 8)
            p2 = (cx + tw // 2 + 14, cy + 8)
            self._overlay_rect(frame, p1, p2, (15, 15, 18), 0.78)
            cv2.rectangle(frame, p1, p2, (75, 75, 240), 2, cv2.LINE_AA)
            cv2.putText(frame, txt, (cx - tw // 2, cy),
                        cv2.FONT_HERSHEY_DUPLEX, 0.7,
                        (75, 75, 240), 2, cv2.LINE_AA)
        if heat > heat_thresh:
            txt = f"CRITICAL HEAT  {heat:.1f}°C"
            (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_DUPLEX, 0.6, 2)
            p1 = (cx - tw // 2 - 14, cy - th - 36)
            p2 = (cx + tw // 2 + 14, cy - 28)
            self._overlay_rect(frame, p1, p2, (15, 15, 18), 0.78)
            cv2.rectangle(frame, p1, p2, (40, 60, 240), 2, cv2.LINE_AA)
            cv2.putText(frame, txt, (cx - tw // 2, cy - 36),
                        cv2.FONT_HERSHEY_DUPLEX, 0.6,
                        (40, 60, 240), 2, cv2.LINE_AA)


# 6. ANA ORKESTRATÖR
class RobotController:
    def __init__(self, cfg: ConfigDict, logger: logging.Logger,
                 max_frames: Optional[int] = None,
                 headless: bool = False):
        self.cfg = cfg
        self.logger = logger
        self.max_frames = max_frames        # None = sınırsız
        self.headless = headless            # True = cv2.imshow yok (test)
        self.vision = VisionProcessor(cfg, logger)
        self.hw = HardwareLink(cfg, logger)
        self.hud = HUD()
        self.dashboard = Dashboard(width=340)
        self.area_history = deque(maxlen=120)

        self.state = State.SEARCHING
        self.last_cmd = "X"
        self.cmd_history = deque(maxlen=max(1, cfg.robot.command_smoothing))
        self.recording = False
        self.video_writer = None
        self.scan_dir = 1
        self.scan_timer = time.time()
        self.frame_idx = 0
        # Stable-fire için temporal smoothing — web_app ile aynı mantık
        self._fire_history: deque = deque(maxlen=5)
        self._last_fire_seen_ts = 0.0
        self._fire_hold_sec = 1.0

        self.out_dir = Path(cfg.output.dir)
        if not self.out_dir.is_absolute():
            self.out_dir = THIS_DIR / self.out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)

        self.csv: Optional[CSVLogger] = None
        if cfg.output.csv_log:
            self.csv = CSVLogger(self.out_dir)
            logger.info(f"CSV log: {self.csv.path}")

        threading.Thread(target=self.hw.thread_reader, daemon=True).start()
        threading.Thread(target=self.hw.thread_telemetry, daemon=True).start()

        self._sim_gen: Optional[FireSceneGenerator] = None

        # Yeni AI bileşenleri
        # Mesafe tahmini (kalibrasyon konfigden)
        self.distance_est = DistanceEstimator.from_config(cfg)
        # Webhook bildirimi (config.notify yoksa no-op)
        notify_cfg = cfg.get("notify") if hasattr(cfg, "get") else None
        self.webhook = WebhookNotifier(notify_cfg, logger=logger)
        # Yangın yoğunluk haritası — sahne boyutu ilk frame'de ayarlanır
        self._heatmap: Optional[FireHeatmap] = None
        hm_cfg = cfg.get("heatmap") if hasattr(cfg, "get") else None
        self.heatmap_enabled = bool(
            hm_cfg.get("enabled", True)) if hm_cfg else True
        self.heatmap_decay = float(
            hm_cfg.get("decay", 0.88)) if hm_cfg else 0.88

    # Kamera açma
    def open_source(self):
        sim_src = self.cfg.mode.sim_source
        if self.cfg.mode.simulation and sim_src == "synthetic":
            scene_cfg = SceneConfig(width=960, height=540, n_targets=2,
                                    moving=True, smoke=True,
                                    emit_labels=True)
            self._sim_gen = FireSceneGenerator(scene_cfg)
            # Sentetik sahnenin GT etiketlerini "tespit" olarak besle
            # → YOLO modelinin sentetik dağılımı tanımama sorunu çözülür,
            # sistem alt katmanları (tracker→fuzzy→SA→FSM) test edilebilir.
            sim_cfg = self.cfg.get("sim") if hasattr(self.cfg, "get") else None
            use_sim_passthrough = bool(
                sim_cfg.get("passthrough_detections", True)) if sim_cfg else True
            if use_sim_passthrough:
                self.vision.set_external_detector(
                    SimDetectionInjector(self._sim_gen, fake_conf=0.85))
                self.logger.info("Kaynak: sentetik sahne + GT passthrough")
            else:
                self.vision.set_external_detector(None)
                self.logger.info("Kaynak: sentetik sahne (YOLO modeli üzerinden)")
            return self._sim_gen
        # Sentetik dışı kaynaklarda harici detector'ı kapat
        self.vision.set_external_detector(None)
        if self.cfg.mode.simulation and sim_src == "video":
            path = self.cfg.mode.sim_video_path
            cap = cv2.VideoCapture(path)
            if not cap.isOpened():
                self.logger.error("Video açılamadı: %s", path)
                return None
            self.logger.info(f"Kaynak: video {path}")
            return cap
        if self.cfg.mode.simulation:
            return _open_webcam_with_fallback(
                int(self.cfg.mode.webcam_index), self.logger)
        # ESP32-CAM (gerçek robot) — timeout'lu helper
        url = self.cfg.connection.stream_url
        return _open_esp32_stream(url, self.logger, timeout_sec=8.0)

    # Karar mantığı
    def decide(self, targets: List[Target], heat: float, fw: int):
        if heat > self.cfg.robot.heat_threshold_c:
            self.state = State.HEAT_ACTION
            return "X", 0, "DOWN"
        if not targets:
            if self.state != State.MANUAL:
                self.state = State.SEARCHING
            return None, self.cfg.robot.scan_speed, ""

        primary = targets[0]
        if primary.area >= self.cfg.robot.area_stop:
            self.state = State.TOO_CLOSE
            return "X", 0, ""

        if primary.area >= self.cfg.robot.area_close:
            spd = self.cfg.robot.speed_close
        elif primary.area >= self.cfg.robot.area_medium:
            spd = self.cfg.robot.speed_medium
        else:
            spd = self.cfg.robot.speed_far

        third = fw // 3
        if primary.cx < third:
            cmd = "A"
        elif primary.cx > 2 * third:
            cmd = "D"
        else:
            cmd = "W"
        self.state = State.APPROACHING
        return cmd, spd, ""

    def _smoothed_cmd(self, cmd: str) -> str:
        self.cmd_history.append(cmd)
        # En sık tekrar eden
        return Counter(self.cmd_history).most_common(1)[0][0]

    def execute(self, cmd: Optional[str], spd: int, arm: str):
        if self.state == State.SEARCHING:
            now = time.time()
            if now - self.scan_timer > 2.0:
                self.scan_dir *= -1
                self.scan_timer = now
            c = "A" if self.scan_dir == 1 else "D"
            self.hw.send(c, self.cfg.robot.scan_speed)
            self.last_cmd = c
            return
        if self.state in (State.HEAT_ACTION, State.TOO_CLOSE):
            self.hw.send("X", 0, arm)
            self.last_cmd = "X"
            return
        if self.state == State.APPROACHING and cmd:
            smoothed = self._smoothed_cmd(cmd)
            self.hw.send(smoothed, spd, arm)
            self.last_cmd = smoothed

    # Kayıt
    def toggle_recording(self, fw: int, fh: int):
        if not self.recording:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            vp = self.out_dir / f"video_{ts}.avi"
            fourcc = cv2.VideoWriter_fourcc(*self.cfg.output.video_codec)
            self.video_writer = cv2.VideoWriter(
                str(vp), fourcc, self.cfg.output.video_fps, (fw, fh)
            )
            self.recording = True
            self.logger.info(f"REC başladı: {vp}")
        else:
            self.recording = False
            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None
            self.logger.info("REC durdu")

    # Klavye
    def handle_key(self, key: int, fw: int, fh: int) -> bool:
        if key == ord("q"):
            return True  # exit
        if key == ord("m"):
            self.state = (State.MANUAL if self.state != State.MANUAL
                          else State.SEARCHING)
            self.logger.info(f"Mod: {self.state.name}")
            return False
        if key == ord("r"):
            self.toggle_recording(fw, fh)
            return False
        if self.state == State.MANUAL:
            mapping = {
                ord("w"): ("W", self.cfg.robot.speed_medium, ""),
                ord("s"): ("S", self.cfg.robot.speed_medium, ""),
                ord("a"): ("A", self.cfg.robot.speed_medium, ""),
                ord("d"): ("D", self.cfg.robot.speed_medium, ""),
                ord("x"): ("X", 0, ""),
                ord("k"): ("X", 0, "DOWN"),
                ord("l"): ("X", 0, "UP"),
            }
            if key in mapping:
                c, s, a = mapping[key]
                self.hw.send(c, s, a)
                self.last_cmd = c
                return False
        # Sentetik sahne tuşları
        if self._sim_gen is not None:
            self._sim_gen.handle_key(key)
        return False

    # Ana döngü
    def run(self):
        self.logger.info("=" * 50)
        self.logger.info(" Robot Controller v5.0 (YOLOv8 + SIM)")
        self.logger.info("=" * 50)
        cap = None
        fps_t = time.time()
        fps_n = 0
        fps_disp = 0.0
        # Reconnect kontrolü: sonsuz fail'i engelle, kullanıcıya açık hata ver
        open_attempts = 0
        max_open_attempts = 5
        try:
            while True:
                if cap is None or not cap.isOpened():
                    cap = self.open_source()
                    if cap is None or not cap.isOpened():
                        open_attempts += 1
                        if open_attempts > max_open_attempts:
                            self.logger.error(
                                "Kaynak %d denemede açılamadı — kapanıyor.",
                                max_open_attempts)
                            break
                        self.logger.warning(
                            "Açma denemesi %d/%d başarısız, 1.5s sonra tekrar...",
                            open_attempts, max_open_attempts)
                        time.sleep(1.5)
                        continue
                    open_attempts = 0

                ok, frame = cap.read()
                if not ok or frame is None:
                    self.logger.warning("Kare alınamadı, yeniden bağlanılıyor...")
                    try:
                        cap.release()
                    except Exception:
                        pass
                    cap = None
                    self._sim_gen = None
                    continue

                self.frame_idx += 1
                fh, fw = frame.shape[:2]
                fps_n += 1
                now = time.time()
                if now - fps_t >= 1.0:
                    fps_disp = fps_n / (now - fps_t)
                    fps_n, fps_t = 0, now

                targets, smoothed_area = self.vision.process(frame)
                heat_c, voltage = self.hw.sensors()

                # Sim modunda telemetri yok → alan üzerinden sahte ısı
                if not self.cfg.mode.use_telemetry_heat:
                    score = min(smoothed_area / max(fw * fh, 1), 1.0) * 100.0
                    heat_c = 25.0 + score * 0.6

                # SA sıralaması
                if targets:
                    robot_px = (fw // 2, fh)
                    order = self.vision.sa_order(targets, robot_px)
                    targets = [targets[i] for i in order]

                # Klavye
                key = cv2.waitKey(1) & 0xFF
                if self.handle_key(key, fw, fh):
                    self.logger.info("Çıkış komutu alındı")
                    self.hw.send("X", 0)
                    break

                # Karar & yürüt
                cmd_decided, spd_decided, arm = (None, 0, "")
                if self.state != State.MANUAL:
                    cmd_decided, spd_decided, arm = self.decide(targets, heat_c, fw)
                    self.execute(cmd_decided, spd_decided, arm)

                # Stable-fire sinyalini Arduino'ya ilet (LED/buzzer alarmı)
                fire_now = bool(targets)
                self._fire_history.append(fire_now)
                if fire_now:
                    self._last_fire_seen_ts = time.time()
                window_stable = (sum(self._fire_history) >= 3
                                 and len(self._fire_history) >= 3)
                recent_hold = (time.time() - self._last_fire_seen_ts) <= self._fire_hold_sec
                stable_fire = bool(window_stable or recent_hold)
                self.hw.signal_fire(stable_fire)

                # Webhook: stable-fire kenarı (False→True) → dış dünyaya POST
                primary_for_hook = targets[0] if targets else None
                hook_payload = {
                    "fps": round(fps_disp, 1),
                    "n_targets": len(targets),
                    "heat_c": round(heat_c, 1),
                    "voltage": round(voltage, 2),
                    "primary_priority": (
                        round(primary_for_hook.priority, 3)
                        if primary_for_hook else 0.0),
                    "primary_label": (
                        primary_for_hook.label if primary_for_hook else ""),
                    "state": self.state.name,
                }
                self.webhook.on_state_change(stable_fire, hook_payload)

                # Heatmap güncelle (lazy initialize: ilk frame'de boyut bilinince)
                if self.heatmap_enabled:
                    if self._heatmap is None:
                        self._heatmap = FireHeatmap(
                            width=fw, height=fh, decay=self.heatmap_decay)
                    self._heatmap.update(targets)

                # Kayıt
                if self.recording and self.video_writer:
                    self.video_writer.write(frame)

                # CSV
                if self.csv:
                    p = targets[0] if targets else None
                    dist_m = (
                        f"{self.distance_est.estimate(p, fh):.2f}"
                        if p else "")
                    self.csv.write({
                        "frame": self.frame_idx,
                        "state": self.state.name,
                        "cmd": self.last_cmd,
                        "spd": spd_decided,
                        "n_targets": len(targets),
                        "primary_cx": p.cx if p else "",
                        "primary_cy": p.cy if p else "",
                        "primary_area": p.area if p else "",
                        "primary_priority": f"{p.priority:.3f}" if p else "",
                        "primary_label": p.label if p else "",
                        "primary_distance_m": dist_m,
                        "heat_c": f"{heat_c:.2f}",
                        "voltage": f"{voltage:.2f}",
                        "fps": f"{fps_disp:.1f}",
                        "stable_fire": int(stable_fire),
                        "heatmap_max": (
                            f"{self._heatmap.max_intensity():.3f}"
                            if self._heatmap else ""),
                    })

                # Heatmap overlay (HUD'dan önce — overlay olarak alttan görünmeli)
                if self._heatmap is not None:
                    frame = self._heatmap.render(frame)

                # HUD (frame overlay)
                self.hud.draw(
                    frame, self.state, targets, fps_disp,
                    self.cfg.robot.area_stop, heat_c,
                    self.cfg.robot.heat_threshold_c, self.recording,
                    sim_mode=self.cfg.mode.simulation,
                )

                # Dashboard (side panel)
                self.area_history.append(smoothed_area)
                primary = targets[0] if targets else None
                memberships = self.vision.get_memberships(
                    primary.area if primary else 0.0
                )
                ctx = DashboardContext(
                    state=self.state.name,
                    fps=fps_disp,
                    cmd=self.last_cmd,
                    spd=spd_decided if cmd_decided is not None else 0,
                    heat_c=heat_c,
                    voltage=voltage,
                    heat_threshold=self.cfg.robot.heat_threshold_c,
                    targets=targets,
                    raw_count=self.vision.last_raw_count,
                    raw_max_conf=self.vision.last_raw_max_conf,
                    conf_threshold=self.cfg.ai.conf_threshold,
                    memberships=memberships,
                    primary_priority=primary.priority if primary else 0.0,
                    primary_area=primary.area if primary else 0.0,
                    area_stop=self.cfg.robot.area_stop,
                    area_history=self.area_history,
                    sim_mode=self.cfg.mode.simulation,
                    recording=self.recording,
                    mode_label=(self.cfg.mode.sim_source.upper()
                                if self.cfg.mode.simulation else "LIVE"),
                )
                panel = self.dashboard.render(frame.shape[0], ctx)
                canvas = np.hstack([frame, panel])

                if not self.headless:
                    title = "FIRE-SENTINEL v3.0 — " + (
                        "SIMULATION" if self.cfg.mode.simulation else "LIVE"
                    )
                    cv2.imshow(title, canvas)

                if self.max_frames is not None and self.frame_idx >= self.max_frames:
                    self.logger.info(
                        f"max_frames={self.max_frames} ulaşıldı, kapanıyor"
                    )
                    break

        except KeyboardInterrupt:
            self.logger.info("Ctrl+C ile durduruldu")
        except Exception as e:
            self.logger.exception(f"Beklenmeyen hata: {e}")
        finally:
            self.logger.info("Kapanış...")
            # Yumuşak kapanış: fire alarmı söndür + motor durdur
            try:
                self.hw.signal_fire(False)
                self.hw.send("X", 0)
            except Exception:
                pass
            self.hw.stop()
            if cap is not None and hasattr(cap, "release"):
                cap.release()
            if self.video_writer:
                self.video_writer.release()
            if self.csv:
                self.csv.close()
            cv2.destroyAllWindows()
            self.logger.info("Bitti.")


# 7. ENTRY POINT
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(THIS_DIR / "configs" / "config.yaml"))
    ap.add_argument("--sim", default=None,
                    choices=["webcam", "synthetic", "video"],
                    help="Konfigteki sim_source'u override eder")
    ap.add_argument("--no-sim", action="store_true",
                    help="simulation=false yapar (gerçek robot)")
    ap.add_argument("--max-frames", type=int, default=None,
                    help="Bu kadar frame işle ve çık (CI/smoke test)")
    ap.add_argument("--headless", action="store_true",
                    help="OpenCV penceresi açma (CI/sunucu)")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.sim:
        cfg["mode"]["sim_source"] = args.sim
        cfg["mode"]["simulation"] = True
    if args.no_sim:
        cfg["mode"]["simulation"] = False

    out_dir = Path(cfg.output.dir)
    if not out_dir.is_absolute():
        out_dir = THIS_DIR / out_dir
    logger = setup_logger(out_dir)

    app = RobotController(cfg, logger,
                          max_frames=args.max_frames,
                          headless=args.headless)
    app.run()


if __name__ == "__main__":
    main()
