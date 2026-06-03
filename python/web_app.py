#!/usr/bin/env python3
"""
web_app.py — Yangın Tespit Robotu / Web UI Backend (v3)
========================================================
GitHub Pages'teki statik live.html sayfasına canlı veri besler.

Endpoint'ler:
  GET  /state          → JSON: durum, kamera açısı, yangın, fps, conf, heat
  GET  /video_feed     → MJPEG canlı kamera (üzerinde FIRE bbox)
  GET  /snapshot       → Tek-kare JPEG (anlık görüntü indirme)
  GET  /plot.png       → RANSAC tipi kesişim çizimi
  POST /start          → vision döngüsünü başlat
  POST /stop           → vision döngüsünü durdur
  POST /command        → manuel sürüş komutu (W/A/S/D/X + arm K/L)
  POST /source         → kaynak değiştir (webcam | esp32 | synthetic)
  GET  /config         → frontend için ayarlar (conf threshold vs.)
  GET  /healthz        → ping

v3 yenilikleri:
  • Kaynak seçimi: webcam | esp32 (MJPEG URL) | synthetic
  • Manuel kontrol: /command — gerçek Arduino bağlıysa seriden gönderir
  • Stable-fire imzası Arduino'ya FIRE:ON komutu olarak iletilir
  • Heat/voltage telemetrisi (HardwareLink threadleri canlı)
  • /snapshot — gerçek tek-kare JPEG

CORS açıktır — `*` (sadece lokal/demo amaçlı).

Kullanım:
    python web_app.py                       # 0.0.0.0:5000 webcam
    python web_app.py --port 5050 --autostart
    python web_app.py --source esp32        # ESP32-CAM kaynağı
"""
from __future__ import annotations

import argparse
import io
import logging
import math
import os
import platform
import sys
import threading
import time
from collections import deque
from pathlib import Path

# macOS AVFoundation: cv2.VideoCapture'ı background thread'de açtığımız için
# izin sorgusu main run loop hatası verir. İzin zaten verildiyse skip et.
os.environ.setdefault("OPENCV_AVFOUNDATION_SKIP_AUTH", "1")
# Windows MSMF backend bazı USB webcam'lerde 30+ sn donuyor → DSHOW tercih edilir.
# OpenCV bu env var ile MSMF transformations'ı atlar (yan etkisi yok, sadece daha hızlı).
os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

import cv2

# Platform tespit: webcam backend seçimi için kullanıyoruz.
_IS_WINDOWS = platform.system() == "Windows"
_IS_MACOS   = platform.system() == "Darwin"


def _webcam_backend() -> int:
    """Platforma göre en sağlam VideoCapture backend'ini döner.
    Windows: DSHOW (MSMF yavaş açılıyor + bazı kameralarda kilitleniyor).
    macOS:   AVFoundation (default).
    Linux:   V4L2.
    """
    if _IS_WINDOWS:
        return cv2.CAP_DSHOW
    if _IS_MACOS:
        return cv2.CAP_AVFOUNDATION
    return cv2.CAP_V4L2
import numpy as np
from flask import Flask, Response, jsonify, request

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

from pc_vision_controller import (                                # noqa: E402
    VisionProcessor, HardwareLink, list_webcams,
    _probe_webcam, _open_esp32_stream, webcam_failure_hint,
)
from utils.config_loader import load_config                       # noqa: E402
from ai.sim_detector import SimDetectionInjector                  # noqa: E402
from ai.heatmap import FireHeatmap                                # noqa: E402
from ai.distance import DistanceEstimator                         # noqa: E402
from ai.webhook import WebhookNotifier                            # noqa: E402


# 1. VisionService — kamera + AI + (opsiyonel) donanım threadi
class VisionService:
    """Webcam / ESP32-CAM / synthetic kaynaklarından okur, YOLOv8 ile işler,
    paylaşımlı state'i (latest_jpeg + state_snapshot) günceller.

    Arduino bağlıysa stable-fire görüldüğünde FIRE:ON komutu, kesilince
    FIRE:OFF gider; ayrıca /command endpoint'i manuel sürüşü destekler.
    """

    VALID_SOURCES = ("webcam", "esp32", "synthetic")

    def __init__(self, cfg, logger):
        self.cfg = cfg
        self.logger = logger
        self.vision = VisionProcessor(cfg, logger)

        # Donanım bağlantısı (config.simulation=false ise Arduino açar)
        # Burada UI üzerinden control etmek için HER ZAMAN canlı tutuyoruz;
        # simülasyon modunda send/connect no-op döner.
        self.hw = HardwareLink(cfg, logger)
        threading.Thread(target=self.hw.thread_reader, daemon=True).start()
        threading.Thread(target=self.hw.thread_telemetry, daemon=True).start()

        # Yeni AI bileşenleri
        self.distance_est = DistanceEstimator.from_config(cfg)
        notify_cfg = cfg.get("notify") if hasattr(cfg, "get") else None
        self.webhook = WebhookNotifier(notify_cfg, logger=logger)
        hm_cfg = cfg.get("heatmap") if hasattr(cfg, "get") else None
        self.heatmap_enabled = bool(
            hm_cfg.get("enabled", True)) if hm_cfg else True
        self.heatmap_decay = float(
            hm_cfg.get("decay", 0.88)) if hm_cfg else 0.88
        self._heatmap: FireHeatmap | None = None

        self.cap = None
        self.running = False
        self.lock = threading.Lock()
        self.latest_jpeg: bytes | None = None
        self.latest_raw_jpeg: bytes | None = None  # bbox'sız snapshot için
        self.t0 = time.time()
        self.fps = 0.0
        self.positions: deque = deque(maxlen=80)
        self.frame_size = (640, 480)

        # Temporal smoothing
        self.fire_history: deque = deque(maxlen=5)
        self.last_fire_ts = 0.0
        self.fire_hold_sec = 1.0
        # Arduino'ya fire alert sinyali yumuşatma
        self._last_fire_signal = ""
        self._last_signal_ts   = 0.0
        self._signal_min_gap   = 0.7   # saniye

        # Kaynak / mod
        self.source = "webcam"        # default; set_source() ile değişir

        # Kaynak açılış hatası: kullanıcı UI'da sebebini görsün (boş = sorun yok)
        self.source_error: str = ""

        self.state_snapshot = self._empty_state()
        self._thread: threading.Thread | None = None
        # stop() çift-çağrı yarışını engeller (sticky lock değil, sadece guard)
        self._stop_lock = threading.Lock()

    # start/stop
    def _empty_state(self) -> dict:
        return {
            "running": False,
            "fire_detected": False,
            "stable_fire": False,
            "fire_history": [],
            "angle_deg": 0.0,
            "system_time_ms": 0,
            "n_targets": 0,
            "raw_count": 0,
            "raw_max_conf": 0.0,
            "classes": {},
            "primary_priority": 0.0,
            "primary_area": 0,
            "primary_distance_m": 0.0,
            "heatmap_max": 0.0,
            "fps": 0.0,
            "heat_c": 25.0,
            "voltage": 0.0,
            "source": self.source if hasattr(self, "source") else "webcam",
            "source_error": getattr(self, "source_error", ""),
            "conf_threshold": float(self.cfg.ai.conf_threshold),
            "imgsz": int(self.cfg.ai.imgsz),
        }

    def start(self):
        if self.running:
            return
        # Yeni döngü → eski hata mesajını temizle
        self.source_error = ""
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self.logger.info("vision döngüsü başlatıldı (source=%s)", self.source)

    def stop(self):
        # Idempotency: aynı anda iki stop() çağrısı race etmesin.
        # _stop_lock acquire edilemezse zaten başka bir stop sürüyor → bekle, sonra geç.
        with self._stop_lock:
            was_running = self.running
            self.running = False
            # Thread'in döngüden çıkmasını bekle ki cap.release() race etmesin.
            t = self._thread
            if (t is not None and t.is_alive()
                    and threading.current_thread() is not t):
                t.join(timeout=3.0)
                if t.is_alive():
                    self.logger.warning(
                        "vision thread 3s içinde kapanmadı — cap zorla release ediliyor")
            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None
            # Robot bağlıysa fire-alert söndür ve durdur
            self.hw.send("X", 0)
            self.hw.send("N")   # FIRE:OFF — alarm söner
            with self.lock:
                self.state_snapshot["running"] = False
            if was_running:
                self.logger.info("✓ vision döngüsü durduruldu, kamera serbest")

    def set_source(self, source: str) -> bool:
        if source not in self.VALID_SOURCES:
            return False
        if source == self.source:
            return True
        # Aktif döngüyü durdur, kaynağı değiştir.
        # stop() artık thread'i kendi join ediyor → ek bekleme gerekmez.
        was_running = self.running
        # Önceki kaynak fail etmiş ve durmuşsa (running=False, source_error dolu),
        # kullanıcı yeni bir kaynak deniyor demek → otomatik start uygundur.
        had_error = bool(self.source_error)
        if was_running:
            self.stop()
        self.source = source
        # State snapshot'ı hemen güncelle ki /source çağrısı sonrası /state
        # cevap vermeden önce _loop'un set etmesini beklemeyelim.
        with self.lock:
            self.state_snapshot["source"] = source
        # config bayraklarını ayarla — kaynağa göre
        if source == "synthetic":
            self.cfg["mode"]["sim_source"] = "synthetic"
            self.cfg["mode"]["simulation"] = True
            # Sentetik moda geçişte: passthrough'u açık ve heatmap'i taze tut
            # (yeni Roboflow modeli sentetik dağılımı tanımaz; GT etiketleri ver)
            if "sim" not in self.cfg:
                self.cfg["sim"] = {}
            self.cfg["sim"]["passthrough_detections"] = True
        elif source == "esp32":
            self.cfg["mode"]["simulation"] = False  # gerçek stream
            if "sim" in self.cfg:
                self.cfg["sim"]["passthrough_detections"] = False
        else:
            self.cfg["mode"]["sim_source"] = "webcam"
            self.cfg["mode"]["simulation"] = True
            if "sim" in self.cfg:
                self.cfg["sim"]["passthrough_detections"] = False
        # Heatmap'i sıfırla (önceki sahnenin kalıntısı kalmasın)
        if self._heatmap is not None:
            self._heatmap.reset()
        # Tracker history'sini de sıfırla (farklı kaynaktan track id taşıma)
        try:
            self.vision.tracker.reset()
        except Exception:
            pass
        if was_running or had_error:
            # had_error path: önceki kaynak fail edip durmuştu, kullanıcı yeni
            # kaynak denerken implicit start bekler (UX kalitesi)
            self.start()
        self.logger.info("kaynak değişti → %s", source)
        return True

    # kaynak hatası Türkçe açıklama
    @staticmethod
    def _explain_open_failure(source: str) -> str:
        if source == "webcam":
            return webcam_failure_hint()
        if source == "esp32":
            return ("ESP32-CAM stream'ine erişilemedi. WiFi/IP doğru mu? "
                    "Tarayıcıdan stream URL'yi açıp kontrol edin.")
        if source == "synthetic":
            return ("Sentetik sahne başlatılamadı (sim modülü import edilemedi). "
                    "python/sim/ dizinini kontrol edin.")
        return f"Kaynak '{source}' açılamadı."

    # kaynak açma
    def _open_source(self):
        if self.source == "synthetic":
            try:
                from sim.fire_scene_generator import (
                    FireSceneGenerator, SceneConfig,
                )
            except Exception as e:
                self.logger.error("synthetic kaynak yüklenemedi: %s", e)
                return None
            sc = SceneConfig(width=960, height=540, n_targets=2,
                             moving=True, smoke=True, emit_labels=True)
            scene = FireSceneGenerator(sc)
            # Sim passthrough — YOLO modeli sentetik dağılımı tanımıyor,
            # GT etiketlerini "tespit" olarak besle ki demo gerçekten gözüksün.
            sim_cfg = self.cfg.get("sim") if hasattr(self.cfg, "get") else None
            use_pt = bool(sim_cfg.get("passthrough_detections", True)) if sim_cfg else True
            if use_pt:
                self.vision.set_external_detector(
                    SimDetectionInjector(scene, fake_conf=0.85))
                self.logger.info("kaynak: synthetic + GT passthrough")
            else:
                self.vision.set_external_detector(None)
                self.logger.info("kaynak: synthetic (YOLO)")
            return scene

        # Sentetik dışı kaynaklarda passthrough'u kapat
        self.vision.set_external_detector(None)

        if self.source == "esp32":
            # Timeout'lu helper — ölü stream'de sonsuz blocking yok
            return _open_esp32_stream(
                self.cfg.connection.stream_url, self.logger, timeout_sec=8.0)

        # webcam — platforma göre backend seç (Windows DSHOW, macOS AVF, Linux V4L2)
        idx = int(self.cfg.mode.webcam_index)
        backend = _webcam_backend()
        self.logger.info(
            "webcam açılıyor: index=%d backend=%s", idx,
            {cv2.CAP_DSHOW: "DSHOW", cv2.CAP_AVFOUNDATION: "AVFoundation",
             cv2.CAP_V4L2: "V4L2"}.get(backend, str(backend)))

        cap = cv2.VideoCapture(idx, backend)
        if not cap.isOpened():
            # Fallback: default backend dene (bazı USB kameraları DSHOW reddediyor)
            self.logger.warning(
                "backend %s ile açılamadı, varsayılan backend deneniyor...",
                backend)
            try:
                cap.release()
            except Exception:
                pass
            cap = cv2.VideoCapture(idx)
            if not cap.isOpened():
                self.logger.error(
                    "WEBCAM AÇILAMADI (index=%d). Çözüm yolları:\n"
                    "  • Başka bir uygulama kamerayı kullanıyor olabilir "
                    "(Zoom/Teams/Tarayıcı sekmeleri) — kapatın.\n"
                    "  • Windows Ayarlar → Gizlilik → Kamera: 'Masaüstü uygulamaları' AÇIK olmalı.\n"
                    "  • Farklı bir index deneyin: config.yaml içinde mode.webcam_index=1 yapın.\n"
                    "  • USB kamerayı çıkarıp tekrar takın.", idx)
                try:
                    cap.release()
                except Exception:
                    pass
                return None

        # Çözünürlük: 1280x720 ideal; 60 FPS çoğu webcam'i kırıyor → 30.
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FPS, 30)
        # BUFFERSIZE = 1 latency'yi düşürür; bazı driver'larda fail eder, sessiz geçer.
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        # Warmup: ilk birkaç kare bazen siyah/boş geliyor (özellikle DSHOW)
        # — okumadan döndürürsek ana loop "kare alınamadı" sanır, kaynağı kapatır.
        warmup_ok = False
        for _ in range(10):
            ok, fr = cap.read()
            if ok and fr is not None and fr.size > 0:
                warmup_ok = True
                break
            time.sleep(0.1)
        if not warmup_ok:
            self.logger.error(
                "webcam açıldı ama kare okunamadı — driver yanıt vermiyor. "
                "Başka uygulama kullanıyor olabilir.")
            try:
                cap.release()
            except Exception:
                pass
            return None

        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        f = cap.get(cv2.CAP_PROP_FPS)
        self.logger.info("✓ webcam hazır: %dx%d @ %.0f fps", w, h, f)
        return cap

    # ana döngü
    def _loop(self):
        self.cap = self._open_source()
        if self.cap is None:
            msg = self._explain_open_failure(self.source)
            self.source_error = msg
            self.logger.error("kaynak açılamadı (source=%s) — döngü kapanıyor: %s",
                              self.source, msg)
            self.running = False
            with self.lock:
                self.state_snapshot["running"] = False
                self.state_snapshot["source_error"] = msg
                # Frontend'in "şu an hangi kaynak fail etti"yi gösterebilmesi için
                self.state_snapshot["source"] = self.source
            return

        fps_t = time.time()
        fps_n = 0
        skip = max(1, int(getattr(self.cfg.ai, "inference_every_n", 1)))
        frame_idx = 0
        last_targets = []

        # Reconnect rate-limit: sürekli fail eden kaynak için exponential backoff
        # + max retry. Sentetik bypass — render hiç fail etmemeli.
        reconnect_attempts = 0
        max_reconnects = 5
        backoff = 1.0

        while self.running:
            ok, frame = self.cap.read()
            if not ok or frame is None:
                # Sentetik kaynak fail etmez; etse bile reset için tek try yeter.
                reconnect_attempts += 1
                if reconnect_attempts > max_reconnects:
                    self.logger.error(
                        "kaynak %d denemede açılamadı (source=%s) — "
                        "döngü duruyor. /start ile tekrar deneyin.",
                        max_reconnects, self.source)
                    self.running = False
                    break
                self.logger.warning(
                    "kare alınamadı (deneme %d/%d), %.1fs sonra yeniden...",
                    reconnect_attempts, max_reconnects, backoff)
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None
                # Backoff sırasında stop() çağrılırsa hemen çık
                end_t = time.time() + backoff
                while time.time() < end_t and self.running:
                    time.sleep(0.1)
                if not self.running:
                    break
                self.cap = self._open_source()
                if self.cap is None:
                    backoff = min(backoff * 2, 10.0)
                    continue
                # Yeniden bağlanma başarılı → sayaçları sıfırla
                reconnect_attempts = 0
                backoff = 1.0
                continue
            # Başarılı kare → reconnect sayaçları sıfır
            if reconnect_attempts:
                reconnect_attempts = 0
                backoff = 1.0

            fh, fw = frame.shape[:2]
            self.frame_size = (fw, fh)
            frame_idx += 1

            fps_n += 1
            now = time.time()
            if now - fps_t >= 1.0:
                self.fps = fps_n / (now - fps_t)
                fps_n = 0
                fps_t = now

            if frame_idx % skip == 0:
                try:
                    targets, _smoothed = self.vision.process(frame)
                    last_targets = targets
                except Exception as e:
                    # Tek kare çökerse loop'u koru — bir sonraki kare denenir.
                    self.logger.warning("vision.process exception: %s", e)
                    targets = last_targets
            else:
                targets = last_targets

            # Bbox'sız raw snapshot için kopya sakla
            ok_raw, raw_buf = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 88]
            )
            # Heatmap overlay (overlay'den önce, böylece bbox'lar üstte kalır)
            if self.heatmap_enabled:
                if self._heatmap is None:
                    self._heatmap = FireHeatmap(
                        width=fw, height=fh, decay=self.heatmap_decay)
                self._heatmap.update(targets)
                frame = self._heatmap.render(frame)
            self._draw_overlay(frame, targets)

            angle_deg = 0.0
            primary = targets[0] if targets else None
            if primary is not None:
                fov_h = 60.0
                offset = (primary.cx - fw / 2) / (fw / 2)
                angle_deg = offset * (fov_h / 2)
                self.positions.append((float(primary.cx), float(primary.cy)))

            ok_enc, buf = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80]
            )
            if not ok_enc:
                continue

            # Temporal smoothing
            fire_now = bool(targets)
            now_ts = time.time()
            self.fire_history.append(fire_now)
            if fire_now:
                self.last_fire_ts = now_ts
            window_hits = sum(self.fire_history)
            window_stable = window_hits >= 3 and len(self.fire_history) >= 3
            recent_hold = (now_ts - self.last_fire_ts) <= self.fire_hold_sec
            stable_fire = bool(window_stable or recent_hold)

            # Arduino'ya alert sinyali (rate-limited)
            self._maybe_signal_arduino(stable_fire, now_ts)

            # Webhook bildirimi (stable-fire kenarında)
            try:
                self.webhook.on_state_change(stable_fire, {
                    "n_targets": len(targets),
                    "fps": round(self.fps, 1),
                    "primary_label": primary.label if primary else "",
                    "primary_priority": (
                        round(primary.priority, 3) if primary else 0.0),
                    "source": self.source,
                })
            except Exception as e:
                self.logger.warning("webhook hatası: %s", e)

            heat_c, voltage = self.hw.sensors()

            # Mesafe + heatmap_max
            primary_distance = (
                self.distance_est.estimate(primary, fh) if primary else 0.0)
            hm_max = self._heatmap.max_intensity() if self._heatmap else 0.0

            with self.lock:
                self.latest_jpeg = buf.tobytes()
                if ok_raw:
                    self.latest_raw_jpeg = raw_buf.tobytes()
                self.state_snapshot = {
                    "running": True,
                    "fire_detected": fire_now,
                    "stable_fire": stable_fire,
                    "fire_history": list(self.fire_history),
                    "angle_deg": round(angle_deg, 1),
                    "system_time_ms": int((time.time() - self.t0) * 1000),
                    "n_targets": len(targets),
                    "raw_count": int(self.vision.last_raw_count),
                    "raw_max_conf": round(
                        float(self.vision.last_raw_max_conf), 3),
                    "classes": {
                        k: [v[0], round(v[1], 3)]
                        for k, v in self.vision.last_class_breakdown.items()
                    },
                    "primary_priority": (
                        round(float(primary.priority), 3) if primary else 0.0),
                    "primary_area": (
                        int(primary.area) if primary else 0),
                    "primary_distance_m": round(float(primary_distance), 2),
                    "heatmap_max": round(float(hm_max), 3),
                    "fps": round(self.fps, 1),
                    "heat_c": round(float(heat_c), 1),
                    "voltage": round(float(voltage), 2),
                    "source": self.source,
                    "conf_threshold": float(self.cfg.ai.conf_threshold),
                    "imgsz": int(self.cfg.ai.imgsz),
                }

        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

    # Arduino'ya stable-fire sinyali (rate-limited)
    def _maybe_signal_arduino(self, stable_fire: bool, now_ts: float):
        signal = "F" if stable_fire else "N"
        if signal == self._last_fire_signal:
            # Aynı sinyali sürekli atmaktan kaçınıyoruz; periyodik refresh
            # (Arduino kendi auto-off timeout'u var → 5sn'de bir tekrar yeter)
            if signal == "F" and (now_ts - self._last_signal_ts) > 3.0:
                self.hw.send("F")
                self._last_signal_ts = now_ts
            return
        if (now_ts - self._last_signal_ts) < self._signal_min_gap:
            return
        self.hw.send(signal)
        self._last_fire_signal = signal
        self._last_signal_ts   = now_ts

    # overlay (FIRE bbox + yumuşak HUD)
    @staticmethod
    def _draw_overlay(frame, targets):
        fh, fw = frame.shape[:2]
        for i, t in enumerate(targets):
            # Gerçek bbox tracker'dan geliyorsa onu kullan,
            # yoksa area'dan kare üretip fallback yap.
            if getattr(t, "bbox", None) is not None:
                bx1, by1, bx2, by2 = t.bbox
                x1 = max(0, min(fw - 1, int(bx1)))
                y1 = max(0, min(fh - 1, int(by1)))
                x2 = max(0, min(fw - 1, int(bx2)))
                y2 = max(0, min(fh - 1, int(by2)))
            else:
                side = max(40, int(math.sqrt(max(1.0, t.area))))
                x1 = max(0, t.cx - side // 2)
                y1 = max(0, t.cy - side // 2)
                x2 = min(fw - 1, t.cx + side // 2)
                y2 = min(fh - 1, t.cy + side // 2)
            color = (0, 60, 230) if i == 0 else (60, 160, 230)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            label = "FIRE" if i == 0 else f"#{i+1}"
            (lw, lh), _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_DUPLEX, 0.55, 1)
            cv2.rectangle(frame, (x1, max(0, y1 - lh - 10)),
                          (x1 + lw + 14, y1), color, -1)
            cv2.putText(frame, label, (x1 + 7, max(lh + 4, y1 - 6)),
                        cv2.FONT_HERSHEY_DUPLEX, 0.55,
                        (255, 255, 255), 1, cv2.LINE_AA)

    # erişimciler
    def get_jpeg(self) -> bytes | None:
        with self.lock:
            return self.latest_jpeg

    def get_snapshot_jpeg(self) -> bytes | None:
        with self.lock:
            return self.latest_raw_jpeg or self.latest_jpeg

    def get_state(self) -> dict:
        with self.lock:
            return dict(self.state_snapshot)

    # Manuel komut
    # cmd_char: W/A/S/D/X/K/L. spd: 0..255. arm: "UP"|"DOWN"|""
    def send_command(self, cmd_char: str, spd: int = 180, arm: str = ""):
        cmd_char = (cmd_char or "").upper()[:1]
        if cmd_char not in {"W", "A", "S", "D", "X", "K", "L", "F", "N", "B", "V"}:
            return False, "geçersiz komut"
        spd = max(0, min(255, int(spd)))
        self.hw.send(cmd_char, spd, (arm or "").upper())
        return True, f"sent {cmd_char} spd={spd} arm={arm or '-'}"

    # RANSAC tipi konum çizimi
    def render_plot_png(self) -> bytes:
        with self.lock:
            pts = list(self.positions)
            fw, fh = self.frame_size

        fig, ax = plt.subplots(figsize=(5.0, 4.0), dpi=95)
        ax.set_title("RANSAC ile Yaklaşık Kesişim Noktası", fontsize=10)
        ax.set_facecolor("#ffffff")

        if len(pts) >= 2:
            origin = (fw / 2.0, float(fh))
            xs = np.array([p[0] for p in pts])
            ys = np.array([fh - p[1] for p in pts])

            mx, my = float(np.median(xs)), float(np.median(ys))

            dists = np.hypot(xs - mx, ys - my)
            thr = max(20.0, float(np.std(dists)) * 1.2)
            inlier = dists <= thr

            for x, y in zip(xs, ys):
                ax.plot([origin[0], x], [fh - origin[1], y],
                        color="#3056d3", lw=1.2, alpha=0.55)
            if (~inlier).any():
                ax.scatter(xs[~inlier], ys[~inlier],
                           c="#ff8a3d", s=22, zorder=4)
            if inlier.any():
                ax.scatter(xs[inlier], ys[inlier],
                           c="#21bf73", s=28, zorder=5)
            ax.scatter([mx], [my], c="#e63946", s=80,
                       edgecolors="white", linewidths=1.5, zorder=6)

            handles = [
                Line2D([0], [0], color="#3056d3", lw=1.5, label="Vektör"),
                Line2D([0], [0], marker="o", linestyle="",
                       markerfacecolor="#ff8a3d", markeredgecolor="#ff8a3d",
                       markersize=7, label="Tüm Kesişimler"),
                Line2D([0], [0], marker="o", linestyle="",
                       markerfacecolor="#21bf73", markeredgecolor="#21bf73",
                       markersize=7, label="RANSAC Geçerli Noktalar"),
                Line2D([0], [0], marker="o", linestyle="",
                       markerfacecolor="#e63946", markeredgecolor="white",
                       markersize=9, label="Yaklaşık Merkez"),
            ]
            ax.legend(handles=handles, fontsize=7, loc="upper left",
                      framealpha=0.9)
            ax.set_xlim(-fw * 0.05, fw * 1.05)
            ax.set_ylim(-fh * 0.05, fh * 1.05)
        else:
            ax.text(0.5, 0.5, "yangın bekleniyor…",
                    ha="center", va="center",
                    transform=ax.transAxes, color="#888", fontsize=11)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)

        ax.grid(True, linestyle=":", alpha=0.35)
        ax.tick_params(labelsize=8)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", facecolor="white")
        plt.close(fig)
        return buf.getvalue()


# 2. Flask uygulaması
app = Flask(__name__)
service: VisionService | None = None


@app.after_request
def add_cors_headers(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@app.route("/healthz")
def healthz():
    return jsonify(ok=True)


@app.route("/cameras")
def cameras():
    """Hızlı webcam taraması — 0..max-1 index'lerinden hangileri açılıyor.

    Aktif vision döngüsü bir webcam'i tutuyorsa o index'i probe ETMEYİZ
    (cap zaten kilitli, ikinci open şişer) — yerine 'in_use=True' işaretleriz.
    """
    in_use_idx = None
    try:
        if (service is not None and service.source == "webcam"
                and service.running):
            in_use_idx = int(service.cfg.mode.webcam_index)
    except Exception:
        pass

    max_index = max(1, int(request.args.get("max", 4)))
    items = []
    for i in range(max_index):
        if i == in_use_idx:
            items.append({"index": i, "available": True,
                          "width": 0, "height": 0, "in_use": True})
        else:
            items.append({**_probe_webcam(i), "in_use": False})
    return jsonify(cameras=items,
                   active_source=service.source if service else None)


@app.route("/state")
def state():
    return jsonify(service.get_state())


@app.route("/config")
def config():
    cfg = service.cfg
    return jsonify({
        "conf_threshold": float(cfg.ai.conf_threshold),
        "iou_threshold":  float(cfg.ai.iou_threshold),
        "imgsz":          int(cfg.ai.imgsz),
        "model_path":     str(cfg.ai.model_path),
        "classes_of_interest": list(cfg.ai.get("classes_of_interest") or []),
        "source":         service.source,
        "valid_sources":  list(VisionService.VALID_SOURCES),
        "heat_threshold": float(cfg.robot.heat_threshold_c),
        "voltage_nominal": 11.1,
        "voltage_min":     9.6,
        "version":        "3.1.1",
    })


@app.route("/start", methods=["POST", "OPTIONS"])
def start():
    if request.method == "OPTIONS":
        return ("", 204)
    service.start()
    return jsonify(running=True)


@app.route("/stop", methods=["POST", "OPTIONS"])
def stop():
    if request.method == "OPTIONS":
        return ("", 204)
    service.stop()
    return jsonify(running=False)


@app.route("/source", methods=["POST", "OPTIONS"])
def source_set():
    if request.method == "OPTIONS":
        return ("", 204)
    data = request.get_json(silent=True) or {}
    src = (data.get("source") or request.args.get("source") or "").lower()
    ok = service.set_source(src)
    return jsonify(ok=ok, source=service.source), (200 if ok else 400)


@app.route("/command", methods=["POST", "OPTIONS"])
def command():
    if request.method == "OPTIONS":
        return ("", 204)
    data = request.get_json(silent=True) or {}
    cmd  = (data.get("cmd")  or request.args.get("cmd")  or "X")
    spd  = int(data.get("spd") or request.args.get("spd") or 180)
    arm  = (data.get("arm")  or request.args.get("arm")  or "")
    ok, msg = service.send_command(cmd, spd, arm)
    return jsonify(ok=ok, msg=msg), (200 if ok else 400)


@app.route("/video_feed")
def video_feed():
    boundary = b"--frame"

    def gen():
        while True:
            jpeg = service.get_jpeg()
            if jpeg is None:
                ph = np.full((360, 640, 3), 18, dtype=np.uint8)
                cv2.putText(ph, "kamera bekleniyor",
                            (180, 190), cv2.FONT_HERSHEY_DUPLEX,
                            0.7, (200, 200, 200), 1, cv2.LINE_AA)
                _, b = cv2.imencode(".jpg", ph)
                jpeg = b.tobytes()
            yield (boundary + b"\r\nContent-Type: image/jpeg\r\n\r\n"
                   + jpeg + b"\r\n")
            time.sleep(1 / 60.0)

    return Response(
        gen(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/snapshot")
def snapshot():
    img = service.get_snapshot_jpeg()
    if img is None:
        return Response(b"", status=503, mimetype="image/jpeg")
    resp = Response(img, mimetype="image/jpeg")
    resp.headers["Content-Disposition"] = (
        f'attachment; filename="snap_{int(time.time())}.jpg"')
    return resp


@app.route("/plot.png")
def plot_png():
    return Response(service.render_plot_png(), mimetype="image/png")


# 3. Entry point
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(THIS_DIR / "configs" / "config.yaml"))
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", default=5000, type=int)
    ap.add_argument("--source", default="webcam",
                    choices=list(VisionService.VALID_SOURCES))
    ap.add_argument("--autostart", action="store_true",
                    help="kamera döngüsünü otomatik başlat")
    args = ap.parse_args()

    # Konsol + dosya log: pc_vision_controller ile uyumlu çıktı
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("web")
    # Çıktı dizini config'ten — file handler oraya yazsın
    try:
        cfg_peek = load_config(args.config)
        out_dir = Path(cfg_peek.output.dir)
        if not out_dir.is_absolute():
            out_dir = THIS_DIR / out_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(out_dir / "web_app.log", encoding="utf-8")
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"))
        logger.addHandler(fh)
        # Werkzeug log'larını da dosyaya yansıt
        logging.getLogger("werkzeug").addHandler(fh)
    except Exception as e:
        logger.warning("File log kurulamadı: %s", e)

    cfg = load_config(args.config)

    # Kaynak başlangıcı — set_source flag'leri ayarlar
    global service
    try:
        service = VisionService(cfg, logger)
    except FileNotFoundError as e:
        # Model yoksa anlamlı hata — Flask başlatılmadan kapan
        logger.error("VisionService başlatılamadı: %s", e)
        sys.exit(2)
    service.set_source(args.source)
    if args.autostart:
        service.start()

    logger.info("Flask başlıyor → http://%s:%d  (source=%s)",
                args.host, args.port, args.source)
    logger.info("CORS: * (lokal demo)")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
