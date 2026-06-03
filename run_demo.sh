#!/usr/bin/env bash
# ============================================================
#  OYTS — Tek komutla canlı demo (macOS / Linux)
# ============================================================
#  Backend (Flask + YOLO) ve frontend (static live.html)
#  sunucularını başlatır, tarayıcıyı açar.
#
#  Kullanım:
#      ./run_demo.sh                 # webcam yok → synthetic
#      ./run_demo.sh esp32           # ESP32-CAM (Wi-Fi)
#      ./run_demo.sh webcam          # Mac/Linux webcam
#      ./run_demo.sh doctor          # sadece preflight (başlatma)
#      ./run_demo.sh stop            # tüm sunucuları durdur
# ============================================================
set -e

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON_DIR="$REPO_ROOT/python"
WEB_DIR="$REPO_ROOT/web"
LOG_DIR="/tmp/oyts_demo"
mkdir -p "$LOG_DIR"

BACKEND_PORT=5050
FRONTEND_PORT=8765
SOURCE="${1:-synthetic}"

# ─── Python tespiti ─────────────────────────────────────────
# Sırayla: aktif venv → python3 → python → /usr/bin/python3
detect_python() {
  if [[ -n "${VIRTUAL_ENV:-}" && -x "$VIRTUAL_ENV/bin/python" ]]; then
    echo "$VIRTUAL_ENV/bin/python"; return
  fi
  for c in python3 python /usr/bin/python3; do
    if command -v "$c" >/dev/null 2>&1; then
      echo "$(command -v "$c")"; return
    fi
  done
  echo ""
}

PY="$(detect_python)"
if [[ -z "$PY" ]]; then
  echo "✗ Python bulunamadı. Python 3.9+ kurun: https://www.python.org/downloads/"
  exit 1
fi

case "$SOURCE" in
  stop)
    echo "▶ Sunucular durduruluyor..."
    pkill -f "python.*web_app.py" 2>/dev/null && echo "  • backend stopped" || true
    pkill -f "python.*serve.py"   2>/dev/null && echo "  • frontend stopped" || true
    exit 0
    ;;
  doctor)
    cd "$PYTHON_DIR"
    exec "$PY" -m utils.doctor --source any
    ;;
  webcam|esp32|synthetic) ;;
  *)
    echo "Hata: kaynak '$SOURCE' geçersiz (webcam|esp32|synthetic|doctor|stop)"
    exit 1
    ;;
esac

# ─── İlk açılış kurulumu (idempotent: paketler + model) ───
echo "▶ Ortam kontrolü..."
(
  cd "$PYTHON_DIR"
  "$PY" -m utils.setup_env --quiet
) || SETUP_RC=$?
SETUP_RC="${SETUP_RC:-0}"

if [[ "$SETUP_RC" -ne 0 ]]; then
  echo
  echo "✗ Kurulum tamamlanamadı. İnternet bağlantısını kontrol edip tekrar deneyin."
  echo "  Manuel: $PY -m pip install -r $PYTHON_DIR/requirements.txt"
  exit 1
fi

# ─── Preflight (webcam moduna özel kamera testi dahil) ─────
echo "▶ Preflight kontrolleri..."
(
  cd "$PYTHON_DIR"
  "$PY" -m utils.doctor --source "$SOURCE" --ports "$BACKEND_PORT,$FRONTEND_PORT" --open-settings
) || PREFLIGHT_RC=$?
PREFLIGHT_RC="${PREFLIGHT_RC:-0}"

if [[ "$PREFLIGHT_RC" -ne 0 ]]; then
  echo
  echo "✗ Preflight başarısız. Yukarıdaki hatayı düzeltip tekrar deneyin."
  if [[ "$SOURCE" == "webcam" ]]; then
    echo "  İpucu: kamera olmadan denemek için → ./run_demo.sh synthetic"
  fi
  exit 1
fi

# ─── Eski instansları temizle ──────────────────────────────
pkill -f "python.*web_app.py" 2>/dev/null || true
pkill -f "python.*serve.py"   2>/dev/null || true
sleep 1

# Kaynağa göre config seç:
# - synthetic → varsayılan config.yaml (mixed model, HSV kapalı)
# - webcam/esp32 → config_webcam.yaml (real model, HSV açık)
case "$SOURCE" in
  webcam|esp32) CFG_ARG="--config $PYTHON_DIR/configs/config_webcam.yaml" ;;
  *)            CFG_ARG="" ;;
esac

echo "▶ Backend başlıyor (port $BACKEND_PORT, source=$SOURCE)..."
nohup "$PY" "$PYTHON_DIR/web_app.py" \
    $CFG_ARG --port "$BACKEND_PORT" --source "$SOURCE" --autostart \
    > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "  • PID $BACKEND_PID  → log: $LOG_DIR/backend.log"

echo "▶ Frontend başlıyor (port $FRONTEND_PORT)..."
nohup "$PY" "$WEB_DIR/serve.py" "$FRONTEND_PORT" \
    > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "  • PID $FRONTEND_PID  → log: $LOG_DIR/frontend.log"

# Backend hazır olana kadar bekle (YOLO yüklemesi ~10-20 sn)
echo -n "▶ Backend hazır olması bekleniyor"
READY=0
for i in {1..40}; do
  if curl -sf "http://127.0.0.1:$BACKEND_PORT/healthz" > /dev/null 2>&1; then
    echo "  ✓ ($i sn)"
    READY=1
    break
  fi
  echo -n "."
  sleep 1
done

if [[ "$READY" -ne 1 ]]; then
  echo
  echo "✗ Backend 40 sn içinde hazır olmadı."
  echo "  Log: $LOG_DIR/backend.log (son 20 satır):"
  tail -20 "$LOG_DIR/backend.log" | sed 's/^/    /'
  if [[ "$SOURCE" == "webcam" ]]; then
    echo
    echo "  Kamera olmadan denemek için: ./run_demo.sh synthetic"
  fi
  exit 1
fi

URL="http://127.0.0.1:$FRONTEND_PORT/live.html"

echo
echo "============================================================"
echo " 🔥 OYTS Demo Hazır"
echo "============================================================"
echo "  Frontend : $URL"
echo "  Backend  : http://127.0.0.1:$BACKEND_PORT  (source=$SOURCE)"
echo "  Loglar   : $LOG_DIR/"
echo
echo "  Durdurmak için:  ./run_demo.sh stop"
echo "============================================================"

# macOS'ta tarayıcıyı aç; Linux xdg-open varsa o
if command -v open >/dev/null 2>&1; then
  open "$URL"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL" >/dev/null 2>&1 &
fi
