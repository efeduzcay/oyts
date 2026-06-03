"""Frame bazlı CSV log writer. Telemetri + komut + tespit istatistiği."""
from __future__ import annotations

import csv
import os
import threading
from datetime import datetime
from pathlib import Path


class CSVLogger:
    FIELDS = [
        "ts", "frame", "state", "cmd", "spd",
        "n_targets", "primary_cx", "primary_cy", "primary_area",
        "primary_priority", "primary_label", "primary_distance_m",
        "heat_c", "voltage", "fps",
        "stable_fire", "heatmap_max",
    ]

    def __init__(self, out_dir: str | Path):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = out_dir / f"telemetry_{ts}.csv"
        self._fp = open(self.path, "w", newline="", encoding="utf-8")
        self._w = csv.DictWriter(self._fp, fieldnames=self.FIELDS)
        self._w.writeheader()
        self._fp.flush()
        self._lock = threading.Lock()

    def write(self, row: dict):
        # Eksik anahtarları boş bırak
        full = {k: row.get(k, "") for k in self.FIELDS}
        full["ts"] = full["ts"] or datetime.now().isoformat(timespec="milliseconds")
        with self._lock:
            self._w.writerow(full)
            self._fp.flush()

    def close(self):
        with self._lock:
            try:
                self._fp.close()
            except Exception:
                pass
