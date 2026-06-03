"""Flask backend endpoint'leri için entegrasyon testleri.

VisionService'i fake'liyoruz — gerçek YOLO yükleme, kamera açma yok.
"""
import logging
import threading
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def client():
    """web_app.app test client + fake service."""
    import web_app

    # Fake service: gerçek YOLO/kameraya gerek yok
    class _FakeCfg:
        class mode:
            webcam_index = 0
            simulation = True

    class _FakeService:
        source = "synthetic"
        running = False
        cfg = _FakeCfg()
        def get_state(self): return {"running": False}

    web_app.service = _FakeService()
    return web_app.app.test_client()


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_cameras_returns_list(client):
    # _probe_webcam'i mock — gerçek donanım çağrısı olmasın
    fake_results = [
        {"index": 0, "available": True,  "width": 1280, "height": 720},
        {"index": 1, "available": False, "width": 0,    "height": 0},
        {"index": 2, "available": True,  "width": 640,  "height": 480},
    ]
    call_iter = iter(fake_results)
    with patch("web_app._probe_webcam",
               side_effect=lambda i: next(call_iter)):
        r = client.get("/cameras?max=3")
    assert r.status_code == 200
    body = r.get_json()
    assert len(body["cameras"]) == 3
    assert body["cameras"][0]["available"] is True
    assert body["cameras"][1]["available"] is False
    assert body["cameras"][0]["in_use"] is False
    assert body["active_source"] == "synthetic"


def test_cameras_marks_in_use_when_webcam_active(client):
    """Webcam çalışıyorsa o index probe edilmez, in_use=True işaretlenir."""
    import web_app
    web_app.service.source = "webcam"
    web_app.service.running = True
    web_app.service.cfg.mode.webcam_index = 1

    probed = []
    def _spy(i):
        probed.append(i)
        return {"index": i, "available": False, "width": 0, "height": 0}

    with patch("web_app._probe_webcam", side_effect=_spy):
        r = client.get("/cameras?max=3")
    body = r.get_json()
    # Index 1 atlandı (kilit), 0 ve 2 probe edildi
    assert 1 not in probed
    assert sorted(probed) == [0, 2]
    # Index 1 in_use=True dönmüş olmalı
    by_idx = {c["index"]: c for c in body["cameras"]}
    assert by_idx[1]["in_use"] is True
    assert by_idx[1]["available"] is True
    assert by_idx[0]["in_use"] is False


def test_cameras_default_max(client):
    """max query verilmezse default 4 kamera probe eder."""
    counter = {"n": 0}
    def _spy(i):
        counter["n"] += 1
        return {"index": i, "available": False, "width": 0, "height": 0}
    with patch("web_app._probe_webcam", side_effect=_spy):
        r = client.get("/cameras")
    assert r.status_code == 200
    assert counter["n"] == 4


def test_cameras_max_clamped_to_at_least_1(client):
    """max=0 veya negatif gelirse en az 1 index probe edilmeli."""
    counter = {"n": 0}
    def _spy(i):
        counter["n"] += 1
        return {"index": i, "available": False, "width": 0, "height": 0}
    with patch("web_app._probe_webcam", side_effect=_spy):
        r = client.get("/cameras?max=0")
    assert r.status_code == 200
    assert counter["n"] == 1


# _explain_open_failure
def test_explain_failure_messages_are_turkish():
    from web_app import VisionService
    assert "Webcam" in VisionService._explain_open_failure("webcam")
    assert "ESP32" in VisionService._explain_open_failure("esp32")
    assert "sim" in VisionService._explain_open_failure("synthetic").lower()
    # Bilinmeyen kaynak için generic fallback
    assert "weird" in VisionService._explain_open_failure("weird")


# stop() idempotency
def _make_mock_service():
    """VisionService.__init__'i atlayıp stop() davranışını izole test et.

    Gerçek init YOLO + HardwareLink + kamera açar → testte çok pahalı.
    """
    from web_app import VisionService
    svc = VisionService.__new__(VisionService)
    svc.running = False
    svc._stop_lock = threading.Lock()
    svc.lock = threading.Lock()
    svc._thread = None
    svc.cap = None
    svc.state_snapshot = {"running": False}
    svc.logger = logging.getLogger("test-stop")
    svc.logger.handlers = [logging.NullHandler()]
    svc.hw = MagicMock()
    return svc


def test_stop_when_never_started_is_noop():
    """stop() running=False'da minimum iş yapar, exception fırlatmaz."""
    svc = _make_mock_service()
    svc.stop()  # patlamamalı
    # hw.send hala çağrılır (motor durdurma + alarm söndürme her ihtimal için)
    assert svc.hw.send.call_count == 2  # X + N


def test_stop_called_twice_is_idempotent():
    """İki ardışık stop() patlamamalı; ikincisi was_running=False ile sessiz geçer."""
    svc = _make_mock_service()
    svc.running = True
    svc.cap = MagicMock()
    svc.stop()
    # İkinci çağrı — cap None, running False, yine de çalışmalı
    svc.stop()
    # Cap release edildi sadece bir kez (ilk stop'ta), ikincide cap None'du
    assert svc.cap is None


def test_stop_releases_camera_handle():
    svc = _make_mock_service()
    svc.running = True
    cap_mock = MagicMock()
    svc.cap = cap_mock
    svc.stop()
    cap_mock.release.assert_called_once()
    assert svc.cap is None
    assert svc.running is False
    assert svc.state_snapshot["running"] is False


def test_empty_state_includes_source_error_field():
    """UI bu alanı bekliyor — hata yoksa boş string."""
    svc = _make_mock_service()
    # _empty_state() cfg'ye dokunuyor; minimal mock ekleyelim
    svc.cfg = MagicMock()
    svc.cfg.ai.conf_threshold = 0.25
    svc.cfg.ai.imgsz = 640
    svc.source = "webcam"
    svc.source_error = ""
    state = svc._empty_state()
    assert "source_error" in state
    assert state["source_error"] == ""


def test_loop_failure_updates_snapshot_source():
    """Webcam fail edince state_snapshot.source eski kaynağa düşmemeli —
    aktif (fail edilen) kaynağı göstermeli ki UI doğru hatayı bağlasın."""
    svc = _make_mock_service()
    svc.cfg = MagicMock()
    svc.cfg.ai.conf_threshold = 0.25
    svc.cfg.ai.imgsz = 640
    svc.source = "webcam"
    svc.source_error = ""
    # state_snapshot eski "synthetic" kaynağı gösteriyor
    svc.state_snapshot = {"source": "synthetic", "running": True}
    # _open_source None döndürsün → fail path
    svc._open_source = lambda: None
    svc._loop()
    assert svc.state_snapshot["source"] == "webcam"
    assert svc.state_snapshot["running"] is False
    assert "Webcam" in svc.state_snapshot["source_error"]


def test_set_source_auto_starts_after_previous_error():
    """Kaynak A fail edip durduktan sonra B'ye geçiş otomatik start etmeli.
    Kullanıcı 'şu kaynağı dene' diyor — manual /start çağrısı beklemek kötü UX."""
    svc = _make_mock_service()
    svc.cfg = MagicMock()
    svc.cfg.__setitem__ = MagicMock()  # cfg["mode"]["..."] yazımı için
    svc.cfg.__getitem__ = MagicMock(return_value=MagicMock())
    svc.cfg.__contains__ = MagicMock(return_value=True)
    svc.source = "webcam"
    svc.source_error = "Webcam açılamadı..."  # önceki fail durumu
    svc.running = False                       # döngü durmuş
    svc.vision = MagicMock()
    svc._heatmap = None
    svc.VALID_SOURCES = ("webcam", "esp32", "synthetic")

    started = {"called": False}
    svc.start = lambda: started.__setitem__("called", True)
    svc.stop = MagicMock()

    ok = svc.set_source("synthetic")
    assert ok is True
    assert svc.source == "synthetic"
    assert started["called"] is True, "fail sonrası set_source auto-start etmeli"


def test_set_source_no_autostart_if_clean_stopped():
    """Temiz durmuş (source_error=='') bir servis için /source auto-start ETMEMELİ —
    kullanıcı bilinçli durdurmuş olabilir."""
    svc = _make_mock_service()
    svc.cfg = MagicMock()
    svc.cfg.__setitem__ = MagicMock()
    svc.cfg.__getitem__ = MagicMock(return_value=MagicMock())
    svc.cfg.__contains__ = MagicMock(return_value=True)
    svc.source = "synthetic"
    svc.source_error = ""
    svc.running = False
    svc.vision = MagicMock()
    svc._heatmap = None
    svc.VALID_SOURCES = ("webcam", "esp32", "synthetic")

    started = {"called": False}
    svc.start = lambda: started.__setitem__("called", True)
    svc.stop = MagicMock()

    svc.set_source("webcam")
    assert started["called"] is False, "temiz durmuş servis auto-start etmemeli"
