"""Bulanık mantık üyelik + Simulated Annealing testleri.

VisionProcessor.model yüklemesini bypass etmek için _trap, fuzzy_priority,
sa_order metotlarını izole test ediyoruz (sahte cfg ile).
"""
import math
import random
import types

import pytest


def _make_processor_skel():
    """VisionProcessor metotlarını gerçek init'siz kullanabilmek için
    minimum cfg ile bir nesne kurar."""
    from pc_vision_controller import VisionProcessor

    # init'i atla, sadece gerekli attribute'ları setle
    vp = VisionProcessor.__new__(VisionProcessor)
    vp._fuzzy_sets = {
        "SMALL":  [0, 0, 2000, 3000],
        "MEDIUM": [2000, 3000, 10000, 12000],
        "LARGE":  [10000, 12000, 24000, 28000],
        "HUGE":   [24000, 28000, 60000, 60000],
    }
    vp._fuzzy_out = {"SMALL": 0.15, "MEDIUM": 0.45, "LARGE": 0.78, "HUGE": 1.00}
    vp.cfg = types.SimpleNamespace(
        sa=types.SimpleNamespace(
            t_start=5000.0, t_end=1.0, alpha=0.99, max_iter=500),
    )
    return vp


def test_trap_outside_returns_zero():
    from pc_vision_controller import VisionProcessor as VP
    assert VP._trap(-10, [0, 1, 2, 3]) == 0.0
    assert VP._trap(100, [0, 1, 2, 3]) == 0.0


def test_trap_plateau_is_one():
    from pc_vision_controller import VisionProcessor as VP
    assert VP._trap(1.5, [0, 1, 2, 3]) == 1.0
    assert VP._trap(2.0, [0, 1, 2, 3]) == 1.0


def test_trap_rising_falling_edges():
    from pc_vision_controller import VisionProcessor as VP
    assert VP._trap(0.5, [0, 1, 2, 3]) == pytest.approx(0.5)
    assert VP._trap(2.5, [0, 1, 2, 3]) == pytest.approx(0.5)


def test_fuzzy_priority_small_area_low():
    vp = _make_processor_skel()
    p = vp.fuzzy_priority(500)
    assert p == pytest.approx(0.15, abs=1e-3)


def test_fuzzy_priority_huge_area_max():
    vp = _make_processor_skel()
    p = vp.fuzzy_priority(40000)
    assert p == pytest.approx(1.0, abs=1e-3)


def test_fuzzy_priority_intermediate_between():
    vp = _make_processor_skel()
    p = vp.fuzzy_priority(6000)   # MEDIUM ortası
    assert 0.4 < p < 0.55


def test_sa_order_single_target_trivial():
    from pc_vision_controller import Target
    vp = _make_processor_skel()
    t = Target(cx=100, cy=100, area=5000, priority=0.5, label="fire")
    assert vp.sa_order([t], robot_pos=(0, 0)) == [0]


def test_sa_order_picks_closest_first():
    from pc_vision_controller import Target
    random.seed(42)
    vp = _make_processor_skel()
    # 3 hedef: yakın, orta, uzak
    near = Target(cx=10,  cy=10,  area=5000, priority=0.4, label="fire")
    mid  = Target(cx=100, cy=100, area=5000, priority=0.5, label="fire")
    far  = Target(cx=500, cy=500, area=5000, priority=0.6, label="fire")
    order = vp.sa_order([far, mid, near], robot_pos=(0, 0))
    # En küçük toplam yol: near→mid→far (orig idx: 2,1,0)
    assert order[0] == 2
