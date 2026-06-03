"""
ai/bright_flame_detector.py — Küçük alev (çakmak, mum) için klasik CV detector
==============================================================================
YOLO modeli ÇAKMAK gibi 50-300 piksel alevleri sıkça atlar (training datasetinde
yok). Bu modül HSV tabanlı algoritma ile bunları yakalar:

  1. V > 240 (neredeyse beyaz çekirdek) — alev iç merkezi
  2. Çevresinde turuncu/sarı halo (H 0-40 + S 100+)
  3. Çevresi karanlık (alev karanlıkta parlar — kontrast)
  4. Bbox aspect ratio dikey (alev yukarı uzar) — opsiyonel zayıf filtre

Çıkış: YOLO ile aynı formatta detections listesi
       [(bbox, label, conf), ...] — label = "fire", conf = composite skor

VisionProcessor'a YOLO sonrası eklenir, validator ikisini birden doğrular.
"""
from __future__ import annotations

from typing import List, Tuple

import cv2
import numpy as np


class BrightFlameDetector:
    """Klasik CV — küçük parlak alev çekirdekli bölgeleri bulur.

    Args:
        min_area: alev çekirdeği min piksel² (çok küçük gürültüyü ele)
        max_area: max piksel² (büyük parlak alanları YOLO halletsin)
        min_dark_ratio: çevresindeki karanlık piksel oranı (kontrast)
        fake_conf: bulunan adaylara atanan conf değeri (YOLO uyumu için)
    """

    def __init__(self,
                 min_area: int = 30,
                 max_area: int = 4000,
                 min_dark_ratio: float = 0.30,
                 fake_conf: float = 0.50,
                 pad_ratio: float = 0.7):
        self.min_area = int(min_area)
        self.max_area = int(max_area)
        self.min_dark_ratio = float(min_dark_ratio)
        self.fake_conf = float(fake_conf)
        self.pad_ratio = float(pad_ratio)
        # Morphology kernel
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

    def detect(self, frame: np.ndarray
               ) -> List[Tuple[Tuple[int, int, int, int], str, float]]:
        h, w = frame.shape[:2]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 1) Çekirdek maskesi: V çok yüksek + S en az orta + ALEV HUE
        # El/cilt parlak beyaz olabilir ama hue 0-15 (kırmızımsı ten) veya
        # düşük S; alev çekirdeği H 5-45 (turuncu-sarı) + yüksek V.
        # Plus: alev beyaz çekirdeği için S düşük olsa da V çok yüksek (>=250)
        h = hsv[..., 0]
        v = hsv[..., 2]
        s = hsv[..., 1]
        flame_hue = (h <= 45) | (h >= 160)   # turuncu-sarı veya kırmızı wrap
        super_bright = v >= 250               # beyaz çekirdek (S düşük olabilir)
        bright_satur = (v >= 240) & (s >= 80) # parlak + saturated halo
        core_mask = ((super_bright | (bright_satur & flame_hue))
                     .astype(np.uint8) * 255)

        # Çevre maskesi: çekirdek genişletilip beyaza yakın etrafa bakılır
        if core_mask.sum() == 0:
            return []

        core_mask = cv2.morphologyEx(core_mask, cv2.MORPH_OPEN, self._kernel)
        core_mask = cv2.morphologyEx(core_mask, cv2.MORPH_CLOSE, self._kernel,
                                      iterations=2)

        # 2) Bağlı bileşenler — her çekirdek aday
        n_lbl, labels, stats, _ = cv2.connectedComponentsWithStats(
            core_mask, connectivity=8)

        detections = []
        for i in range(1, n_lbl):
            area = int(stats[i, cv2.CC_STAT_AREA])
            if area < self.min_area or area > self.max_area:
                continue
            x = int(stats[i, cv2.CC_STAT_LEFT])
            y = int(stats[i, cv2.CC_STAT_TOP])
            cw = int(stats[i, cv2.CC_STAT_WIDTH])
            ch = int(stats[i, cv2.CC_STAT_HEIGHT])

            # 3) Alev bbox'ı genişlet (çekirdeğin etrafındaki halo + uzantı)
            pad_x = int(cw * self.pad_ratio)
            pad_y_top = int(ch * (self.pad_ratio + 0.6))    # üst daha geniş
            pad_y_bot = int(ch * self.pad_ratio * 0.4)      # alt dar
            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y_top)
            x2 = min(w - 1, x + cw + pad_x)
            y2 = min(h - 1, y + ch + pad_y_bot)
            if x2 - x1 < 8 or y2 - y1 < 8:
                continue

            # 4) Kontrast kontrolü: çevresi karanlık olmalı (alev karanlıkta parlar)
            # bbox'un dışındaki halka piksel ortalaması
            outer_pad = 12
            ox1 = max(0, x1 - outer_pad)
            oy1 = max(0, y1 - outer_pad)
            ox2 = min(w - 1, x2 + outer_pad)
            oy2 = min(h - 1, y2 + outer_pad)
            outer_v = v[oy1:oy2, ox1:ox2]
            inner_v = v[y1:y2, x1:x2]
            if outer_v.size == 0 or inner_v.size == 0:
                continue
            # Halka = outer - inner; ama performans için outer ortalamasını kullan
            # ve inner ortalamasından farkına bak
            outer_mean = float(outer_v.mean())
            inner_mean = float(inner_v.mean())
            # Çekirdek çevreden en az 60 birim daha parlak olmalı
            if (inner_mean - outer_mean) < 50:
                continue
            # Çevredeki karanlık piksel oranı
            outer_only_mask = np.ones_like(outer_v, dtype=bool)
            # iç dikdörtgeni hariç tut
            iy1 = max(0, y1 - oy1); ix1 = max(0, x1 - ox1)
            iy2 = iy1 + (y2 - y1);  ix2 = ix1 + (x2 - x1)
            outer_only_mask[iy1:iy2, ix1:ix2] = False
            outer_only = outer_v[outer_only_mask]
            if outer_only.size == 0:
                continue
            dark_ratio = float((outer_only < 80).mean())
            if dark_ratio < self.min_dark_ratio:
                # çevre karanlık değil → kırmızı duvar, ekran beyazı vb. → ele
                continue

            detections.append(((x1, y1, x2, y2), "fire", self.fake_conf))

        return detections
