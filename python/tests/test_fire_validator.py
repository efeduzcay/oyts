"""FireValidator — multi-signal yangın doğrulayıcı testleri."""
import numpy as np
import pytest

from ai.fire_validator import FireValidator


def _flame_frame(w=320, h=240, x=120, y=80, size=40):
    """Sahte: koyu arka plan + ortada parlak turuncu/sarı çekirdek."""
    img = np.full((h, w, 3), 20, dtype=np.uint8)
    # Turuncu halka (BGR)
    img[y:y+size, x:x+size] = (40, 130, 230)
    # Beyaz parlak çekirdek
    cx, cy = x + size // 2, y + size // 2
    img[cy-6:cy+6, cx-6:cx+6] = (245, 245, 245)
    return img


def _solid_red_frame(w=320, h=240, x=80, y=60, size=80):
    """Düz kırmızı bir 'foto' bölgesi — alev değil."""
    img = np.full((h, w, 3), 40, dtype=np.uint8)
    img[y:y+size, x:x+size] = (40, 40, 200)   # düşük V, S yüksek; kırmızı
    return img


def test_static_red_image_rejected_after_warmup():
    """Statik kırmızı bölge: temporal=motion=0 → composite çok düşük → reject."""
    v = FireValidator(history_size=4, min_score=0.35)
    f = _solid_red_frame()
    bbox = (80, 60, 160, 140)
    ok, scores = True, None
    # Birkaç frame aynı resmi besle (history dolsun)
    for i in range(6):
        v.begin_frame(f)
        ok, scores = v.validate(f, bbox)
        v.end_frame()
    assert not ok, f"composite={scores.composite:.3f} scores={scores.as_dict()}"
    assert scores.temporal < 0.2
    assert scores.motion < 0.2


def test_flickering_flame_accepted():
    """Titreyen alev kabul edilmeli — gerçek alev gibi hem hareket
    hem parlaklık varyansı simüle ediyoruz."""
    v = FireValidator(history_size=4, min_score=0.35)
    bbox = (120, 80, 160, 120)
    # 6 frame: konum + parlaklık jitter (gerçek titreme simülasyonu)
    np.random.seed(7)
    last_ok = False
    last_scores = None
    for i in range(6):
        # Hem boyut hem konum oynat (motion sinyali için)
        size_off = np.random.randint(-4, 5)
        x_off    = np.random.randint(-3, 4)
        y_off    = np.random.randint(-3, 4)
        f = _flame_frame(x=120 + x_off, y=80 + y_off, size=40 + size_off)
        v.begin_frame(f)
        ok, scores = v.validate(f, bbox)
        last_ok, last_scores = ok, scores
        v.end_frame()
    assert last_ok, f"composite={last_scores.composite:.3f} scores={last_scores.as_dict()}"
    # Temporal ve motion alev için pozitif olmalı
    assert last_scores.temporal > 0.2
    assert last_scores.motion > 0.05


def test_begin_frame_required():
    """begin_frame çağrılmazsa güvenli default (kabul) döner."""
    v = FireValidator()
    ok, _ = v.validate(_flame_frame(), (10, 10, 50, 50))
    assert ok is True


def test_temporal_only_mode():
    """enable_temporal_only: sadece temporal sinyale bakar."""
    v = FireValidator(enable_temporal_only=True, min_score=0.5)
    f = _solid_red_frame()
    for _ in range(5):
        v.begin_frame(f); v.validate(f, (80, 60, 160, 140)); v.end_frame()
    ok, scores = v.validate(f, (80, 60, 160, 140))
    # composite == temporal; statik resim için düşük
    assert scores.composite == scores.temporal


def test_reset_clears_history():
    v = FireValidator()
    v.begin_frame(_flame_frame()); v.end_frame()
    v.begin_frame(_flame_frame()); v.end_frame()
    v.reset()
    assert v._gray_history.__len__() == 0


def test_tiny_bbox_rejected():
    """6 pikselden küçük bbox direkt reject."""
    v = FireValidator()
    v.begin_frame(_flame_frame())
    ok, scores = v.validate(_flame_frame(), (10, 10, 13, 13))
    assert not ok
    assert scores.composite == 0
