"""RobotController.decide()  — sadece karar mantığı, donanım gerektirmez.

Vision/HW/Dashboard nesneleri çağrılmadığı için RobotController'ı
__new__ ile init'siz örnekliyoruz."""
import types

import pytest

from pc_vision_controller import RobotController, State, Target


def _mk_app(area_stop=25000, area_close=10000, area_medium=3000,
            speed_close=120, speed_medium=160, speed_far=200,
            scan_speed=130, heat_threshold=60.0):
    app = RobotController.__new__(RobotController)
    app.cfg = types.SimpleNamespace(
        robot=types.SimpleNamespace(
            area_stop=area_stop, area_close=area_close, area_medium=area_medium,
            speed_close=speed_close, speed_medium=speed_medium,
            speed_far=speed_far, scan_speed=scan_speed,
            heat_threshold_c=heat_threshold,
        )
    )
    app.state = State.SEARCHING
    return app


def test_no_targets_returns_searching():
    app = _mk_app()
    cmd, spd, arm = app.decide([], heat=25, fw=640)
    assert cmd is None
    assert app.state == State.SEARCHING


def test_heat_above_threshold_triggers_heat_action():
    app = _mk_app(heat_threshold=60)
    cmd, spd, arm = app.decide([], heat=70, fw=640)
    assert cmd == "X"
    assert app.state == State.HEAT_ACTION
    assert arm == "DOWN"


def test_centered_target_far_moves_forward():
    app = _mk_app()
    t = Target(cx=320, cy=240, area=2000, priority=0.5, label="fire")
    cmd, spd, arm = app.decide([t], heat=25, fw=640)
    assert cmd == "W"
    assert spd == app.cfg.robot.speed_far  # area < area_medium
    assert app.state == State.APPROACHING


def test_target_left_third_turns_left():
    app = _mk_app()
    t = Target(cx=50, cy=240, area=5000, priority=0.5, label="fire")
    cmd, _, _ = app.decide([t], heat=25, fw=640)
    assert cmd == "A"


def test_target_right_third_turns_right():
    app = _mk_app()
    t = Target(cx=600, cy=240, area=5000, priority=0.5, label="fire")
    cmd, _, _ = app.decide([t], heat=25, fw=640)
    assert cmd == "D"


def test_very_close_target_stops():
    app = _mk_app(area_stop=10000)
    t = Target(cx=320, cy=240, area=20000, priority=0.95, label="fire")
    cmd, spd, _ = app.decide([t], heat=25, fw=640)
    assert cmd == "X"
    assert spd == 0
    assert app.state == State.TOO_CLOSE


def test_close_target_uses_close_speed():
    app = _mk_app()
    t = Target(cx=320, cy=240, area=15000, priority=0.78, label="fire")
    cmd, spd, _ = app.decide([t], heat=25, fw=640)
    assert spd == app.cfg.robot.speed_close
