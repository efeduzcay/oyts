"""utils.doctor preflight kontrolleri için smoke testler.

Yan etkiler dışlanır: kamera testi atlanır (test ortamı kamerasız), portlar
test sırasında rastgele uygun olduğu için doğrudan _check_port'u patch'lemek
yerine gerçek bir socket bind eder.
"""
import io
import socket
import sys
from contextlib import redirect_stdout
from unittest.mock import patch

from utils import doctor


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_check_python_returns_ok():
    status, msg = doctor._check_python()
    assert status == doctor.OK
    assert msg.startswith("Python")


def test_check_packages_lists_required():
    items = doctor._check_packages()
    names = {n for _, n, _ in items}
    # Bu paketler ortamda yüklü olmalı (requirements.txt)
    for must in ("cv2", "numpy", "flask", "yaml"):
        assert must in names


def test_check_port_free():
    port = _free_port()
    status, _ = doctor._check_port(port)
    assert status == doctor.OK


def test_check_port_busy_is_warn():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    try:
        port = s.getsockname()[1]
        status, msg = doctor._check_port(port)
        assert status == doctor.WARN
        assert str(port) in msg
    finally:
        s.close()


def test_check_model_exists():
    status, msg = doctor._check_model()
    # repo'da model dosyası var
    assert status == doctor.OK
    assert "fire_model.pt" in msg


def test_main_synthetic_skips_camera(capsys):
    # synthetic kaynak → kamera testi listede olmamalı
    rc = doctor.main(["--source", "synthetic", "--ports", str(_free_port())])
    out = capsys.readouterr().out
    assert "kamera" not in out.lower()
    assert rc in (0, 1)  # paket eksikliği gibi durumda 1 olabilir; ortamda 0 bekleniyor


def test_main_json_output_is_valid(capsys):
    import json
    rc = doctor.main(["--source", "synthetic", "--ports", str(_free_port()),
                      "--json"])
    out = capsys.readouterr().out
    data = json.loads(out)
    assert isinstance(data, list)
    assert all("status" in item and "check" in item for item in data)
