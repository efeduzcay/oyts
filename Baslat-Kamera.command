#!/usr/bin/env bash
# OYTS — Kameralı Demo (çift tıkla başlat)
# Terminal'de açılır; ilk açılışta gereken paketleri kurar, kamerayı dener,
# tarayıcıyı açar. Kapatmak için Durdur.command'e çift tıkla.

cd "$(dirname "$0")" || exit 1

cat <<'BANNER'
============================================================
  🔥 OYTS — Otonom Yangın Tespit Sistemi
  KAMERA MODU
============================================================
  • İlk açılışta kütüphaneler otomatik kurulacak (~1-3 dk).
  • macOS kamera izni istendiğinde "İzin Ver" deyin.
  • Tarayıcı kendiliğinden açılacak.
============================================================
BANNER

./run_demo.sh webcam
RC=$?

if [[ "$RC" -ne 0 ]]; then
  echo
  echo "Bir şeyler ters gitti (çıkış kodu: $RC)."
  echo "Sorun çözülmediyse Durdur.command'e basıp tekrar deneyin,"
  echo "veya kamera olmadan Baslat-Simulasyon.command'i kullanın."
fi

echo
echo "Bu pencereyi kapatmak için Enter'a basın..."
read -r _
