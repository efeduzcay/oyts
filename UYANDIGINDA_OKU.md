# 🌅 Uyandığında Buraya Bak

Sen uyurken token bitene kadar otonom çalıştım. **Her şey yeşil.**

## TL;DR

```bash
cd ~/Desktop/robot-3.0.0
./run_demo.sh
```

Tarayıcı otomatik açılır, **sentetik yangın tespit edilir**, manuel sürüş çalışır.

---

## Bu Gece Ne Yapıldı?

### 1. **YOLOv8 Fine-tune Tamamlandı** ✅
- 5000 frame sentetik dataset üretildi
- Backbone donduruldu (freeze=10), lr0=1e-4, ~3 saat MPS eğitim
- **Sonuç (val):** Precision 0.92, Recall 0.89, **mAP50 0.93**, mAP50-95 0.75
- Yeni model: `python/fire_model_v311_mixed.pt`
- Eski model yedeği: `python/fire_model_v3_real.pt` (geri dönüş için)

### 2. **Doğrulama Karşılaştırması**

Sentetik sahne, conf eşiği 0.40:
| Model | Tespit |
|---|---|
| Eski (real-only) | **0** ❌ |
| Yeni (mixed) | **5** ✅ — fire conf 0.92/0.88/0.88 |

15/15 frame'de tespit, end-to-end CSV log doluyor, FSM `APPROACHING` durumuna geçip motor komutu üretiyor.

### 3. **Config Otomatik Geçti**
- `config.yaml` → `model_path: fire_model_v311_mixed.pt`
- `sim.passthrough_detections: false` (artık ihtiyaç yok, model gerçekten görüyor)
- `ai.hsv_required: false` (sentetik için kapalı, gerçek kamerada açabilirsin)
- Eski davranışa dönmek için config.yaml'da modeli ve passthrough'u değiştir

### 4. **Yeni Demo Launcher**
`./run_demo.sh [synthetic|webcam|esp32|stop]` — backend + frontend + tarayıcı tek komut.

### 5. **UI v3.1.1 Polish**
- Hero altında **versiyon rozetleri**: v3.1.1 / model adı / mAP50 0.93 / mixed
- Sistem Durumu: **Mesafe (m)** + **Risk Yoğunluğu (%)** + heatmap gradient bar
- "Yangın Tespit Edildi!" pill artık **flash animasyonu** yapıyor (dikkat çekici)
- Mesafe < 2m → **turuncu/kırmızı** renk (yaklaşma uyarısı)
- Model adı dinamik (config değişirse rozet de değişir)

### 6. **Yeni Dokümantasyon**
- [CHANGELOG.md](CHANGELOG.md) — tüm sürüm geçmişi
- [DEMO.md](DEMO.md) — 5 dakikada canlı demo rehberi + jüri sunum senaryosu
- README v3.1.1'e güncellendi, hızlı başlangıç eklendi
- `web/screenshots/demo_synthetic_{1,2,3}.jpg` — örnek demo çıktıları

### 7. **Test Durumu**
```
44 passed, 1 warning in 2.78s
```
Tüm pytest geçer. Yeni özellik eklerken bu sayı korunmalı.

---

## Hızlı Doğrulama (Sen Test Et)

```bash
cd ~/Desktop/robot-3.0.0

# 1. Testler
cd python && /usr/bin/python3 -m pytest tests/ -q   # 44/44 beklerim

# 2. Sentetik headless
/usr/bin/python3 pc_vision_controller.py --max-frames 10 --headless --sim synthetic
# Beklenen: "max_frames=10 ulaşıldı, kapanıyor" ve kayitlar/ altında CSV

# 3. Tam demo
cd .. && ./run_demo.sh
# Tarayıcıda "Yangın Tespit Edildi!" pulse + bbox + heatmap
```

---

## ESP32-CAM Sorunu (Uyandığında Devam)

Bunu henüz çözmedim — sen demin upload hatası yaşıyordun. Bana **tam hata mesajı** ver:

```
Arduino IDE → Tools → Serial Monitor (baud: 115200)
File → Open → arduino/esp32_cam_stream/esp32_cam_stream.ino
Upload (Sketch → Upload)
Çıkan kırmızı hatanın son 10 satırını kopyala
```

En yaygın 3 neden ve çözümleri DEMO.md'nin sonunda var. Detaylı tarama ile birlikte:

1. **GPIO0-GND BOOT modu** (en sık)
2. **Brownout / yetersiz güç** — kamera 300mA çekiyor, USB-TTL 500mA veriyorsa sınırda
3. **Yanlış board/port/baud** — `AI Thinker ESP32-CAM`, 115200 baud

Sen `[X] Kod yüklenmiyor` dedin, gerisi belirsiz kaldı. Hata mesajı + kullandığın programlayıcı türü (CP2102 mı, ESP32-CAM-MB tabanı mı?) gönder.

---

## Donanım Montaj Rehberi (Hazır)

Önceki cevabımda **adım adım montaj** verdim — şasi, motorlar, L298N, Mega bağlantıları, voltaj bölücü, ESP32-CAM bağımsız bağlantısı, güç dağıtımı, test sırası. LiPo'yu **EN SON** bağla, güvenlik kuralları en üstte.

---

## Şu An Çalışan / Bitmiş

| Sistem | Durum |
|---|---|
| YOLOv8 sentetik tespit | ✅ mAP50 0.93 |
| Heatmap overlay | ✅ |
| Distance estimasyonu | ✅ CSV'de loglanıyor |
| Webhook bildirim | ✅ (URL eklersen aktif) |
| Tracker grace frames | ✅ FSM titremesi sıfır |
| Manuel sürüş (klavye + UI) | ✅ |
| Sim modu end-to-end | ✅ 15/15 frame |
| 44 pytest | ✅ |
| run_demo.sh tek komut | ✅ |
| Dokümantasyon | ✅ README + CHANGELOG + DEMO |
| ESP32-CAM upload sorunu | ❓ Hata mesajı bekliyor |
| Gerçek donanım entegrasyonu | ❓ Bağlanmamış |

---

## Önerilen Sırada Devam

1. **Sabahta ilk iş**: `./run_demo.sh` ile sistemi gör, gözünle doğrula
2. ESP32 hata mesajını gönder, beraber çözelim
3. Mega'yı USB ile bağla, `mega_robot_l298n.ino` yükle, Serial Monitor'de `READY` mesajını bekle
4. Voltaj bölücüyü breadboardta kur (30k + 10k), multimetre ile test et
5. Motor + L298N bağlantısı, **LiPo EN SON**
6. Gerçek kameralı testte `ai.hsv_required: true` yaparak çakmak/mum testi
7. Donanım testi başarılı olursa: `python pc_vision_controller.py --no-sim`

---

İyi sabahlar kanka 🌅 Sistem hazır, jüri için her şey gösterilebilir durumda.
