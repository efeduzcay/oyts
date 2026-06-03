#!/usr/bin/env bash
# OYTS — Tüm sunucuları durdur (kamerayı serbest bırakır)
cd "$(dirname "$0")" || exit 1

echo "============================================================"
echo "  OYTS Durduruluyor"
echo "============================================================"

./run_demo.sh stop

echo
echo "Tamam — bu pencereyi kapatabilirsiniz."
sleep 2
