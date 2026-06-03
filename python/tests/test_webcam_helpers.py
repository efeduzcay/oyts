"""pc_vision_controller._webcam_backend + _open_webcam_with_fallback testleri.

cv2.VideoCapture'ı mock'luyoruz — gerçek kamera/sürücü gerekmiyor.
"""
import logging
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import cv2

import pc_vision_controller as pvc


@pytest.fixture
def silent_logger():
    lg = logging.getLogger("test-webcam")
    lg.handlers = [logging.NullHandler()]
    lg.propagate = False
    return lg


# _webcam_backend platform dispatch
def test_backend_windows():
    with patch.object(pvc, "_IS_WINDOWS", True), \
         patch.object(pvc, "_IS_MACOS", False):
        assert pvc._webcam_backend() == cv2.CAP_DSHOW


def test_backend_macos():
    with patch.object(pvc, "_IS_WINDOWS", False), \
         patch.object(pvc, "_IS_MACOS", True):
        assert pvc._webcam_backend() == cv2.CAP_AVFOUNDATION


def test_backend_linux_fallback():
    with patch.object(pvc, "_IS_WINDOWS", False), \
         patch.object(pvc, "_IS_MACOS", False):
        assert pvc._webcam_backend() == cv2.CAP_V4L2


# _open_webcam_with_fallback
def _mk_cap_mock(isOpened=True, frames=None):
    """Sahte VideoCapture: read() çağrılarında frames listesini tüketir,
    bitince (False, None) döner."""
    if frames is None:
        frames = [(True, np.zeros((480, 640, 3), dtype=np.uint8))]
    cap = MagicMock()
    cap.isOpened.return_value = isOpened
    cap.read.side_effect = list(frames) + [(False, None)] * 50
    cap.get.side_effect = lambda prop: {
        cv2.CAP_PROP_FRAME_WIDTH: 1280.0,
        cv2.CAP_PROP_FRAME_HEIGHT: 720.0,
        cv2.CAP_PROP_FPS: 30.0,
    }.get(prop, 0.0)
    cap.set.return_value = True
    return cap


def test_open_webcam_success(silent_logger):
    """Mutlu yol: backend ile açılır, ilk read warmup'ı geçer."""
    good_cap = _mk_cap_mock(isOpened=True)
    with patch("pc_vision_controller.cv2.VideoCapture", return_value=good_cap):
        cap = pvc._open_webcam_with_fallback(0, silent_logger)
    assert cap is good_cap
    # 1280x720 @ 30 fps konfigürasyonu uygulanmış olmalı
    set_calls = {c.args[0]: c.args[1] for c in good_cap.set.call_args_list
                 if len(c.args) == 2}
    assert set_calls.get(cv2.CAP_PROP_FRAME_WIDTH) == 1280
    assert set_calls.get(cv2.CAP_PROP_FRAME_HEIGHT) == 720
    assert set_calls.get(cv2.CAP_PROP_FPS) == 30


def test_open_webcam_warmup_returns_none_when_no_frames(silent_logger):
    """Backend açılır ama 10 deneme boyunca kare gelmez → None döner, release çağrılır."""
    dead_cap = _mk_cap_mock(isOpened=True, frames=[(False, None)] * 20)
    with patch("pc_vision_controller.cv2.VideoCapture", return_value=dead_cap):
        cap = pvc._open_webcam_with_fallback(0, silent_logger)
    assert cap is None
    dead_cap.release.assert_called()


def test_open_webcam_backend_fail_then_default_succeeds(silent_logger):
    """İlk backend fail eder, default backend başarılı olur."""
    fail_cap = _mk_cap_mock(isOpened=False)
    good_cap = _mk_cap_mock(isOpened=True)
    # VideoCapture iki kez çağrılır: 1) backend ile fail, 2) default ile success
    call_sequence = [fail_cap, good_cap]
    with patch("pc_vision_controller.cv2.VideoCapture",
               side_effect=lambda *a, **kw: call_sequence.pop(0)):
        cap = pvc._open_webcam_with_fallback(0, silent_logger)
    assert cap is good_cap
    fail_cap.release.assert_called()


def test_open_webcam_both_fail_returns_none(silent_logger):
    """Hem backend hem default fail → None, hata log'lanır (kullanıcıya rehber)."""
    fail1 = _mk_cap_mock(isOpened=False)
    fail2 = _mk_cap_mock(isOpened=False)
    call_sequence = [fail1, fail2]
    captured = []
    silent_logger.error = lambda msg, *a, **kw: captured.append(msg % a if a else msg)
    with patch("pc_vision_controller.cv2.VideoCapture",
               side_effect=lambda *a, **kw: call_sequence.pop(0)):
        cap = pvc._open_webcam_with_fallback(0, silent_logger)
    assert cap is None
    # Açıklayıcı Türkçe hata bekliyoruz
    assert any("WEBCAM AÇILAMADI" in m for m in captured)


# _probe_webcam — hızlı index taraması
def test_probe_webcam_open():
    good = _mk_cap_mock(isOpened=True)
    with patch("pc_vision_controller.cv2.VideoCapture", return_value=good):
        info = pvc._probe_webcam(0)
    assert info["index"] == 0
    assert info["available"] is True
    assert info["width"] == 1280
    assert info["height"] == 720
    # Test sonunda release çağrılmalı — kamera kilidi tutmasın
    good.release.assert_called()


def test_probe_webcam_not_open():
    bad = _mk_cap_mock(isOpened=False)
    with patch("pc_vision_controller.cv2.VideoCapture", return_value=bad):
        info = pvc._probe_webcam(2)
    assert info["index"] == 2
    assert info["available"] is False
    assert info["width"] == 0
    assert info["height"] == 0


def test_list_webcams_returns_indices():
    """list_webcams 0..max-1 aralığını tarar; available olanları döner."""
    cap0 = _mk_cap_mock(isOpened=True)
    cap1 = _mk_cap_mock(isOpened=False)
    cap2 = _mk_cap_mock(isOpened=True)
    sequence = iter([cap0, cap1, cap2])
    with patch("pc_vision_controller.cv2.VideoCapture",
               side_effect=lambda *a, **kw: next(sequence)):
        items = pvc.list_webcams(max_index=3)
    assert len(items) == 3
    assert items[0]["available"] is True
    assert items[1]["available"] is False
    assert items[2]["available"] is True


# webcam_failure_hint — platforma göre rehber
def test_failure_hint_macos_mentions_privacy():
    with patch.object(pvc, "_IS_MACOS", True), \
         patch.object(pvc, "_IS_WINDOWS", False):
        hint = pvc.webcam_failure_hint(0)
    assert "macOS" in hint
    assert "Privacy" in hint or "izin" in hint.lower()
    assert "Windows" not in hint


def test_failure_hint_windows_mentions_settings():
    with patch.object(pvc, "_IS_MACOS", False), \
         patch.object(pvc, "_IS_WINDOWS", True):
        hint = pvc.webcam_failure_hint(0)
    assert "Windows" in hint or "Ayarlar" in hint
    assert "macOS" not in hint


def test_failure_hint_linux_mentions_v4l2():
    with patch.object(pvc, "_IS_MACOS", False), \
         patch.object(pvc, "_IS_WINDOWS", False):
        hint = pvc.webcam_failure_hint(0)
    assert "V4L2" in hint or "video" in hint.lower()


def test_failure_hint_includes_index():
    with patch.object(pvc, "_IS_MACOS", True), \
         patch.object(pvc, "_IS_WINDOWS", False):
        assert "index=2" in pvc.webcam_failure_hint(2)


# _open_esp32_stream — timeout + FFMPEG backend
def test_open_esp32_success_sets_timeouts(silent_logger):
    """Açma başarılı → timeout property'leri uygulanmış olmalı."""
    cap = _mk_cap_mock(isOpened=True)
    with patch("pc_vision_controller.cv2.VideoCapture", return_value=cap) as cv_mock:
        out = pvc._open_esp32_stream("http://192.168.1.25/stream",
                                     silent_logger, timeout_sec=5.0)
    assert out is cap
    # FFMPEG backend ile çağırdık mı
    args, kwargs = cv_mock.call_args
    assert args[1] == cv2.CAP_FFMPEG
    # Open + Read timeout 5000ms set edildi mi
    set_props = {c.args[0]: c.args[1] for c in cap.set.call_args_list
                 if len(c.args) == 2}
    assert set_props.get(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC) == 5000
    assert set_props.get(cv2.CAP_PROP_READ_TIMEOUT_MSEC) == 5000


def test_open_esp32_fails_returns_none(silent_logger):
    """isOpened False → None döner ve cap release edilir."""
    cap = _mk_cap_mock(isOpened=False)
    with patch("pc_vision_controller.cv2.VideoCapture", return_value=cap):
        out = pvc._open_esp32_stream("http://dead.invalid/stream",
                                     silent_logger, timeout_sec=2.0)
    assert out is None
    cap.release.assert_called()


def test_open_esp32_timeout_set_failure_is_swallowed(silent_logger):
    """Bazı driver'lar bu property'leri set edemez — patlamamalı."""
    cap = _mk_cap_mock(isOpened=True)
    cap.set.side_effect = Exception("driver does not support property")
    with patch("pc_vision_controller.cv2.VideoCapture", return_value=cap):
        out = pvc._open_esp32_stream("http://ok/stream",
                                     silent_logger, timeout_sec=1.0)
    # Exception içeri sızmadı, cap döndü
    assert out is cap
