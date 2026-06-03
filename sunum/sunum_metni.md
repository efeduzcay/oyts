# OYTS — Otonom Yangın Tespit Sistemi
## PowerPoint Sunum Metni

> **Proje:** Piri Reis Üniversitesi · BIP 2012 Bitirme Projesi
> **Geliştiriciler:** Sema Nur Işık & Efe Düzçay
> **Sürüm:** v3.1.1 · Haziran 2026
>
> Bu dosya PowerPoint hazırlamak için **slayt başlık + içerik + konuşmacı notları** formatında düzenlenmiştir. Her bölüm bir slayda denk gelir.

---

## 🎯 Sunum Akışı (önerilen 18 slayt, ~12 dk)

1. Kapak
2. Proje Tanıtımı
3. Sorun: Yangın Neden Geç Tespit Edilir?
4. Mevcut Çözümler ve Eksiklikleri
5. Bizim Çözümümüz: OYTS
6. Sistem Mimarisi — 3 Katman
7. Donanım Bileşenleri
8. Katman 1 — ESP32-CAM (Görüntü)
9. Katman 2 — Arduino Mega (Hareket + Alarm)
10. Katman 3 — PC + YOLOv8 (Karar)
11. Algoritma 1 — YOLOv8 Derin Öğrenme
12. Algoritma 2 — Bulanık Mantık Önceliklendirme
13. Algoritma 3 — Simulated Annealing Rota
14. Akıllı Filtreleme — Multi-Signal Validator
15. Sentetik Simülasyon — Donanımsız Test
16. Yazılım Mimarisi + Testler
17. Sonuçlar & Demo
18. Sonuç ve Gelecek Çalışmalar

---

# SLAYT 1 — Kapak

## Başlık
🔥 **OYTS — Otonom Yangın Tespit Sistemi**

## Alt Başlık
YOLOv8 · Bulanık Mantık · Simulated Annealing

## Görsel Önerisi
- Robot fotoğrafı veya hero render (web/index.html'deki gradient arkaplan tarzı)
- Köşede üniversite logosu

## Bilgi
- **Proje:** BIP 2012 — Bitirme Projesi
- **Üniversite:** Piri Reis Üniversitesi
- **Geliştiriciler:** Sema Nur Işık · Efe Düzçay
- **Tarih:** Haziran 2026

---

# SLAYT 2 — Proje Tanıtımı

## Başlık
**Proje Nedir?**

## İçerik (3 madde)
- Yangınları **erken evrede** ve **otonom** olarak tespit eden, müdahale eden robot sistem
- **3 katmanlı** gömülü sistem: göz (kamera), beyin (mikrodenetleyici), karar (yapay zekâ)
- **İnsana bağımlı olmadan** sürekli izleme ve müdahale yapabiliyor

## Sayısal Vurgular (kart şeklinde)
- **~6.000 satır** Python kodu
- **~1.000 satır** Arduino C++ kodu
- **50 birim test** (otomatik doğrulama)
- **mAP50 = 0.93** (sentetik sahne) / **0.60** (gerçek dünya)

## Konuşma Notu
> "Projemiz, bir konferans salonunda, depoda veya benzin istasyonunda gece-gündüz fark etmeksizin sürekli devriye gezen, alev çıktığı an tespit edip müdahale eden bir robottur. Toplam 7 bin satırın üzerinde kod ve 50 otomatik test ile profesyonel bir yazılım kalitesi hedefledik."

---

# SLAYT 3 — Sorun: Yangın Neden Geç Tespit Edilir?

## Başlık
**Sorun Tespiti**

## 3 Ana Problem (ikonlarla)

### 🚨 Geç Tespit
Klasik duman dedektörleri alev sahneye çıktıktan sonra tetiklenir — yangın yayılmış olur.

### 👤 İnsan Bağımlılığı
CCTV varsa bile **gece veya mesai dışında** monitör izleyen olmaz.

### 📍 Sabit Nokta Körlüğü
Sabit kameralar açı dışını göremez. **Hareketli bir göz** gerekli.

## Görsel Önerisi
Üç sütunlu kart düzeni (web/index.html'deki gibi)

## Konuşma Notu
> "Türkiye'de 2024 yılında 70 binin üzerinde yangın olayı yaşandı. Bu yangınların büyük bölümü, ilk dakikalarda fark edilseydi büyük hasara dönüşmeyecekti. Mevcut duman alarmları alev çıktıktan dakikalar sonra tetiklenir ve sabit kameralar her noktayı göremez."

---

# SLAYT 4 — Mevcut Çözümler ve Eksiklikleri

## Başlık
**Mevcut Sistemler Yetersiz**

## Karşılaştırma Tablosu

| Sistem | Hız | Otonom mu? | Hareketli mi? | Maliyet |
|---|---|---|---|---|
| Duman Dedektörü | Yavaş ❌ | Hayır | Hayır | Düşük |
| CCTV + İnsan | Orta | Hayır ❌ | Hayır | Yüksek |
| AI Destekli CCTV | Hızlı | Yarı | Hayır ❌ | Çok Yüksek |
| **OYTS (Bizim)** | **Hızlı ✓** | **Evet ✓** | **Evet ✓** | **Düşük-Orta** |

## Konuşma Notu
> "Hem hızlı, hem tamamen otonom, hem de hareketli olabilen bir sistem yoktu. Profesyonel çözümler çok pahalı, ev/ofis ölçeğinde kullanılamıyor. Biz bu boşluğu hedefledik."

---

# SLAYT 5 — Bizim Çözümümüz: OYTS

## Başlık
**Çözüm: Robot Otonom Yangınla Mücadele Eder**

## 3 Ana Yetenek (kart düzeni — web/index.html'deki gibi)

### 👁 GÖRÜYOR
ESP32-CAM ile ortamı sürekli izler, alev rengini saniyeler içinde tanır.

### 🧠 KARAR VERİYOR
Birden fazla yangın varsa Bulanık Mantık ile **hangisi öncelikli** olduğunu hesaplar.

### 🎯 MÜDAHALE EDİYOR
Hedefe yaklaşır, sıcaklık eşiğine geldiğinde **otomatik müdahale** başlatır.

## Vurgu Mesaj
> **"Hiçbir insan müdahalesine gerek yok. Robot kendi kendine görür, karar verir ve müdahale eder."**

## Konuşma Notu
> "Sistemimizin 3 temel yeteneği var. Birincisi görme yeteneği — ESP32-CAM her saniye onlarca kare yollar ve modelimiz bunu analiz eder. İkincisi karar verme — birden çok alev olduğunda Bulanık Mantık kullanarak hangisinin daha öncelikli olduğunu hesaplar. Üçüncüsü müdahale — durum makinesiyle yaklaşır ve sıcaklık 60°C'yi geçtiğinde durur ve müdahale başlatır."

---

# SLAYT 6 — Sistem Mimarisi: 3 Katman

## Başlık
**Üç Katman, Üç Sorumluluk**

## Mimari Diyagram
```
        ┌──────────────────────────────────────────┐
        │  PC (Python · YOLOv8 · Fuzzy · SA)       │
        │  ←── Karar Katmanı                       │
        └──────────────┬───────────────────────────┘
                       │ Wi-Fi (MJPEG)     USB Serial
                       ▼                          ▼
        ┌─────────────────────┐    ┌──────────────────────┐
        │   ESP32-CAM          │    │  Arduino Mega 2560   │
        │   ← Göz Katmanı      │    │  ← Beyin/Kas Katmanı │
        └─────────────────────┘    └──────────────────────┘
```

## Katman Sorumlulukları

| Katman | Donanım | Görev |
|---|---|---|
| **Göz** | ESP32-CAM | Wi-Fi MJPEG yayın · Telemetri (sıcaklık) |
| **Beyin / Kas** | Arduino Mega 2560 + L298N | Motor kontrolü · Servo · Voltaj · Alarm |
| **Karar** | PC + Python | Tespit · Önceliklendirme · Rota |

## Konuşma Notu
> "Sistemi 3 katmanlı tasarladık. Her katmanın net bir sorumluluğu var — bu modüler yaklaşım sayesinde herhangi bir katmanı izole test edebiliyoruz. Mesela kamera olmadan da, robot olmadan da PC tarafı sentetik sahne ile test edilebiliyor."

---

# SLAYT 7 — Donanım Bileşenleri

## Başlık
**Donanım Bileşenleri**

## Tablo

| Bileşen | Model / Özellik | Görev |
|---|---|---|
| Görüntü modülü | ESP32-CAM (AI Thinker) | MJPEG akış + JSON telemetri |
| Mikrodenetleyici | Arduino Mega 2560 | Motor + servo kontrolü, voltaj izleme |
| Motor sürücüsü | L298N Dual H-Bridge | 4× DC motor PWM kontrolü |
| Şasi | 4WD TT Motor Platformu | Diferansiyel sürüş |
| Servo motor | SG90 / MG90S | Robot kol hareketi |
| Güç kaynağı | 3S LiPo 11.1V + 5V 3A regülatör | Sistem beslemesi |
| İşlem birimi | PC (Mac M4 / Windows) | YOLOv8 inference + UI |

## Toplam Maliyet
**~600-800 TL** (PC hariç)

## Görsel Önerisi
- 3 robot fotoğrafı (web/photo/photo1.jpg, photo2.jpeg, photo3.jpeg)

## Konuşma Notu
> "Tüm bileşenler hobi-elektronik mağazalarından kolayca temin edilebiliyor. Bilinçli olarak yaygın ve uygun fiyatlı modüller seçtik — proje **tekrarlanabilir** olsun, başka öğrenciler de aynı donanımla yapabilsin diye."

---

# SLAYT 8 — Katman 1: ESP32-CAM (Göz)

## Başlık
**ESP32-CAM — Görüntü Katmanı**

## Özellikler

- **Wi-Fi MJPEG stream** — gerçek zamanlı 30 fps yayın
- **Dinamik çözünürlük** — `/resolution` endpoint ile runtime'da değişir (QVGA → UXGA)
- **WiFi auto-reconnect** — bağlantı düşerse otomatik tekrar bağlanır
- **Frame fail watchdog** — N kare üst üste hata olursa soft restart
- **CORS açık** — doğrudan tarayıcıdan izlenebilir
- **JSON telemetri** — `/telemetry` endpoint: IP, RSSI, PSRAM, FPS, sıcaklık

## Kod Mimarisi
- Arduino C++ (1034 satır)
- HTTP sunucu non-blocking yapıda
- Heartbeat LED (built-in flash LED)

## Konuşma Notu
> "ESP32-CAM'ı tek başına bir mini-web sunucu gibi tasarladık. PC tarayıcıdan doğrudan stream izleyebilir, JSON telemetri çekebilir. Bağlantı düşse bile otomatik yeniden bağlanır — sahada güvenli."

---

# SLAYT 9 — Katman 2: Arduino Mega (Beyin/Kas)

## Başlık
**Arduino Mega 2560 — Hareket ve Alarm Katmanı**

## Özellikler

### Motor Kontrolü
- L298N H-Bridge ile **4WD diferansiyel sürüş**
- PWM hız kontrolü (60-255 arası)
- **Non-blocking servo sweep** — kontrol döngüsü hiç durmaz

### Güvenlik
- **Komut zaman aşımı** (500 ms) — PC'den komut gelmezse otomatik durdurma
- **Voltaj izleme** (A0 pin, 30k+10k voltaj bölücü)
- **Düşük pil uyarısı** (`WARN:BATT_LOW`)

### Alarm
- **Fire LED** (D13) + opsiyonel buzzer (D8)
- 5 sn'de sinyal gelmezse alarm otomatik söner

### İletişim
- **STATUS heartbeat** (1 sn'de bir)
- **Yapısal protokol**: `CMD:FORWARD;SPD:180;ARM:UP`
- READY handshake ile boot sinyali

## Konuşma Notu
> "Arduino Mega projemizin omurgası. Motor kontrolü, servo, voltaj izleme ve alarm yönetimi hepsi burada. Önemli nokta: hiçbir komut bloklamaz — servo hareket ederken bile motor zaman aşımı ve voltaj okuma sürmeye devam eder."

---

# SLAYT 10 — Katman 3: PC + YOLOv8 (Karar)

## Başlık
**PC Tarafı — Karar Katmanı**

## Yazılım Pipeline

```
YOLOv8 Tespit → Multi-Validator → IoU Tracker
       → Fuzzy Priority → Simulated Annealing → FSM → Motor
```

## Ana Modüller
- **`pc_vision_controller.py`** — Ana orkestratör
- **`web_app.py`** — Flask backend + web UI
- **`ai/`** klasörü — 13 AI modülü:
  - `tracker.py` — IoU multi-target tracker
  - `heatmap.py` — Per-pixel risk gradient
  - `distance.py` — Mono-kamera mesafe tahmini
  - `fire_validator.py` — 4-sinyal doğrulayıcı
  - `bright_flame_detector.py` — Klasik CV küçük alev tespiti
  - `webhook.py` — Dış sistem bildirim
  - `sim_detector.py` — Sentetik passthrough
  - + eğitim ve değerlendirme araçları

## Teknolojiler
Python 3.10+ · YOLOv8 (Ultralytics) · PyTorch · OpenCV · Flask · NumPy

## Konuşma Notu
> "PC tarafı projemizin beynidir. Sadece YOLOv8 inference değil — onun çıktısını filtreleyen, takip eden, önceliklendiren ve robot komutuna çeviren tüm bir karar zincirini biz yazdık. 13 ayrı AI modülü, her biri tek bir sorumluluğa sahip."

---

# SLAYT 11 — Algoritma 1: YOLOv8 Derin Öğrenme

## Başlık
**YOLOv8 — Derin Öğrenme ile Görüntüden Tespit**

## Model Bilgileri
- **Mimari:** YOLOv8s (Small) — 11.1M parametre, 28.4 GFLOPs
- **Sınıflar:** fire (alev), smoke (duman), default
- **Çözünürlük:** 640×640
- **Inference hızı:** MPS'de 16+ FPS, CPU'da 3-5 FPS

## Eğitim Süreci
| Dataset | Boyut | mAP50 | Süre |
|---|---|---|---|
| D-Fire + FASDD (orijinal) | ~25.000 image | 0.55 | hazır |
| + 5000 sentetik (fine-tune) | 30.000 image | **0.93** | 1 saat |
| + 2000 Roboflow (yeniden) | 32.000 image | 0.60 (real) | 1 saat |

## Fine-tuning Stratejisi
- **freeze=10** (backbone dondurulur, sadece head öğrenir)
- **lr0=1e-4** (catastrophic forgetting önleme)
- **30 epoch maks** (genelde patience=15 ile erken durur)

## Görsel Önerisi
- Eğitim loss grafiği (`runs/finetune/synfinetune_*/results.png`)
- Confusion matrix

## Konuşma Notu
> "YOLOv8, gerçek zamanlı obje tespiti için tasarlanmış son nesil bir derin öğrenme modeli. Biz bu modeli kendi sentetik dataset'imizle fine-tune ettik — orijinal model sentetik sahneyi tanımıyordu, fine-tune sonrası mAP50 0.93 elde ettik."

---

# SLAYT 12 — Algoritma 2: Bulanık Mantık

## Başlık
**Bulanık Mantık (Fuzzy Logic) — Önceliklendirme**

## Neden Bulanık Mantık?

Yangının "öncelik" değeri keskin sınırlarla ayrılamaz. Bir 5000 piksellik alev "küçük" mü "orta" mı? Klasik mantıkla "MEDIUM" başlangıcı 5000 ise 4999 piksellik alev SMALL olur — anlamsız.

**Bulanık mantık:** bir alev hem %60 MEDIUM hem %40 SMALL olabilir.

## Mamdani Çıkarsama

### Üyelik Fonksiyonları (trapezoidal)

| Küme | Aralık (piksel²) | Çıkış Skoru |
|---|---|---|
| SMALL | [0, 0, 2000, 3000] | 0.15 |
| MEDIUM | [2000, 3000, 10000, 12000] | 0.45 |
| LARGE | [10000, 12000, 24000, 28000] | 0.78 |
| HUGE | [24000, 28000, 60000, 60000] | 1.00 |

### Defuzzification (Ağırlıklı Ortalama)

```
P = Σ(μᵢ × vᵢ) / Σ(μᵢ)
```

## Örnek
3000 piksellik bir alev: μ_SMALL=0.5, μ_MEDIUM=0.5
**P = (0.5×0.15 + 0.5×0.45) / 1.0 = 0.30**

## Konuşma Notu
> "Bulanık mantık, yangının büyüklüğünü ve önceliğini insan gibi düşünme imkânı verir. Bir alev hem 'küçük' hem 'orta' olabilir. Bu sayede 1 pikselin alev sınıfını değiştirmesi gibi saçmalıklar yaşanmaz. Mamdani modeli en yaygın bulanık çıkarsama yöntemidir."

---

# SLAYT 13 — Algoritma 3: Simulated Annealing

## Başlık
**Simulated Annealing — Çoklu Yangında Rota Optimizasyonu**

## Problem
3-5 yangın aynı anda varsa, robot **hangisine önce gitmeli?**

Tüm permütasyonlar kontrol edilse (Brute Force):
- 5 yangın → 120 olası sıralama
- 10 yangın → 3.6 milyon — gerçek zamanlıda imkânsız

## Çözüm: Simulated Annealing

Metal tavlamadan esinlenmiş bir optimizasyon algoritması:

```
Başlangıç sıcaklığı: T = 5000
Soğuma katsayısı: α = 0.995
İterasyon: 3000

Her iterasyonda:
  1. Mevcut çözümü ufak bir değişiklikle değiştir
  2. Yeni çözüm daha iyiyse → kabul
  3. Daha kötüyse → P = e^(-ΔC/T) olasılıkla yine de kabul
  4. T = T × α (sıcaklığı düşür)
```

## Sonuç
- Optimuma yakın çözüm (genelde %95+)
- 5-10 yangın için **milisaniyeler içinde**
- Robot konumundan başlayan **en kısa toplam Öklid mesafesi**

## Görsel Önerisi
- 5 yangın noktası + robot başlangıç noktası + optimal rota çizgisi
- Sıcaklık-mesafe grafiği

## Konuşma Notu
> "Simulated Annealing, NP-zor problemleri yaklaşık çözmek için kullanılan klasik bir algoritma. Bizim senaryomuzda 'gezgin satıcı problemi' var — robot tüm yangınları minimum mesafeyle ziyaret etmeli. Algoritma rasgele kötü hamleleri de bir olasılıkla kabul ederek local minimum tuzaklarından kaçar."

---

# SLAYT 14 — Akıllı Filtreleme: Multi-Signal Validator

## Başlık
**Multi-Signal Fire Validator — False Positive Eliminasyonu**

## Sorun
YOLO tek başına yetmez:
- Telefondan **kırmızı bir fotoğraf** = yangın sanır
- **Cilt** veya yüz parlamaları = yangın sanır
- **Kırmızı duvar** = yangın sanır

## Çözüm: 4 Fiziksel İmza ile Doğrulama

### 4 Sinyal

| Sinyal | Ölçtüğü | Ağırlık |
|---|---|---|
| **bright_core** | V≥245 (beyaz çekirdek) piksel oranı | **0.45** |
| **temporal** | Son N frame'de ROI içi piksel-piksel değişim | 0.25 |
| **motion** | Frame-to-frame absolute difference | 0.20 |
| **saturation** | Alev rengi konformanı (H + S + V) | 0.10 |

### Composite Karar
```
score = Σ(weight_i × signal_i)
karar = ACCEPT if score ≥ 0.35 else REJECT
```

## Sonuç Matrisi

| Senaryo | composite | Karar |
|---|---|---|
| Gerçek çakmak (titrer) | 0.66 | ✅ KABUL |
| Yangın videosu | 0.55 | ✅ KABUL |
| Statik kırmızı foto | 0.12 | ❌ RED |
| Yüz / cilt | 0.14 | ❌ RED |

## Konuşma Notu
> "Bu modülü tamamen kendi tasarladık. Gerçek alevin 4 fiziksel özelliği var: beyaz parlayan çekirdek, içerden titreşim, hareket ve karakteristik renk profili. Bir fotoğraf veya cilt bu kombinasyonun tümünü gösteremez. Validator'ı eklemeden önce sistem yüzü yangın sanıyordu — şimdi sadece gerçek alev geçiyor."

---

# SLAYT 15 — Sentetik Simülasyon

## Başlık
**Sentetik Simülasyon — Donanımsız Geliştirme**

## Neden Önemli?

Hardware geliştirmek **yavaş**:
- Test için her seferinde robot çalıştırmak gerek
- Çakmak/mum tehlikeli
- Kötü hava şartlarında test yapılamıyor

**Çözüm:** Foto-gerçekçi bir **sentetik yangın sahnesi üreticisi** yazdık (`sim/fire_scene_generator.py`)

## Özellikleri

### 8 Render Katmanı
1. Arka plan (loş oda, duvar lekeleri)
2. Yer ışık yansıması (turuncu glow)
3. Duman parçacık sistemi
4. Alev (çok-oktavlı value noise + palette)
5. Heat haze (sıcaklık dalgalanması)
6. Kıvılcımlar (yukarı fırlayan parlak noktalar)
7. Bloom (HDR parlaklık)
8. Tone mapping (ACES filmic)

### Etkileşim
- Tuş ile zoom (+/-), yangın sayısı (1-5), büyüme, hareket
- Otomatik **ground truth bbox** etiketi üretir

## Performans
- 960×540'ta MacBook M1'de **25-40 FPS**

## Görsel Önerisi
- Sentetik sahnenin 3-4 ekran görüntüsü (web/screenshots/demo_synthetic_*.jpg)

## Konuşma Notu
> "Bu modül projemizin gizli kahramanı. Sentetik sahne sayesinde kameramız bozulsa, robotumuz şarjda olsa, her şart altında sistemin yazılım tarafını test edebiliyoruz. Hatta YOLO modelimizi bu sahnelerden 5000 frame ile fine-tune ederek başarımını artırdık."

---

# SLAYT 16 — Yazılım Mimarisi + Testler

## Başlık
**Profesyonel Yazılım Pratiği**

## Test Paketi — **50/50 Pytest Geçiyor**

| Test Dosyası | Test Sayısı | Kapsam |
|---|---|---|
| `test_tracker.py` | 8 | IoU eşleştirme, stable promotion, grace |
| `test_fuzzy_sa.py` | 8 | Üyelik fonksiyonu, SA ordering |
| `test_decision.py` | 7 | FSM dallanmaları |
| `test_ai_modules.py` | 11 | Heatmap, distance, webhook, sim_detector |
| `test_fire_validator.py` | 6 | 4-sinyal validator |
| `test_scene_generator.py` | 5 | Sentetik render smoke |
| `test_config_csv.py` | 5 | ConfigDict, CSVLogger |
| **Toplam** | **50** | |

## Kod Tabanı

- **6027 satır** Python (37 dosya)
- **1034 satır** Arduino C++ (2 .ino)
- **YAML konfigurasyon** (3 farklı profil)
- **Pytest CI-ready** (`--max-frames N --headless` modu)
- **Logger + CSV telemetri** (her frame için kayıt)

## Yazılım Pratikleri
- Type hints
- Docstrings (Türkçe açıklamalar)
- Cross-platform (macOS + Windows test edilmiş)
- Tek komutla demo (`./run_demo.sh`)
- Web UI + REST API
- Webhook ile dış sistem entegrasyonu

## Konuşma Notu
> "Sadece çalışan bir prototip değil, **bakım yapılabilir** ve **test edilebilir** bir yazılım yazdık. 50 birim test, her commit'te otomatik çalışır — bir özellik bozulursa hemen fark ederiz. Bu, gerçek üretim kalitesi standardı."

---

# SLAYT 17 — Sonuçlar & Demo

## Başlık
**Sonuçlar ve Canlı Demo**

## Başarım Metrikleri

### Model
- **Sentetik mAP50:** 0.93 (mükemmel)
- **Gerçek mAP50:** 0.60 (kullanılabilir)
- **Inference hızı:** 16+ FPS (Apple M4 MPS)
- **Tespit gecikmesi:** <1 saniye

### Sistem
- **Yangın tespiti:** ✅ Çakmak, mum, yangın videosu
- **False positive filtresi:** ✅ Kırmızı foto, cilt, yüz elenir
- **Manuel sürüş:** ✅ Klavye + ekran üzeri panel
- **Heatmap overlay:** ✅ Risk yoğunluğu canlı

### Demo Akışı
1. `./run_demo.sh synthetic` → tek komut
2. Tarayıcı otomatik açılır
3. Sentetik sahne canlı yangın gösterir
4. Sistem otomatik tespit + bbox + mesafe ölçer
5. 🎲 / 📷 / 📡 chip'leri ile mod değiştir

## Görsel Önerisi
- Web UI ekran görüntüsü (Sistem Durumu + Canlı Kamera + Manuel Sürüş)
- Demo video QR kodu (varsa)

## Konuşma Notu
> "Sistemimizi 3 farklı modda gösterebiliyoruz: sentetik (donanım yok), webcam (Mac kamerası), ESP32-CAM (gerçek robot). Şu an canlı demo yapacağım — [demo başlat]. Görüldüğü gibi sistem 2 yangını otomatik tespit ediyor, mesafelerini ölçüyor ve risk yoğunluk haritasını render ediyor."

---

# SLAYT 18 — Sonuç ve Gelecek Çalışmalar

## Başlık
**Sonuç ve Gelecek Çalışmalar**

## Kazanımlar

### Teknik
- 7 binin üzerinde satır kod, 50 birim test ile profesyonel kalite
- 13 farklı AI modülü — modüler yapı
- Hibrit yaklaşım: derin öğrenme + klasik bilgisayarlı görü
- Çapraz platform: macOS, Windows, gömülü cihazlar

### Akademik
- 3 farklı algoritma sınıfının entegrasyonu (DL + Fuzzy + Metasezgisel)
- Sentetik veri üretimi ile transfer öğrenme
- Multi-signal fusion ile false-positive eliminasyonu

## Sınırlamalar
- **Çok küçük alev** (çakmak < 30 piksel) zorlu — dataset sınırı
- **Aşırı parlak ortam** (güneşli) kontrast düşer
- **Wi-Fi mesafesi** ESP32-CAM için ~30-50 m

## Gelecek Çalışmalar
- **Termal kamera** entegrasyonu (gerçek sıcaklık ölçümü)
- **Söndürme mekanizması** — CO₂ valfi veya sprey
- **Çoklu robot** koordinasyonu (büyük alanlar için)
- **MLOps pipeline** — Roboflow Active Learning ile sürekli iyileştirme
- **Termoplastik 3D baskı şasi** (özelleştirilmiş)

## Konuşma Notu
> "Projemizi sadece bitirme tezi olarak değil, gerçek dünyada kullanılabilir bir prototip olarak tasarladık. Açık kaynak olarak yayınlanıyor, başka öğrenciler buradan devam edebilir. Gelecekte termal kamera ve söndürme mekanizması ekleyerek tam fonksiyonel hale getirmeyi planlıyoruz."

---

# SLAYT 19 (BONUS) — Teşekkürler / Sorular

## Başlık
**Teşekkürler**

## İçerik
- Danışman Hocamıza
- Piri Reis Üniversitesi Bilgisayar Programcılığı Bölümü'ne
- Open-source topluluğuna (Ultralytics YOLOv8, Roboflow, D-Fire/FASDD dataset'leri)

## Bağlantılar
- **GitHub:** github.com/efeduzcay/robotproje123
- **Canlı Demo:** mesleki-proje.github.io/web-sitesi/
- **Proje Sürümü:** v3.1.1 (Haziran 2026)

## Soru-Cevap
"Sorularınız için hazırız."

## Geliştiriciler
**Sema Nur Işık** & **Efe Düzçay**

---

# 📝 SUNUM HAZIRLAMA İPUÇLARI

## Genel
- **Süre:** 18 slayt × 30-45 sn = 9-13 dakika
- **Görsel yoğunluğu:** Slayt başına 1 ana görsel + max 3 metin satırı
- **Renk paleti** (web sitenizdeki gibi):
  - Ana mavi: `#0047AB`
  - Vurgu turuncu: `#FF6B35`
  - Arka plan: `#F8FAFF`
  - Koyu metin: `#1a202c`

## Font Önerisi
- **Başlık:** Inter / Montserrat Bold
- **Gövde:** Inter / Open Sans Regular
- **Kod / monospace:** JetBrains Mono / Fira Code

## Görseller (`web/photo/` ve `web/screenshots/` klasörlerinden)
- `web/photo/photo1.jpg` — Devre + bileşenler (Slayt 7)
- `web/photo/photo2.jpeg` — Robot şasi (Slayt 7)
- `web/photo/photo3.jpeg` — Robot bağlantı detay (Slayt 7)
- `web/screenshots/demo_synthetic_1.jpg` — Sistem çalışırken (Slayt 15, 17)
- `web/screenshots/demo_synthetic_2.jpg` — Heatmap görüntüsü
- `web/screenshots/demo_synthetic_3.jpg` — Primary + secondary track

## Animasyon Önerileri
- Hero slayt: alev emoji'sini pulse animasyonuyla
- Mimari slayt: kutular sırayla appear
- Algoritma slaytları: formüller fade-in
- Demo slayt: ekran video kaydı embed et

## Demo Hazırlığı
Sunumdan **5 dakika önce** terminal'de:
```bash
cd ~/Desktop/robot-3.0.0
./run_demo.sh synthetic
```
Tarayıcıyı F11 (full-screen) ile aç. Sunum sırasında demo slaytına gelince Cmd+Tab ile geç.

## Konuşmacı Notları İçin
Her slaytta "Konuşma Notu" bölümü ekledim. Bunları PowerPoint'in **Speaker Notes** kısmına kopyala (View > Notes Master / View > Speaker Notes).

---

**Hazırlayan:** OYTS Proje Ekibi
**Sürüm:** Sunum Metni v1.0 — 2026-06-01
