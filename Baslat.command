#!/usr/bin/env bash
# OYTS Launcher — tek pencere arayüzü (çift tıkla)
# Tkinter penceresi açılır; oradan webcam/simülasyon/durdur seç.
cd "$(dirname "$0")" || exit 1

# Python detection: aktif venv → python3 → python → /usr/bin/python3
PY=""
if [[ -n "${VIRTUAL_ENV:-}" && -x "$VIRTUAL_ENV/bin/python" ]]; then
  PY="$VIRTUAL_ENV/bin/python"
else
  for c in python3 python /usr/bin/python3; do
    if command -v "$c" >/dev/null 2>&1; then
      PY="$(command -v "$c")"
      break
    fi
  done
fi

if [[ -z "$PY" ]]; then
  cat <<'MSG'
============================================================
  Python bulunamadı.
  Lütfen Python 3.9 veya üzeri kurun:
  https://www.python.org/downloads/
============================================================
MSG
  echo "Enter ile kapat..."
  read -r _
  exit 1
fi

# Tkinter kontrolü (bazı dağıtımlarda eksik olabilir)
if ! "$PY" -c "import tkinter" >/dev/null 2>&1; then
  echo "Tkinter bulunamadı. macOS Python'una tkinter dahildir;"
  echo "Python'u python.org'dan resmi sürümle kurun (Homebrew bazen eksik)."
  echo "Enter ile kapat..."
  read -r _
  exit 1
fi

exec "$PY" python/launcher.py
