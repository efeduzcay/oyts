"""Pytest konfigürasyonu — `python/` dizinini sys.path'e ekler."""
import sys
from pathlib import Path

PYTHON_DIR = Path(__file__).resolve().parent.parent
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))
