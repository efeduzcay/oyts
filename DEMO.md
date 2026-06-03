# 🔥 OYTS — Hızlı Demo Rehberi

**5 dakikada** sıfırdan canlı demoya.

---

## 1. Tek Komutla Demo

```bash
./run_demo.sh
```

Bu kadar. Şu olur:
1. Flask backend başlar (port **5050**, YOLOv8 + sentetik sahne)
2. Statik web sunucusu başlar (port **8765**)
3. Tarayıcıda `http://127.0.0.1:8765/live.html` açılır
4. **Yangınlar otomatik tespit edilir** — kırmızı bbox + FIRE etiketi + ısı haritası overlay
5. Manuel sürüş paneli + WASD klavye desteği aktif

### Durdurmak için
```bash
./run_demo.sh stop
```

---

## 2. Farklı Kaynaklar

```bash
./run_demo.sh synthetic    # Sentetik sahne (varsayılan, donanım gerektirmez)
./run_demo.sh webcam       # Mac webcam → çakmak/mum yakıp test
./run_demo.sh esp32        # ESP32-CAM Wi-Fi stream
```

ESP32 için önce `python/configs/config.yaml` içindeki `connection.stream_url` IP'sini güncelle.

---

## 3. Klavye Kısayolları (live.html)

| Tuş | Eylem |
|---|---|
| **W / A / S / D** | İleri / Sol / Sağ / Geri |
| **X** | Dur |
| **K / L** | Kol aşağı / yukarı |
| Hız slider | 60-255 arası anlık ayar |

---

## 4. Görsel Demo'da Neyi Vurgula

### Sol panel — Sistem Durumu
- **Yangın Tespiti** kırmızı pill → "Yangın Tespit Edildi!"
- **FPS** yeşil rozet (10+ FPS)
- **Stable Hedef: 2 / 2** — tracker tutarlılığı
- **Max Confidence: 0.85+** (eşik üstü)
- **Öncelik (P)** — fuzzy logic çıktısı
- **Mesafe (m)** — mono-kamera tahmini
- **Risk Yoğunluğu (%)** — heatmap pik değeri

### Orta — Canlı Kamera
- Çoklu **bbox** (kırmızı=primary, turuncu=secondary)
- **Heatmap halo** alev etrafında turuncu gradient
- "SYNTHETIC" / "WEBCAM" / "ESP32" pill kaynağı gösterir

### Sağ — RANSAC Konum Çizimi
- Tespit vektörleri + ortak kesişim noktası
- Çoklu kareden konum tutarlılığı

---

## 5. Sözlü Demo Senaryosu

> "Bu, **YOLOv8** tabanlı otonom yangın tespit robotu. Sentetik modda, gerçek
> donanım olmadan tam sistem çalışıyor. **Bulanık mantık** ile her hedefin
> önceliği skorlanır, **Simulated Annealing** ile çoklu yangın için en kısa
> ziyaret sırası bulunur. Stable-fire kararı geldiğinde gerçek robotta
> Arduino'ya LED + buzzer alarm sinyali gider.
>
> Burada *mesafe* mono-kameradan, *risk yoğunluğu* per-pixel heatmap'ten,
> *kamera açısı* primary hedefin görüntüdeki yatay konumundan hesaplanır.
> Manuel müdahale için klavye veya ekran üzerinden sürüş yapılabilir.
>
> Model, **gerçek yangın + sentetik sahne karışık eğitim** ile yapıldı —
> mAP50 0.93. Eğitim pipeline'ı tek komut: `python ai/finetune_synthetic.py`."

---

## 6. Sorun Giderme

| Sorun | Çözüm |
|---|---|
| Backend açılmıyor | `tail -50 /tmp/oyts_demo/backend.log` — Python/dep eksik mi? |
| Tarayıcıda "backend kapalı" | Backend henüz hazır değil (YOLO yükleme 10-20 sn). Sayfayı yenile. |
| Yangın görünmüyor (sentetik) | Config'te `passthrough_detections: true` yap — model bypass. |
| Webcam çalışmıyor | macOS gizlilik izni: Sistem Ayarları → Gizlilik → Kamera → Terminal. |
| `model_path bulunamadı` | `cd python && ls fire_model*.pt` — yoksa `cp fire_model_v3_real.pt fire_model.pt` |

---

## 7. Hızlı Test (donanımsız)

```bash
cd python
/usr/bin/python3 -m pytest tests/         # 44 test, hepsi geçmeli
python pc_vision_controller.py --max-frames 10 --headless   # 10 frame sim koşusu
```

Her ikisi başarıyla biterse sistem sağlam.

---

## 8. Sıralı Komut Özeti

```bash
# Kurulum (bir kerelik)
cd python && pip install -r requirements.txt

# Demo
./run_demo.sh

# Test
cd python && /usr/bin/python3 -m pytest tests/

# Yeniden eğitim (3-4 saat MPS)
cd python && python ai/finetune_synthetic.py

# Donanımla canlı (Arduino + ESP32-CAM bağlı)
python pc_vision_controller.py --no-sim
```
