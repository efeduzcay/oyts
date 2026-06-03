"""
ai/heatmap.py — Yangın yoğunluk ısı haritası (per-pixel risk gradient)
======================================================================
Her tespit bbox'ını priority-ağırlıklı Gaussian disk olarak haritaya yazar,
kareler arası temporal decay ile yumuşatır. Çıktı (Hot palette → red→yellow)
ham frame üzerine alpha-blend edilir.

Kullanım:
    hm = FireHeatmap(width=960, height=540)
    hm.update(targets)              # her frame
    overlay = hm.render(frame)      # blended bgr
"""
from __future__ import annotations

from typing import Iterable, Optional

import cv2
import numpy as np


class FireHeatmap:
    """Düşük çözünürlüklü çalışan, hızlı bir yangın risk ısı haritası.

    Tespit bbox'larını ağırlıklı Gaussian disk olarak basar; ardışık
    karelerin etkisini `decay` ile sönümler — kararlı bölgeler kırmızı,
    geçici tespitler soluk turuncu olarak görünür.
    """

    def __init__(self,
                 width: int,
                 height: int,
                 decay: float = 0.88,
                 blur_sigma: float = 12.0,
                 alpha: float = 0.45,
                 low_res: int = 6):
        self.width = width
        self.height = height
        self.decay = float(np.clip(decay, 0.0, 0.999))
        self.blur_sigma = max(1.0, float(blur_sigma))
        self.alpha = float(np.clip(alpha, 0.0, 1.0))
        # Heatmap düşük çözünürlükte tutulur (8x daha az piksel),
        # render'da upsample edilir → ~10x daha hızlı blur.
        self.low_w = max(64, width // low_res)
        self.low_h = max(48, height // low_res)
        self._field = np.zeros((self.low_h, self.low_w), dtype=np.float32)
        # Hot palette LUT (256 → BGR)
        self._lut = self._make_lut()

    @staticmethod
    def _make_lut() -> np.ndarray:
        x = np.linspace(0, 1, 256, dtype=np.float32)
        # Siyah → koyu kırmızı → turuncu → sarı → beyaz
        r = np.clip(x * 3.0, 0, 1)
        g = np.clip(x * 3.0 - 1.0, 0, 1)
        b = np.clip(x * 3.0 - 2.0, 0, 1)
        lut = np.stack([b * 255, g * 255, r * 255], axis=1).astype(np.uint8)
        return lut

    def update(self, targets: Iterable) -> None:
        """Her target için priority-ağırlıklı disk çizip decay uygula."""
        # Decay
        self._field *= self.decay
        sx = self.low_w / self.width
        sy = self.low_h / self.height
        for t in targets:
            pri = float(getattr(t, "priority", 0.5))
            cx = int(getattr(t, "cx", 0) * sx)
            cy = int(getattr(t, "cy", 0) * sy)
            area = float(getattr(t, "area", 100.0))
            # Disk yarıçapı: alan ile orantılı, ama küçük bbox da görünür kalsın
            r = int(np.sqrt(max(50.0, area)) * 0.6 * (sx + sy) * 0.5)
            r = max(4, min(self.low_w // 2, r))
            if 0 <= cx < self.low_w and 0 <= cy < self.low_h:
                cv2.circle(self._field, (cx, cy), r, float(pri), -1)
        np.clip(self._field, 0.0, 1.0, out=self._field)

    def render(self, frame: np.ndarray) -> np.ndarray:
        """Frame üzerine ısı haritasını alpha-blend eder ve döner.

        frame BGR uint8; çıktı da BGR uint8.
        """
        if self._field.max() < 0.02:
            return frame
        blurred = cv2.GaussianBlur(self._field, (0, 0), self.blur_sigma)
        blurred = np.clip(blurred, 0.0, 1.0)
        # LUT-renkli ısı haritası
        idx = (blurred * 255).astype(np.uint8)
        colored_low = self._lut[idx]
        colored = cv2.resize(colored_low, (frame.shape[1], frame.shape[0]),
                             interpolation=cv2.INTER_LINEAR)
        # Alpha: yoğunluk yüksek piksellerde daha opak
        alpha_map = cv2.resize(blurred, (frame.shape[1], frame.shape[0]),
                               interpolation=cv2.INTER_LINEAR)
        a = (alpha_map * self.alpha)[..., None]
        out = frame.astype(np.float32) * (1 - a) + colored.astype(np.float32) * a
        return np.clip(out, 0, 255).astype(np.uint8)

    def max_intensity(self) -> float:
        """Anlık en yüksek risk değeri [0,1] — telemetriye uygun."""
        return float(self._field.max())

    def reset(self) -> None:
        self._field.fill(0.0)
