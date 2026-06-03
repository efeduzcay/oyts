"""Yeni AI modülleri (heatmap, distance, webhook, sim_detector) testleri."""
import types
import numpy as np
import pytest

from ai.distance import DistanceEstimator
from ai.heatmap import FireHeatmap
from ai.sim_detector import SimDetectionInjector
from ai.webhook import WebhookNotifier


# DistanceEstimator
def _mk_target(area, cy=200):
    return types.SimpleNamespace(area=area, cx=100, cy=cy)


def test_distance_smaller_area_farther():
    est = DistanceEstimator(ref_area=10000, ref_distance=2.0,
                            use_vertical_bias=False)
    d_close = est.estimate(_mk_target(area=10000))
    d_far   = est.estimate(_mk_target(area=2500))
    assert d_close == pytest.approx(2.0, abs=0.05)
    assert d_far  > d_close * 1.5


def test_distance_vertical_bias_brings_closer():
    est = DistanceEstimator(ref_area=10000, ref_distance=2.0,
                            use_vertical_bias=True,
                            bottom_close_factor=0.5)
    d_top    = est.estimate(_mk_target(area=10000, cy=10),  frame_height=400)
    d_bottom = est.estimate(_mk_target(area=10000, cy=390), frame_height=400)
    assert d_bottom < d_top


def test_distance_clipped_within_bounds():
    est = DistanceEstimator(ref_area=1, ref_distance=1.0,
                            min_distance=0.5, max_distance=5.0,
                            use_vertical_bias=False)
    # Çok küçük alan → büyük mesafe, ama max 5 ile kırpılır
    assert est.estimate(_mk_target(area=0.0001)) <= 5.0
    # Çok büyük alan → küçük mesafe, ama min 0.5 ile kırpılır
    assert est.estimate(_mk_target(area=1e9)) >= 0.5


# FireHeatmap
def test_heatmap_initially_zero():
    hm = FireHeatmap(width=320, height=240)
    assert hm.max_intensity() == 0.0


def test_heatmap_updates_increase_intensity():
    hm = FireHeatmap(width=320, height=240, decay=1.0)
    targets = [types.SimpleNamespace(cx=160, cy=120, area=5000, priority=0.9)]
    hm.update(targets)
    assert hm.max_intensity() > 0.5


def test_heatmap_decay_reduces_intensity_over_time():
    hm = FireHeatmap(width=320, height=240, decay=0.5)
    targets = [types.SimpleNamespace(cx=160, cy=120, area=5000, priority=0.9)]
    hm.update(targets)
    first = hm.max_intensity()
    # 5 frame target görünmesin → exponential decay
    for _ in range(5):
        hm.update([])
    assert hm.max_intensity() < first * 0.1


def test_heatmap_render_returns_image_with_same_shape():
    hm = FireHeatmap(width=320, height=240)
    frame = np.full((240, 320, 3), 50, dtype=np.uint8)
    out = hm.render(frame)
    assert out.shape == frame.shape


# SimDetectionInjector
def test_sim_detector_converts_labels():
    scene = types.SimpleNamespace(
        cfg=types.SimpleNamespace(emit_labels=False),
        last_labels=lambda: [(0, 10, 10, 50, 50), (1, 100, 100, 200, 200)],
    )
    inj = SimDetectionInjector(scene, fake_conf=0.7)
    dets = inj.detect(np.zeros((300, 300, 3), dtype=np.uint8))
    assert len(dets) == 2
    bbox0, lbl0, conf0 = dets[0]
    assert bbox0 == (10, 10, 50, 50)
    assert lbl0 == "fire"
    assert conf0 == pytest.approx(0.7)
    assert dets[1][1] == "smoke"


def test_sim_detector_sets_emit_labels_flag():
    cfg = types.SimpleNamespace(emit_labels=False)
    scene = types.SimpleNamespace(cfg=cfg, last_labels=lambda: [])
    SimDetectionInjector(scene)
    assert cfg.emit_labels is True


# WebhookNotifier
def test_webhook_no_urls_is_noop():
    n = WebhookNotifier(cfg=None)
    # state_change çağrısı hata fırlatmamalı
    n.on_state_change(stable_fire=True, state_snapshot={"x": 1})
    assert n.urls == []


def test_webhook_rising_edge_only(monkeypatch):
    """En az 1 URL varken sadece False→True kenarında payload kuyruğa eklenir."""
    cfg = {"webhooks": ["http://noop.invalid/x"], "min_interval_sec": 0}
    n = WebhookNotifier(cfg=cfg)
    # Worker thread'i POST denemesin diye kuyruğu izole et
    sent = []

    class _StubQ:
        def put_nowait(self, x): sent.append(x)
    n._q = _StubQ()
    n.on_state_change(False, {})   # düşük → noop
    n.on_state_change(False, {})   # düşük → noop
    assert sent == []
    n.on_state_change(True, {"k": 1})   # rising → 1 payload
    assert len(sent) == 1
    assert sent[0]["event"] == "fire_confirmed"
    n.on_state_change(True, {})    # tekrar True → tetiklenmez
    assert len(sent) == 1
    n.on_state_change(False, {})   # falling → tetiklenmez
    assert len(sent) == 1
    n.on_state_change(True, {})    # tekrar rising → +1
    assert len(sent) == 2
