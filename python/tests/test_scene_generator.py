"""FireSceneGenerator smoke testleri — render boyutu, etiket çıktısı, anahtar.

Render hızı testi DEĞİL — sadece "kırılmadan çalışıyor mu" kontrolü.
"""
import numpy as np
import pytest

from sim.fire_scene_generator import FireSceneGenerator, SceneConfig


def test_scene_returns_correct_shape():
    gen = FireSceneGenerator(SceneConfig(width=320, height=240, n_targets=2,
                                          enable_keys=False))
    ok, frame = gen.read()
    assert ok
    assert frame.shape == (240, 320, 3)
    assert frame.dtype == np.uint8


def test_scene_emit_labels():
    gen = FireSceneGenerator(SceneConfig(width=320, height=240, n_targets=2,
                                          emit_labels=True, enable_keys=False))
    # Birkaç frame ısınsın
    for _ in range(3):
        gen.read()
    labels = gen.last_labels()
    # En az alev etiketleri gelmeli
    fire_lbls = [l for l in labels if l[0] == 0]
    assert len(fire_lbls) >= 1
    # Her etiket geçerli bbox formatında
    for cls, x1, y1, x2, y2 in labels:
        assert cls in (0, 1)
        assert 0 <= x1 < x2 <= 320
        assert 0 <= y1 < y2 <= 240


def test_scene_handle_key_changes_target_count():
    gen = FireSceneGenerator(SceneConfig(width=320, height=240, n_targets=2,
                                          enable_keys=True))
    gen.handle_key(ord("4"))
    assert gen.cfg.n_targets == 4


def test_scene_zoom_within_bounds():
    gen = FireSceneGenerator(SceneConfig(width=320, height=240, n_targets=1,
                                          enable_keys=True))
    for _ in range(20):
        gen.handle_key(ord("+"))
    assert gen.cfg.approach_zoom <= 4.0
    for _ in range(50):
        gen.handle_key(ord("-"))
    assert gen.cfg.approach_zoom >= 1.0


def test_isOpened_always_true():
    gen = FireSceneGenerator(SceneConfig(width=160, height=120, n_targets=1,
                                          enable_keys=False))
    assert gen.isOpened() is True
