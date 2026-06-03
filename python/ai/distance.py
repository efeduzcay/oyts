"""
ai/distance.py — Mono-kameradan kaba mesafe tahmini
====================================================
Tek kameradan derinlik tahmini → ucuz, kaba bir bbox-area / vertical-position
formülü. Tek noktada kalibre edilirse %20-30 hata ile çalışır (laboratuvar).

Model:
    Bilinen referans bbox alanı A_ref piksel², bu hedef kamera düzleminde
    `D_ref` metre uzakta. Bbox boyu lineer olarak mesafeyle ters orantılı:
        D = D_ref * sqrt(A_ref / A)

    Vertical position (bbox y-merkez) zemin düzleminde 'kameranın altı' iddiası
    ile düzeltici çarpan: ekranın altına yakın hedef => daha yakın.

Kalibrasyon (bir kere):
    `python ai/distance.py --calibrate path/to/known_distance.jpg --dist 1.5`
    sonucu config'e yaz:
        distance:
          ref_area_px: 8400
          ref_distance_m: 1.5

Kullanım:
    est = DistanceEstimator(ref_area=8400, ref_distance=1.5)
    d = est.estimate(target)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DistanceEstimator:
    """Bbox alanını metre cinsinden mesafeye çevirir.

    Yangın kaynağı boyutu sahneler arasında değişebilir → bu tahmin
    *kabadır* ve sadece relative karşılaştırma için güvenilirdir.
    """
    ref_area: float = 8400.0          # piksel²
    ref_distance: float = 1.5         # metre
    min_distance: float = 0.15
    max_distance: float = 20.0
    # Ekranın altı = daha yakın varsayımı için düşey düzeltme [0..1] aralığı
    use_vertical_bias: bool = True
    bottom_close_factor: float = 0.75   # ekranın en altı → mesafe * 0.75

    def estimate(self, target, frame_height: Optional[int] = None) -> float:
        """target.area + target.cy kullanır."""
        area = max(1.0, float(getattr(target, "area", 1.0)))
        d = self.ref_distance * (self.ref_area / area) ** 0.5
        if self.use_vertical_bias and frame_height:
            cy = float(getattr(target, "cy", frame_height * 0.5))
            # ekranın altı (cy/H → 1.0) → bottom_close_factor;
            # ekranın üstü (cy/H → 0)  → 1.0
            t = max(0.0, min(1.0, cy / max(1.0, float(frame_height))))
            factor = 1.0 - (1.0 - self.bottom_close_factor) * t
            d *= factor
        return float(max(self.min_distance, min(self.max_distance, d)))

    @classmethod
    def from_config(cls, cfg) -> "DistanceEstimator":
        """Config'in distance bölümünden örnek üretir (yoksa varsayılan)."""
        if cfg is None:
            return cls()
        try:
            d = cfg.distance
            return cls(
                ref_area=float(d.get("ref_area_px", 8400)),
                ref_distance=float(d.get("ref_distance_m", 1.5)),
                use_vertical_bias=bool(d.get("use_vertical_bias", True)),
                bottom_close_factor=float(d.get("bottom_close_factor", 0.75)),
            )
        except (AttributeError, KeyError):
            return cls()
