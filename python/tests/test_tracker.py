"""IoU tracker davranış testleri."""
import pytest

from ai.tracker import IoUTracker, _iou


def test_iou_perfect_overlap():
    a = (0, 0, 10, 10)
    assert _iou(a, a) == pytest.approx(1.0)


def test_iou_disjoint():
    a = (0, 0, 10, 10)
    b = (20, 20, 30, 30)
    assert _iou(a, b) == 0.0


def test_iou_half_overlap():
    a = (0, 0, 10, 10)
    b = (5, 0, 15, 10)
    # intersection 50, union 150 → 1/3
    assert _iou(a, b) == pytest.approx(50 / 150)


def test_tracker_promotes_after_min_hits():
    t = IoUTracker(iou_threshold=0.3, min_hits=3, stable_grace_frames=0)
    box = ((10, 10, 50, 50), "fire", 0.9)
    # 1 hit — not stable yet
    assert t.update([box]) == []
    assert t.update([box]) == []
    # 3rd hit — stable
    stable = t.update([box])
    assert len(stable) == 1
    assert stable[0].label == "fire"
    assert stable[0].hits == 3


def test_tracker_stable_grace_keeps_target_through_short_gap():
    t = IoUTracker(iou_threshold=0.3, min_hits=2, stable_grace_frames=2)
    box = ((10, 10, 50, 50), "fire", 0.9)
    # bootstrap to stable
    t.update([box])
    t.update([box])
    # detected — stable
    assert len(t.update([box])) == 1
    # miss 1 — still stable (within grace)
    assert len(t.update([])) == 1
    # miss 2 — still stable
    assert len(t.update([])) == 1
    # miss 3 — grace exhausted, demoted
    assert t.update([]) == []


def test_tracker_drops_after_max_missed():
    t = IoUTracker(iou_threshold=0.3, min_hits=1,
                   max_missed=2, stable_grace_frames=0)
    box = ((0, 0, 20, 20), "fire", 0.9)
    t.update([box])
    # miss until track removed
    t.update([])
    t.update([])
    t.update([])
    # iç state'te bu noktada track olmamalı; yeni bbox geldiğinde
    # YENİ id atanmalı (yani önceki silinmiş)
    out = t.update([box])
    assert out[0].track_id != 1 or out[0].hits == 1


def test_tracker_separate_labels_dont_match():
    t = IoUTracker(iou_threshold=0.3, min_hits=1, stable_grace_frames=0)
    fire = ((0, 0, 20, 20), "fire", 0.9)
    smoke = ((0, 0, 20, 20), "smoke", 0.9)
    out1 = t.update([fire])
    out2 = t.update([smoke])
    # Aynı bbox ama farklı label → ayrı track
    assert out1[0].track_id != out2[0].track_id


def test_tracker_reset_clears_state():
    t = IoUTracker(iou_threshold=0.3, min_hits=1)
    t.update([((0, 0, 10, 10), "fire", 0.9)])
    t.reset()
    out = t.update([((0, 0, 10, 10), "fire", 0.9)])
    # reset sonrası ilk update → yeni id (id'ler 1'den başlamasa bile)
    assert out[0].hits == 1
