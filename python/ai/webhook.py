"""
ai/webhook.py — Stable-fire olayında dış sistemlere bildirim
=============================================================
Yangın kararı geldiğinde (stable_fire=True'ya geçtiği an) yapılandırılmış bir
JSON payload'unu bir veya birden çok URL'ye POST eder. Rate-limit'li ve
non-blocking (arka plan thread'inde).

Config örneği:
    notify:
      webhooks:
        - "https://hooks.example.com/oyts"
        - "http://192.168.1.5:8000/alarm"
      min_interval_sec: 30
      include_snapshot_b64: false
      timeout_sec: 3.0

Kullanım:
    notifier = WebhookNotifier(cfg.notify, logger)
    notifier.on_state_change(stable_fire=True, state_snapshot=...)
"""
from __future__ import annotations

import base64
import json
import logging
import queue
import threading
import time
import urllib.error
import urllib.request
from typing import Iterable, Optional


class WebhookNotifier:
    def __init__(self, cfg, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger("WebhookNotifier")
        self.urls = list(self._cfg_get(cfg, "webhooks", []) or [])
        self.min_interval = float(self._cfg_get(cfg, "min_interval_sec", 30.0))
        self.include_snapshot_b64 = bool(
            self._cfg_get(cfg, "include_snapshot_b64", False))
        self.timeout = float(self._cfg_get(cfg, "timeout_sec", 3.0))

        self._last_sent = 0.0
        self._prev_fire = False
        self._q: "queue.Queue[dict]" = queue.Queue(maxsize=32)
        self._running = bool(self.urls)
        if self._running:
            threading.Thread(target=self._worker, daemon=True).start()
            self.logger.info("WebhookNotifier aktif: %d hedef", len(self.urls))

    @staticmethod
    def _cfg_get(cfg, key, default):
        if cfg is None:
            return default
        try:
            return cfg.get(key, default)
        except AttributeError:
            return getattr(cfg, key, default)

    def on_state_change(self, stable_fire: bool, state_snapshot: dict,
                        jpeg_bytes: Optional[bytes] = None) -> None:
        """Stable-fire kenarı (False→True) olduğunda webhook'u tetikler."""
        if not self._running:
            return
        rising_edge = stable_fire and not self._prev_fire
        self._prev_fire = stable_fire
        if not rising_edge:
            return
        now = time.time()
        if (now - self._last_sent) < self.min_interval:
            return
        self._last_sent = now
        payload = {
            "event": "fire_confirmed",
            "ts": now,
            "state": dict(state_snapshot),
        }
        if self.include_snapshot_b64 and jpeg_bytes:
            payload["snapshot_b64"] = base64.b64encode(jpeg_bytes).decode()
        try:
            self._q.put_nowait(payload)
        except queue.Full:
            self.logger.warning("webhook kuyruğu dolu, payload düşürüldü")

    def _worker(self) -> None:
        while True:
            payload = self._q.get()
            data = json.dumps(payload).encode("utf-8")
            for url in self.urls:
                try:
                    req = urllib.request.Request(
                        url, data=data,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=self.timeout):
                        self.logger.info("webhook → %s OK", url)
                except (urllib.error.URLError, urllib.error.HTTPError,
                        TimeoutError, ConnectionError) as e:
                    self.logger.warning("webhook → %s başarısız: %s", url, e)
                except Exception as e:
                    self.logger.warning("webhook → %s beklenmeyen hata: %s", url, e)
