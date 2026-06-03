"""
ai/sim_detector.py — Sentetik sahne ground-truth → VisionProcessor uyumlu
==========================================================================
Sentetik FireSceneGenerator'ün etiket çıkışını YOLOv8 detections
formatına çevirir → pc_vision_controller bunu gerçek tespitmiş gibi
takipçi/fuzzy/SA hattına verebilir.

Sebep: YOLOv8 modeli gerçek yangın görüntüleri üzerinde eğitildi; sentetik
sahnenin stilize alev/duman'ı modelin dağılımının dışında, conf çok düşüyor.
Demo amaçlı sentetik moddayken modeli atlayıp GT etiketleri kullanmak
sistemin alt katmanlarını (tracker → fuzzy → SA → FSM → motor) düzgün test
eder.

Kullanım:
    sim_det = SimDetectionInjector(scene)
    detections = sim_det.detect(frame)   # [(bbox, label, conf), ...]
"""
from __future__ import annotations

from typing import List, Tuple

# Sınıf id → label eşlemesi (FireSceneGenerator._compute_labels ile aynı)
CLASS_MAP = {0: "fire", 1: "smoke"}


class SimDetectionInjector:
    """FireSceneGenerator'ün GT bbox'larını YOLO-uyumlu detection listesine
    dönüştürür. Her bbox'a yapay ama yüksek bir conf atanır."""

    def __init__(self, scene, fake_conf: float = 0.85):
        self.scene = scene
        self.fake_conf = float(fake_conf)
        # Scene'in etiket üretmesini garantile
        try:
            self.scene.cfg.emit_labels = True
        except AttributeError:
            pass

    def detect(self, frame=None) -> List[Tuple[Tuple[int, int, int, int], str, float]]:
        """Frame parametresi alır (VisionProcessor uyumu için) ama
        scene'in son render'ından gelen etiketleri kullanır."""
        labels = []
        try:
            labels = self.scene.last_labels()
        except AttributeError:
            return []
        out: List[Tuple[Tuple[int, int, int, int], str, float]] = []
        for cls, x1, y1, x2, y2 in labels:
            name = CLASS_MAP.get(int(cls), "fire")
            out.append(((int(x1), int(y1), int(x2), int(y2)),
                        name, self.fake_conf))
        return out
