# Otonom Yangın Tespit ve Müdahale Robotu

**Sürüm:** v3.1.1 &nbsp;|&nbsp; **Son Güncelleme:** Haziran 2026 &nbsp;|&nbsp; **Durum:** Aktif Geliştirme

Bu proje; **YOLOv8 derin öğrenme modeli**, **Bulanık Mantık (Mamdani)** ve **Simulated Annealing** algoritmalarını entegre ederek gerçek zamanlı yangın tespiti ve otonom robot navigasyonunu hedefleyen üç katmanlı bir gömülü sistem çalışmasıdır.

> **v3.1.1** ile model **sentetik + gerçek karışık** veride fine-tune edildi (mAP50 0.93), **yangın yoğunluk ısı haritası**, **mono-kamera mesafe tahmini** ve **webhook bildirim** eklendi. **44 pytest** baseline + tek komutla demo (`./run_demo.sh`).

## ⚡ Hızlı Başlangıç

```bash
# Bağımlılıklar (bir kerelik)
cd python && pip install -r requirements.txt && cd ..

# Demo (donanımsız, sentetik)
./run_demo.sh

# Tarayıcı otomatik açılır → http://127.0.0.1:8765/live.html
```

Detaylı rehber için: [**DEMO.md**](DEMO.md) &nbsp;·&nbsp; sürüm geçmişi: [**CHANGELOG.md**](CHANGELOG.md)

---

## İçerik

- [Proje Hakkında](#proje-hakkında)
- [Dizin Yapısı](#dizin-yapısı)
- [Sistem Mimarisi](#sistem-mimarisi)
- [Donanım Bileşenleri](#donanım-bileşenleri)
- [Kurulum](#kurulum)
- [Yapay Zeka: Eğitim Pipeline](#yapay-zeka-eğitim-pipeline)
- [Simülasyon Modu](#simülasyon-modu)
- [Çalıştırma](#çalıştırma)
- [Konfigürasyon](#konfigürasyon)
- [Algoritmalar](#algoritmalar)
- [İletişim Protokolü](#iletişim-protokolü)
- [Klavye Kontrolleri](#klavye-kontrolleri)
- [Sürüm Geçmişi](#sürüm-geçmişi)

---

## Proje Hakkında

Üç katmanlı bir otonom yangın müdahale robotu:

1. **ESP32-CAM** (görüntü modülü) — Wi-Fi üzerinden MJPEG akışı + JSON telemetri
2. **Arduino Mega 2560** (mikrodenetleyici) — Motor sürücüleri, servo kolu, voltaj izleme
3. **PC (Python)** — YOLOv8 ile yangın/duman tespiti, bulanık mantık ile öncelik skorlaması, simulated annealing ile rota optimizasyonu

Sistem; kapalı ortamlarda yangın kaynaklarını gerçek zamanlı tespit eder, en yüksek riskli noktayı belirler ve robotu otonom olarak o noktaya yönlendirir.

**Özgün katkılar:**

1. **Derin öğrenme tabanlı tespit:** D-Fire + FASDD üzerinde eğitilen YOLOv8 modeli, **5000 frame sentetik sahnede fine-tune** edildi (mAP50 0.93)
2. **Bulanık mantık önceliklendirme:** Piksel alanına dayalı trapezoidal üyelik fonksiyonları, Mamdani çıkarsama
3. **SA rota optimizasyonu:** Birden fazla hedef için en kısa ziyaret sırası
4. **Sentetik simülasyon ortamı:** Robot olmadan, webcam olmadan, donanımdan bağımsız test
5. **Yangın yoğunluk ısı haritası** (per-pixel risk gradient + decay)
6. **Mono-kamera mesafe tahmini** (bbox area + dikey eksen bias)
7. **Async webhook bildirim** (stable-fire kenarında dış sistemlere POST)
8. **IoU multi-target tracker** (grace-frame stickiness, FSM titremesi sıfır)

---

## Dizin Yapısı

```
robot-3.0.0/
├── arduino/
│   ├── esp32_cam_stream/
│   │   └── esp32_cam_stream.ino       # MJPEG akış + telemetri
│   └── mega_robot_l298n/
│       └── mega_robot_l298n.ino       # Motor + servo kontrolü
│
├── python/
│   ├── pc_vision_controller.py        # Ana orkestratör (v5.0)
│   ├── fire_model.pt                  # Eğitilmiş YOLOv8 ağırlıkları
│   ├── requirements.txt
│   │
│   ├── configs/
│   │   └── config.yaml                # Tüm sistem parametreleri
│   │
│   ├── ai/                            # AI/CV katmanı
│   │   ├── prepare_dataset.py         # D-Fire + FASDD indirici
│   │   ├── train.py                   # YOLOv8 eğitim pipeline
│   │   ├── evaluate.py                # mAP / FPS / predict
│   │   └── tracker.py                 # IoU multi-target tracker
│   │
│   ├── sim/                           # Simülasyon katmanı
│   │   └── fire_scene_generator.py    # Sentetik yangın sahnesi
│   │
│   ├── utils/
│   │   ├── config_loader.py
│   │   └── csv_logger.py
│   │
│   └── kayitlar/                      # Video + CSV + log çıktıları
│
└── README.md
```

---

## Sistem Mimarisi

```
┌──────────────────────────────────────────────────────────────────┐
│                        PC (Python 3.10+)                          │
│  ┌──────────┐  ┌─────────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ YOLOv8   │  │ IoU Tracker │  │ Fuzzy    │  │ Simulated    │  │
│  │ Detector │─▶│ (stable)    │─▶│ Priority │─▶│ Annealing    │  │
│  └──────────┘  └─────────────┘  └──────────┘  └──────────────┘  │
│        ▲                                              │           │
│        │ ┌──────────────────────┐                     ▼           │
│        ├─┤ MJPEG (Wi-Fi)        │           ┌──────────────┐     │
│        │ └──────────────────────┘           │ Decision FSM │     │
│        │ ┌──────────────────────┐           │ + Smoothing  │     │
│        └─┤ Synthetic Fire Scene │           └──────────────┘     │
│          └──────────────────────┘                     │           │
│                       │                               │ USB       │
└───────────────────────┼───────────────────────────────┼───────────┘
                        ▼                               ▼
            ┌───────────────────┐         ┌──────────────────────┐
            │   ESP32-CAM       │         │  Arduino Mega 2560   │
            │   MJPEG Stream    │         │  L298N + 4WD + Servo │
            │   /telemetry      │         │  Voltaj izleme       │
            └───────────────────┘         └──────────────────────┘
```

---

## Donanım Bileşenleri

| Bileşen           | Model / Özellik              | Görev                                   |
|-------------------|------------------------------|-----------------------------------------|
| Görüntü Modülü    | ESP32-CAM (AI Thinker)       | MJPEG akış, JSON telemetri              |
| Mikrodenetleyici  | Arduino Mega 2560            | Motor/servo kontrolü, voltaj izleme     |
| Motor Sürücüsü    | L298N Dual H-Bridge          | 4× DC motor PWM kontrolü                |
| Şasi              | 4WD TT Motor Platform        | Diferansiyel sürüş                      |
| Servo             | SG90 / MG90S                 | Robot kol hareketi                      |
| Güç               | 3S LiPo 11.1V + 5V 3A reg.   | Sistem güç kaynağı                      |
| İşlem Birimi      | PC + NVIDIA GPU (CUDA)       | YOLOv8 inference & eğitim               |

---

## Kurulum

### 1. Python Bağımlılıkları

```bash
cd python
pip install -r requirements.txt

# CUDA 12.1 için PyTorch (NVIDIA GPU varsa)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

### 2. ESP32-CAM (Arduino IDE)

```
Board            : AI Thinker ESP32-CAM
PSRAM            : Enabled
Partition Scheme : Huge APP (3MB No OTA / 1MB SPIFFS)
CPU Frequency    : 240 MHz
Upload Speed     : 115200
```

`arduino/esp32_cam_stream/esp32_cam_stream.ino` içinde `WIFI_SSID` / `WIFI_PASS` düzenleyin.

### 3. Arduino Mega

```
Board   : Arduino Mega or Mega 2560
Baud    : 115200
Kütüph. : Servo.h (built-in)
```

`arduino/mega_robot_l298n/mega_robot_l298n.ino` doğrudan yüklenebilir.

---

## Yapay Zeka: Eğitim Pipeline

### Veri Hazırlama

**D-Fire** ve **FASDD** dataset'lerini birleştirip YOLO formatına dönüştürür (~25k görüntü, fire+smoke etiketli):

```bash
cd python
python ai/prepare_dataset.py --root datasets/fire_v3
```

Çıktı:
```
datasets/fire_v3/
├── images/{train,val,test}/*.jpg
├── labels/{train,val,test}/*.txt
└── data.yaml
```

**Manuel veri:** İnternet kısıtlıysa dataset'i `datasets/_raw/dfire/` ve/veya `datasets/_raw/fasdd/` altına yerleştirin, ardından:
```bash
python ai/prepare_dataset.py --root datasets/fire_v3 --skip-download
```

### Eğitim

Donanıma göre hazır preset'ler:

```bash
# MacBook M4 Air (pasif soğutma)  →  ~10 saat
python ai/train.py --preset mac-air --data datasets/fire_v3/data.yaml --export-deploy

# MacBook Pro M-serisi (aktif soğutma)  →  ~20 saat
python ai/train.py --preset mac-pro --data datasets/fire_v3/data.yaml --export-deploy

# NVIDIA RTX 3060/4060  →  ~6-10 saat
python ai/train.py --preset cuda-mid --data datasets/fire_v3/data.yaml --export-deploy

# NVIDIA RTX 4080/4090  →  ~3-5 saat
python ai/train.py --preset cuda-hi --data datasets/fire_v3/data.yaml --export-deploy
```

Tek tek override de mümkündür:
```bash
python ai/train.py --preset mac-air --epochs 150 --imgsz 512
```

| Preset | Model | imgsz | epochs | batch | device |
|---|---|---|---|---|---|
| `mac-air` | yolov8n | 480 | 100 | 16 | mps |
| `mac-pro` | yolov8s | 640 | 150 | 16 | mps |
| `cuda-mid` | yolov8s | 640 | 200 | 32 | cuda |
| `cuda-hi` | yolov8m | 640 | 300 | 32 | cuda |

**MacBook M-serisi notları:**
- Eğitimi mutlaka **şarjda** yap (pil hızlı biter, throttle olur)
- Düz, hava sirkülasyonu açık yüzeyde tut
- Eğitim sırasında ağır uygulamaları kapat (browser, IDE)
- M4 Air için inference de `configs/config_mac.yaml` ile çalıştır:
  ```bash
  python pc_vision_controller.py --config configs/config_mac.yaml
  ```

`--export-deploy` flag'i eğitim sonunda `best.pt` ağırlıklarını `python/fire_model.pt`'e kopyalar; ana kontrolcü otomatik olarak yeni modeli kullanır.

**Hiperparametreler** (`ai/train.py` içinde, üzerinde düşünülmüş):

| Kategori      | Değer                                                            |
|---------------|------------------------------------------------------------------|
| Optimizer     | AdamW (lr0=0.001, lrf=0.01, cosine LR)                          |
| Loss ağırlık  | box=7.5, cls=0.5, dfl=1.5                                       |
| Augmentation  | mosaic=1.0, mixup=0.15, copy_paste=0.10                         |
| HSV jitter    | h=0.015, s=0.70, v=0.50 (gece/gündüz varyasyonu)                |
| Geometrik     | degrees=10, translate=0.10, scale=0.50, fliplr=0.5              |
| Eğitim hilesi | AMP, EMA, early-stopping (patience=40)                          |

### Değerlendirme

```bash
# Test seti üzerinde mAP, P, R + grafikler
python ai/evaluate.py \
    --weights runs/detect/fire_v3_*/weights/best.pt \
    --data datasets/fire_v3/data.yaml \
    --split test

# FPS testi (200 inference, warmup dahil)
python ai/evaluate.py --weights fire_model.pt --fps

# Görüntü dizini üzerinde tahmin
python ai/evaluate.py --weights fire_model.pt --predict ornekler/
```

---

## Simülasyon Modu

Donanım olmadan **tam sistem testi** mümkündür. Üç farklı simülasyon kaynağı:

| Kaynak       | Konfig anahtarı       | Açıklama                                          |
|--------------|-----------------------|---------------------------------------------------|
| `synthetic`  | `sim_source: synthetic` | Sentetik alev+duman üretici (varsayılan)        |
| `webcam`     | `sim_source: webcam`    | Yerel kamera; gerçek alev/mum ile test          |
| `video`      | `sim_source: video`     | Önceden çekilmiş yangın videosu                 |

### Sentetik Sahne Üreticisi

`sim/fire_scene_generator.py` — Programatik olarak:
- Titreşimli, parlak alev blob'ları (palette tabanlı renk haritası)
- Yumuşak, yükselen duman bulutları (alpha blend)
- 1..5 hedef, hareketli veya sabit
- Robot yaklaşmasını simüle eden zoom

**Standalone test:**
```bash
python sim/fire_scene_generator.py --targets 3 --width 1280 --height 720
```

**Simülasyon içi tuş kısayolları:**

| Tuş     | Eylem                            |
|---------|----------------------------------|
| `+` / `-` | Robot yaklaşma zoom'u           |
| `n`     | Yeni rastgele sahne              |
| `1`-`5` | Hedef sayısı                     |
| `t`     | Hareket aç/kapa                  |
| `g`     | Yangın büyümesi aç/kapa          |
| `h`     | Yardım overlay                   |

---

## Çalıştırma

```bash
cd python

# Varsayılan: simülasyon + sentetik sahne
python pc_vision_controller.py

# Webcam ile (mum/çakmak ile test)
python pc_vision_controller.py --sim webcam

# Önceden çekilmiş video ile
python pc_vision_controller.py --sim video
# (configs/config.yaml içinde sim_video_path ayarlayın)

# Gerçek robot (ESP32-CAM + Arduino bağlı)
python pc_vision_controller.py --no-sim

# Farklı konfig dosyası
python pc_vision_controller.py --config configs/my_config.yaml
```

---

## Konfigürasyon

Tüm sistem parametreleri `configs/config.yaml` üzerinden yönetilir. Önemli bölümler:

```yaml
mode:
  simulation: true              # true = donanım yok
  sim_source: "synthetic"       # webcam | synthetic | video

ai:
  model_path: "fire_model.pt"
  conf_threshold: 0.40          # ↑ FP azaltma
  iou_threshold: 0.45
  device: "auto"                # auto | cuda | mps | cpu
  smoke_priority_factor: 0.6    # duman, ateşten daha düşük öncelik

robot:
  area_stop: 25000              # bu alanın üzeri = TOO_CLOSE
  command_smoothing: 3          # son 3 karenin oy çokluğu

tracking:
  iou_match_threshold: 0.30
  min_consecutive_hits: 3       # 3 kare üst üste görülmezse atla
```

---

## Algoritmalar

### 1. YOLOv8 Tespit

- Model: `yolov8s` veya `yolov8m`, custom-trained `fire_model.pt`
- Sınıflar: `fire`, `smoke`
- Inference: GPU üzerinde ~80–120 FPS (RTX 3060+), CPU ~6–10 FPS
- conf=0.40, iou=0.45 — false-positive azaltma için yüksek tutuldu

### 2. IoU Multi-Target Tracker

Greedy IoU eşleştirme; her bbox'a kalıcı `track_id` atar.

```
stable_target := hits ≥ min_consecutive_hits  AND  missed = 0
```

Sadece **stable** hedefler karar mantığına girer → titreme önlenir.

### 3. Bulanık Mantık — Öncelik Skorlaması

Mamdani; piksel alanı `[0, 1]` öncelik skoruna eşlenir. Trapezoidal kümeler:

| Küme   | Trapez (px²)                  | Çıkış |
|--------|-------------------------------|-------|
| SMALL  | [0, 0, 2K, 3K]               | 0.15  |
| MEDIUM | [2K, 3K, 10K, 12K]           | 0.45  |
| LARGE  | [10K, 12K, 24K, 28K]         | 0.78  |
| HUGE   | [24K, 28K, 60K, 60K]         | 1.00  |

Defuzzification (ağırlıklı ortalama):

$$P = \frac{\sum_i \mu_i v_i}{\sum_i \mu_i}$$

Duman tespitleri `smoke_priority_factor` (varsayılan 0.6) ile çarpılır.

### 4. Simulated Annealing — Rota Optimizasyonu

Birden fazla yangın varsa robot konumundan başlayarak minimum toplam Öklid mesafesi ile ziyaret sırasını bulur.

| Parametre  | Değer | Açıklama            |
|------------|-------|---------------------|
| T_start    | 5000  | Başlangıç sıcaklığı |
| T_end      | 1.0   | Sonlanma sıcaklığı  |
| α (alpha)  | 0.995 | Soğuma katsayısı    |
| max_iter   | 3000  | Maksimum iterasyon  |

Metropolis kabul kriteri: $P(\text{kabul}) = e^{-\Delta C / T}$

### 5. Komut Yumuşatma

Son N karenin oy çokluğu → motor komut titremesini önler. `command_smoothing: 3` varsayılan.

---

## İletişim Protokolü

### PC → Arduino (USB Serial, 115200 baud)

**Yapısal format** (varsayılan):
```
CMD:FORWARD;SPD:180;ARM:DOWN
CMD:LEFT;SPD:160
CMD:STOP;SPD:0
FIRE:ON                 # PC stable-fire imzaladı → LED+buzzer pattern
FIRE:OFF                # alarmı söndür
QUERY:STATUS            # anında STATUS heartbeat döndür
```

**Basit format** (`use_structured_protocol: false`):
```
W → İleri    A → Sol    D → Sağ    S → Geri
X → Dur      K → Kol aşağı         L → Kol yukarı
F → Fire alert ON       N → Fire alert OFF
B → Status anında       V → Voltaj anında
```

### Arduino → PC (v3 protokolü)

```
READY                                                              # boot handshake
VOLT:11.85                                                         # batarya (2sn'de bir)
STATUS:state=RUN,cmd=FORWARD,spd=180,arm=160,volt=11.7,alert=0     # 1sn heartbeat
ACK:FORWARD SPD=180                                                # komut onayı
ACK:FIRE_ON / ACK:FIRE_OFF                                         # alarm durumu
ACK:TIMEOUT_STOP                                                   # 500ms komut yoksa stop
WARN:BATT_LOW                                                      # 9.9V altı uyarısı
```

**Arduino Mega v3 yenilikleri:**
- **Non-blocking servo sweep** — kontrol döngüsü hiç durmuyor, motor zaman aşımı ve voltaj takibi sürerken kol hareket eder
- LED (D13 built-in) + opsiyonel buzzer (D8) ile **fire alert pattern**
- PC otonom modda stable fire görünce `FIRE:ON` / `F` gönderir → 5sn yenilenmezse alarm otomatik söner
- Periyodik **STATUS heartbeat** (1sn'de bir) ve daha güvenli, satır-biriktiren parser
- READY handshake ile boot tamamlanma sinyali

**ESP32-CAM v3 yenilikleri:**
- **WiFi auto-reconnect** (non-blocking state machine)
- `/resolution?value=hd` → runtime'da framesize değişimi (YOLOv8 imgsz ile eşleştirilebilir)
- Stream artificial delay azaltıldı → kameranın doğal FPS limiti devreye girer
- Tüm endpointlerde CORS başlığı (GitHub Pages canlı demo için)
- Frame fail watchdog → arka arkaya başarısız çekimde soft restart
- Heartbeat flash LED, genişletilmiş `/telemetry` (PSRAM, free heap, framesize adı)

### PC ⇄ ESP32-CAM (Wi-Fi HTTP)

```
GET /stream      → MJPEG video akışı
GET /telemetry   → {"heat_c": 45.2, ...}
GET /settings    → Kamera parametre kontrolü
```

---

## Klavye Kontrolleri

| Tuş            | Eylem                                |
|----------------|--------------------------------------|
| `m`            | Otonom / Manuel mod geçişi           |
| `w/a/s/d`      | Manuel yön kontrolü                  |
| `k / l`        | Kol indir / Kol kaldır               |
| `r`            | Video + CSV kaydı başlat/durdur      |
| `+ / -`        | Sim modunda yaklaşma zoom'u          |
| `n`            | Sim modunda yeni rastgele sahne      |
| `1`-`5`        | Sim modunda hedef sayısı             |
| `t`            | Sim modunda hareket aç/kapa          |
| `g`            | Sim modunda yangın büyümesi          |
| `q`            | Çıkış (robotu durdurur)              |

---

## Sürüm Geçmişi

Tam liste: [CHANGELOG.md](CHANGELOG.md)

### v3.1.1 — Haziran 2026 *(Mevcut)*
- **Fine-tuned model** (`fire_model_v311_mixed.pt`): sentetik+gerçek karışık eğitim, mAP50 0.93 — sentetik sahneyi YÜKSEK conf ile (0.85+) tespit ediyor
- **Yeni AI modülleri**: `heatmap.py` (yangın yoğunluk gradient'i), `distance.py` (mesafe tahmini), `webhook.py` (async bildirim), `sim_detector.py` (sentetik GT passthrough)
- **Tracker iyileştirmesi**: `stable_grace_frames` ile FSM titremesi sıfır
- **Test paketi**: 44 pytest (tracker / fuzzy / SA / config / csv / FSM / AI modülleri / scene generator)
- **Tek komutla demo**: `./run_demo.sh synthetic|webcam|esp32|stop`
- **CSV genişletildi**: `primary_distance_m`, `stable_fire`, `heatmap_max`
- **UI v3.1.1**: versiyon rozeti, model adı badge, mesafe + risk yoğunluğu göstergesi, fire-alert flash animasyonu, smooth değer geçişleri
- **Arduino düzeltmeleri**: `MIN_DRIVE_SPEED` uygulanıyor, ESP32 stream CORS

### v3.1.0 — Mayıs 2026
- **Arduino Mega v3:** Non-blocking servo sweep, fire alert LED/buzzer, STATUS heartbeat, satır-biriktiren parser, READY handshake
- **ESP32-CAM v3:** WiFi auto-reconnect, runtime framesize (`/resolution`), frame fail watchdog, tüm endpointlerde CORS, heartbeat LED
- **web_app.py v3:** Kaynak seçici (webcam | esp32 | synthetic), manuel sürüş (`/command`), `/snapshot`, `/config`, heat+voltage telemetri canlı
- **live.html v3:** Dinamik conf threshold tick'i, heat & voltage göstergesi, klavye + on-screen manuel sürüş paneli, gerçek snapshot indirme, kaynak değiştirici
- **pc_vision_controller:** Otonom modda stable-fire görünce Arduino'ya `F` sinyali (rate-limited, 3sn refresh), Arduino STATUS heartbeat parse, READY handshake, temiz kapanışta `N` ile alarmı söndürme

### v3.0.0 — Mayıs 2026
- Tam refactor: `ai/`, `sim/`, `utils/`, `configs/` modüllerine bölündü
- **YAML konfigürasyon sistemi** — tüm parametreler tek yerde
- **Eğitim pipeline'ı**: D-Fire + FASDD indirici, güçlü hyperparametre konfigi
- **Evaluation modülü**: mAP/PR/F1 grafikleri, FPS testi, batch predict
- **Sentetik yangın sahnesi simülatörü** — donanımsız tam sistem testi
- **IoU multi-target tracker** — kararlı hedef seçimi, titreme önleme
- **CSV telemetri logu** — frame bazlı tam kayıt
- **Komut yumuşatma** — oy çokluğu ile motor kararlılığı
- Conf threshold 0.20 → 0.40 (false-positive azaltma)
- Smoke vs fire öncelik ayrımı (`smoke_priority_factor`)

### v2.0.0 — Mart 2026
- YOLOv8 AI entegrasyonu (HSV renk filtresi atıldı)
- Animasyonlu HUD, target lock overlay

### v1.0.0 — Şubat 2026
- İlk sürüm: HSV renk tespiti, durum makinesi, ESP32-CAM stream, Arduino motor kontrolü

---

## Lisans

Akademik / kişisel kullanım. Üçüncü taraf modeller (D-Fire, FASDD, YOLOv8 ağırlıkları) kendi lisanslarına tabidir.
