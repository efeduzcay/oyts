"""config_loader ve csv_logger testleri."""
from pathlib import Path

import pytest

from utils.config_loader import ConfigDict, load_config
from utils.csv_logger import CSVLogger


def test_config_dict_dot_access():
    d = ConfigDict({"a": {"b": {"c": 1}}, "k": "v"})
    assert d.a.b.c == 1
    assert d["k"] == "v"
    assert d.k == "v"


def test_config_dict_attribute_error_for_missing():
    d = ConfigDict({"a": 1})
    with pytest.raises(AttributeError):
        _ = d.does_not_exist


def test_load_config_yaml(tmp_path: Path):
    p = tmp_path / "c.yaml"
    p.write_text("ai:\n  conf: 0.4\nrobot:\n  speed: 180\n")
    cfg = load_config(p)
    assert cfg.ai.conf == 0.4
    assert cfg.robot.speed == 180


def test_load_config_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nope.yaml")


def test_csv_logger_writes_row(tmp_path: Path):
    log = CSVLogger(tmp_path)
    log.write({"frame": 1, "state": "RUN", "primary_label": "fire"})
    log.write({"frame": 2, "state": "STOP"})
    log.close()
    out = log.path.read_text().splitlines()
    assert out[0].startswith("ts,frame,state,")
    assert "RUN" in out[1]
    assert "STOP" in out[2]
    # Eksik alanlar boş bırakılır
    assert out[2].count(",") == out[0].count(",")
