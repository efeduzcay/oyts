"""configs/config.yaml yükleyici. Dict'e nokta-erişim sarmalayıcısı."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml


class ConfigDict(dict):
    """`cfg.ai.conf_threshold` gibi nokta erişimine izin verir."""

    def __getattr__(self, item: str) -> Any:
        if item in self:
            v = self[item]
            return ConfigDict(v) if isinstance(v, Mapping) else v
        raise AttributeError(item)


def load_config(path: str | Path) -> ConfigDict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Konfig dosyası bulunamadı: {p}")
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return ConfigDict(data)
