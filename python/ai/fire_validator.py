"""
ai/fire_validator.py — Multi-signal yangın tespiti doğrulayıcı
================================================================
YOLOv8 bir bbox döndürdüğünde, gerçek alevin sahip olması beklenen
4 fiziksel imzayı ölçer ve ağırlıklı skor ile false-positive eler:

  1. Temporal Varyans    — Alev titrer; statik resim/foto 0 varyans verir.
                          Son K karenin ROI ortalama parlaklık STD'si.
  2. Parlak Çekirdek     — Gerçek alev V>240 (neredeyse beyaz) çekirdeğe
                          sahiptir. Kırmızı/turuncu fotoda olmaz.
  3. Motion Entropy      — ROI bölgesinde frame-fark entropisi (çakmak
                          küçüktür ama hareketlidir; foto hiç oynamaz).
  4. Saturasyon Profili  — Alev: yüksek S + yüksek V. Ten/yüz: orta S,
                          orta V (parlak değil). Cilt elenir.

Skor: 0..1. `min_score`'un altı → reject. Tipik eşik 0.45.

Kullanım:
    val = FireValidator(history_size=8, min_score=0.45)
    val.begin_frame(frame)                  # her frame'in başında
    for (bbox, label, conf) in detections:
        ok, scores = val.validate(frame, bbox)
        if not ok:
            continue   # false positive say
    val.end_frame()                         # history rotate
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional, Tuple

import cv2
import numpy as np


@dataclass
class ValidatorScores:
    """Frame-bazlı doğrulama detayları (debug/CSV için)."""
    temporal: float       # 0..1 (alev titreme şiddeti)
    bright_core: float    # 0..1 (V>240 piksel oranı)
    motion: float         # 0..1 (frame-fark entropisi)
    saturation: float     # 0..1 (alev rengi konformanı)
    composite: float      # ağırlıklı toplam

    def as_dict(self) -> dict:
        return {
            "temporal": round(self.temporal, 3),
            "bright_core": round(self.bright_core, 3),
            "motion": round(self.motion, 3),
            "saturation": round(self.saturation, 3),
            "composite": round(self.composite, 3),
        }


class FireValidator:
    """Multi-signal yangın tespiti doğrulayıcı.

    Args:
        history_size: kaç son grayscale frame tutulsun (temporal için)
        min_score: composite skor bu değerin altıysa REJECT
        weights: 4 alt skorun ağırlıkları (toplam ≈ 1)
        enable_temporal_only: True ise sadece temporal varyansa bak
            (debug — diğer kanalları kapatır)
    """

    DEFAULT_WEIGHTS = {
        # bright_core (V>245) gerçek alevin en güvenilir imzası —
        # kırmızı fotoda V çok parlak gelmez, ten/yüzde sporadik.
        "bright_core": 0.45,
        "temporal":    0.25,
        "motion":      0.20,
        "saturation":  0.10,
    }

    def __init__(self,
                 history_size: int = 8,
                 min_score: float = 0.45,
                 weights: Optional[Dict[str, float]] = None,
                 enable_temporal_only: bool = False):
        self.history_size = max(2, int(history_size))
        self.min_score = float(min_score)
        self.weights = dict(self.DEFAULT_WEIGHTS)
        if weights:
            self.weights.update(weights)
        self.enable_temporal_only = enable_temporal_only
        self._gray_history: Deque[np.ndarray] = deque(maxlen=self.history_size)
        self._curr_gray: Optional[np.ndarray] = None
        self._curr_hsv: Optional[np.ndarray] = None
        self._last_scores: Optional[ValidatorScores] = None

    # frame lifecycle
    def begin_frame(self, frame: np.ndarray) -> None:
        """Yeni frame geldi → grayscale + HSV cache'le."""
        self._curr_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        self._curr_hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    def end_frame(self) -> None:
        """Tüm validate çağrıları bittikten sonra çağır → history rotate."""
        if self._curr_gray is not None:
            self._gray_history.append(self._curr_gray.copy())

    # ana doğrulama
    def validate(self, frame: np.ndarray,
                 bbox: Tuple[int, int, int, int]
                 ) -> Tuple[bool, ValidatorScores]:
        """Bbox'ı 4 sinyalde değerlendir, kabul/red kararı + skorlar."""
        x1, y1, x2, y2 = bbox
        fh, fw = frame.shape[:2]
        x1 = max(0, min(fw - 1, int(x1)))
        y1 = max(0, min(fh - 1, int(y1)))
        x2 = max(0, min(fw - 1, int(x2)))
        y2 = max(0, min(fh - 1, int(y2)))
        if x2 - x1 < 6 or y2 - y1 < 6:
            return False, ValidatorScores(0, 0, 0, 0, 0)

        if self._curr_gray is None or self._curr_hsv is None:
            # begin_frame çağrılmadı → güvenli default: kabul
            return True, ValidatorScores(0.5, 0.5, 0.5, 0.5, 0.5)

        roi_hsv = self._curr_hsv[y1:y2, x1:x2]

        s_temporal    = self._score_temporal(x1, y1, x2, y2)
        s_bright_core = self._score_bright_core(roi_hsv)
        s_motion      = self._score_motion(x1, y1, x2, y2)
        s_saturation  = self._score_saturation(roi_hsv)

        if self.enable_temporal_only:
            composite = s_temporal
        else:
            w = self.weights
            composite = (
                w["temporal"]    * s_temporal +
                w["bright_core"] * s_bright_core +
                w["motion"]      * s_motion +
                w["saturation"]  * s_saturation
            )

        scores = ValidatorScores(s_temporal, s_bright_core,
                                 s_motion, s_saturation, composite)
        self._last_scores = scores
        return composite >= self.min_score, scores

    # alt skorlar
    def _score_temporal(self, x1: int, y1: int, x2: int, y2: int) -> float:
        """ROI içindeki PİKSEL-PİKSEL hareket — alev içi titreşim.
        Sabit alev bile içinden titrer (alev kenarı sürekli değişir).
        Statik foto: tüm pikseller aynı → 0.

        Eski yaklaşım (mean STD) sabit alevi kaçırıyordu çünkü ortalama
        parlaklık sabit olabilir ama içindeki desen titrer."""
        if len(self._gray_history) < 3:
            # Yeterli geçmiş yok → 0 (tek-frame foto reddi)
            return 0.0
        # Son 4 frame'in ROI'leri ile şimdiki ROI arasındaki absdiff toplamı
        # Alev kenarları sürekli oynar → yüksek; statik → 0
        curr_roi = self._curr_gray[y1:y2, x1:x2]
        if curr_roi.size == 0:
            return 0.0
        diffs = []
        for g in list(self._gray_history)[-4:]:
            if g.shape != self._curr_gray.shape:
                continue
            prev_roi = g[y1:y2, x1:x2]
            # Ortalama mutlak fark — alev içinde sürekli desen değişimi
            d = float(np.abs(curr_roi.astype(np.int16) -
                              prev_roi.astype(np.int16)).mean())
            diffs.append(d)
        if not diffs:
            return 0.0
        # Maksimum ve ortalamayı al — flicker en az bir karede güçlü olur
        max_d = max(diffs)
        avg_d = sum(diffs) / len(diffs)
        # Alev tipik 3-15 birim. Statik foto: 0-0.5. Hafif kamera gürültüsü: 0.5-1.5
        # 2+ birim = gerçek alev hareketi (gürültü üstü)
        score = (max_d * 0.6 + avg_d * 0.4) / 5.0
        return float(np.clip(score, 0.0, 1.0))

    def _score_bright_core(self, roi_hsv: np.ndarray) -> float:
        """ROI içinde V≥245 piksel oranı. Gerçek alev çekirdeği neredeyse
        beyaz parlar. Kırmızı fotoda V genelde 180-220, yüzde sporadik.
        Sıkı eşik (245+) cilt highlight'larını da eler."""
        if roi_hsv.size == 0:
            return 0.0
        v = roi_hsv[..., 2]
        s = roi_hsv[..., 1]
        h = roi_hsv[..., 0]
        # Çekirdek = V≥245 + S nispeten düşük olabilir (beyaz)
        # AMA çevresi alev rengi olmalı (H 0-45 veya 160+)
        super_bright = v >= 245
        flame_hue_pix = (h <= 45) | (h >= 160)
        # Beyaz çekirdek + civarında alev rengi varlığı (yumuşatma)
        core_mask = super_bright & (flame_hue_pix | (s >= 100))
        ratio = float(core_mask.mean())
        # 0 → 0, 0.03+ → 1.0 (alev çekirdeği genelde %1-15)
        return float(np.clip(ratio / 0.03, 0.0, 1.0))

    def _score_motion(self, x1: int, y1: int, x2: int, y2: int) -> float:
        """Son frame ile şimdiki frame'in mutlak farkı (ROI). Statik = 0."""
        if not self._gray_history:
            return 0.5
        prev = self._gray_history[-1]
        if prev.shape != self._curr_gray.shape:
            return 0.5
        diff = cv2.absdiff(
            self._curr_gray[y1:y2, x1:x2], prev[y1:y2, x1:x2])
        # Ortalama hareket — alev sürekli oynar, foto 0
        mean_motion = float(diff.mean())
        return float(np.clip(mean_motion / 6.0, 0.0, 1.0))

    def _score_saturation(self, roi_hsv: np.ndarray) -> float:
        """Alev rengi konformanı:
           - Hue: 0-30 (turuncu-sarı) veya 160-180 (kırmızı wrap)
           - Saturation: orta-yüksek
           - V: yüksek
        Sadece bu kombinasyon yüksek skor verir.
        Ten: hue benzer ama S<150 → düşük skor."""
        if roi_hsv.size == 0:
            return 0.0
        h, s, v = roi_hsv[..., 0], roi_hsv[..., 1], roi_hsv[..., 2]
        flame_hue = ((h <= 30) | (h >= 160))
        flame_sat = s >= 160
        flame_val = v >= 180
        mask = flame_hue & flame_sat & flame_val
        ratio = float(mask.mean())
        # Alev tipik %10-50 arasıdır
        return float(np.clip(ratio / 0.15, 0.0, 1.0))

    def last_scores(self) -> Optional[ValidatorScores]:
        return self._last_scores

    def reset(self) -> None:
        self._gray_history.clear()
        self._curr_gray = None
        self._curr_hsv = None
        self._last_scores = None
