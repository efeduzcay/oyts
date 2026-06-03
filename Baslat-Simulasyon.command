#!/usr/bin/env bash
# OYTS — Simülasyon (Sentetik Yangın) Demo
# Kameraya gerek yok. Sentetik yangın sahnesi üretilir, gerçekçi YOLO çıkarımı
# yapılır, robot mantığı (fuzzy + SA) çalışır.

cd "$(dirname "$0")" || exit 1

cat <<'BANNER'
============================================================
  🔥 OYTS — Otonom Yangın Tespit Sistemi
  SİMÜLASYON MODU (kamerasız)
============================================================
  • İlk açılışta kütüphaneler otomatik kurulacak (~1-3 dk).
  • Donanım gerektirmez; sentetik yangın üretilir.
  • Tarayıcı kendiliğinden açılacak.
============================================================
BANNER

./run_demo.sh synthetic
RC=$?

if [[ "$RC" -ne 0 ]]; then
  echo
  echo "Bir şeyler ters gitti (çıkış kodu: $RC)."
  echo "Hatayı görmek için yukarıyı kontrol edin."
fi

echo
echo "Bu pencereyi kapatmak için Enter'a basın..."
read -r _
