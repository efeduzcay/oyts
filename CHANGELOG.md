# OYTS Sürüm Geçmişi

## v3.1.4 — 2026-06-04 *(Mevcut)*

### Tek Pencere Launcher
- **`python/launcher.py`** (yeni) — Tkinter tabanlı tek pencere arayüzü.
  Durum göstergesi (kapalı/webcam/simülasyon/orphan), 3 büyük buton
  (Kameralı / Simülasyon / Durdur), "Tarayıcıyı Aç", "Sistem Kontrolü"
  (doctor), "Log Klasörü", canlı log paneli. Backend'i subprocess olarak
  yönetir; healthz polling 3 sn'de bir.
- **`Baslat.command`** (macOS) / **`Baslat.bat`** (Windows) — tek tıkla
  launcher penceresini açar. Python auto-detect + tkinter doğrulama.
- Eski 3'lü `.command`/`.bat` dosyaları (Baslat-Kamera, Baslat-Simulasyon,
  Durdur, run_webcam.bat, run_sim.bat, stop.bat) ileri kullanım için
  **olduğu gibi duruyor**.
- **`KULLANIM.md`** güncel — tek arayüz "en kolay yol" olarak önerildi.

### Web UI: ESP32-CAM Devre Dışı Görsel İşaretleri
- `web/live.html` — ESP32 chip butonu disabled, "DONANIM YOK" rozeti,
  tooltip, çapraz çizgili devre dışı stil.
- `web/index_v311_new.html` — ESP32-CAM mimari kartı "Şu an aktif değil"
  rozeti + italic açıklama; algılama adımında pasif notu; tech-pill yarı
  saydam + "pasif" badge.
- `web/index.html` — "Görüyor" kartında ve "Donanım Birimleri" listesinde
  PASİF rozet + açıklama satırı. Mimari görünür kalıyor.

---

## v3.1.3 — 2026-06-04

### Sıfır-bilgi Kullanıcı Deneyimi
- **`Baslat-Kamera.command`** / **`Baslat-Simulasyon.command`** / **`Durdur.command`**
  (macOS, yeni) — Finder'dan çift tıklamayla açılır; Terminal'de
  hoşgeldin banner'ı + otomatik kurulum + demo + tarayıcı.
- **`python/utils/setup_env.py`** (yeni) — idempotent ilk açılış:
  eksik paketleri tespit eder, `pip install -r requirements.txt` çalıştırır,
  `fire_model.pt` yoksa yedek modelden kopyalar veya indirir. CLI:
  `python -m utils.setup_env`.
- **Doctor `--open-settings`** — kamera testi fail olunca macOS
  System Settings'i (x-apple.systempreferences) veya Windows
  Ayarlar'ı (ms-settings:privacy-webcam) otomatik açar.
- **`run_webcam.bat`** / **`run_sim.bat`** / **`run_demo.sh`** — backend
  başlamadan önce `setup_env --quiet` çağrısı; eksik paket varsa
  kullanıcı hiçbir şey yapmadan kurulur.
- **`KULLANIM.md`** (yeni) — non-tech kullanıcı için 1 sayfa Türkçe
  quickstart (mac + windows).

### Bilinen Davranış
- Kamera/mic gibi izinler programatik olarak verilemez (TCC/Privacy);
  doctor ilgili ayar panelini açar, kullanıcı tek tıkla onaylar.
- macOS Gatekeeper imzasız `.command` dosyalarını ilk açılışta
  uyarır → sağ tık → Aç ile geçilir (bir kez).

---

## v3.1.2 — 2026-06-03

### Cross-Platform Kararlılık
- **`python/utils/doctor.py`** (yeni) — preflight: Python sürümü, gerekli paketler,
  model dosyası, port doluluğu, opsiyonel kamera testi. CLI:
  `python -m utils.doctor --source webcam`. JSON çıktı `--json` ile.
- **`pc_vision_controller.webcam_failure_hint()`** — platforma göre tek
  kaynak rehberi (macOS: Privacy & Security/TCC, Windows: Gizlilik Ayarları,
  Linux: V4L2/video grubu). Eski karışık "Windows kamera izni" metni atıldı.
- **`web_app.py:_explain_open_failure`** ve **`pc_vision_controller._open_webcam_with_fallback`**
  artık ortak rehberi kullanıyor → tutarlı mesaj.

### Demo Başlatıcılar
- **`run_demo.sh`** — Python auto-detect (aktif venv → `python3` → `python` →
  `/usr/bin/python3`), webcam modunda doctor preflight çağrısı, başarısızlıkta
  synthetic fallback önerisi. `./run_demo.sh doctor` ile preflight standalone.
  Linux için `xdg-open` desteği.
- **`run_webcam.bat`** / **`run_sim.bat`** — backend başlamadan doctor preflight,
  hatalı izin/yanlış index gibi sık sorunlar erken yakalanır. Hata mesajları
  Windows Gizlilik panelinin doğru yoluna işaret eder.

### Test Paketi
- **87 pytest** (44 → 87) — tümü geçer
- `test_doctor.py` (7) — preflight check'ler
- `test_webcam_helpers.py` (+4) — platform-aware `webcam_failure_hint`

### Bilinen Davranış
- Finder veya IDE gibi non-Terminal launcher'lardan çalıştırıldığında macOS
  TCC kamera izni *o uygulamaya* (Terminal değil) ait olur. Doctor bunu açıkça
  raporlar; pratik çözüm: `./run_demo.sh webcam`'i Terminal.app içinden koş.

---

## v3.1.1 — 2026-06-01

### Yeni Modüller (`python/ai/`)
- **`heatmap.py`** → `FireHeatmap`: per-pixel risk gradient + exponential decay + HUD overlay. Düşük çözünürlükte tutulur, render'da upsample edilir.
- **`distance.py`** → `DistanceEstimator`: mono-kameradan kaba mesafe tahmini (`D = D_ref · √(A_ref / A)` + dikey eksen bias). Kalibrasyon config'ten.
- **`webhook.py`** → `WebhookNotifier`: stable-fire kenarında (False→True) async POST; rate-limit (30 sn) + non-blocking worker thread.
- **`sim_detector.py`** → `SimDetectionInjector`: sentetik FireSceneGenerator GT bbox'larını YOLO-uyumlu detection listesine çevirir (passthrough modu için).

### Eğitilmiş Yeni Model
- **`fire_model_v311_mixed.pt`** (58 MB, yolov8s) — mevcut `fire_model.pt`'in 5000 sentetik frame ile fine-tune edilmiş hali. Backbone donduruldu (freeze=10), lr0=1e-4, 8+ epoch.
- **Metrikler (val):** Precision 0.92, Recall 0.89, mAP50 **0.93**, mAP50-95 0.75
- **Sentetik tespit:** eski 0 → yeni **5 hedef @ conf 0.92** (ölçülü test)
- Eski model `fire_model_v3_real.pt` olarak korunuyor (geri dönüş için)

### Mimari & Dayanıklılık
- **`Target.bbox`** artık tracker'dan gerçek bbox taşıyor → HUD/web_app overlay'leri sahte `sqrt(area)` kare yerine gerçek kutu çiziyor.
- **`IoUTracker.stable_grace_frames`** — kısa missed gap'lerde stable target görünür kalır; FSM titremesi sıfır.
- **`VisionProcessor.external_detector`** opsiyonel → sim passthrough için (artık varsayılan **kapalı**; eğitilmiş model gerçekten görüyor).
- `_load_model` `sys.exit` yerine `FileNotFoundError` → web_app sağlıklı kapanır.
- `pc_vision_controller --max-frames N --headless` → CI/test uyumlu.
- `HardwareLink` seri port çöküşünde `arduino_ready`/fire-alert state reset.
- `web_app.py` frame işleme try/except (tek bozuk kare loop'u kıramaz).
- `web_app.py` file logger → `kayitlar/web_app.log`.

### Test Paketi (`python/tests/`)
- **44 pytest** — tümü geçer
- `test_tracker.py` (8) — IoU, promotion, grace, reset
- `test_fuzzy_sa.py` (8) — trap fonksiyonu, fuzzy priority, SA ordering
- `test_decision.py` (7) — FSM dalları
- `test_ai_modules.py` (11) — distance/heatmap/sim_detector/webhook
- `test_scene_generator.py` (5) — sentetik render smoke
- `test_config_csv.py` (5) — ConfigDict, CSVLogger

### Demo & Dağıtım
- **`run_demo.sh`** → tek komutla backend + frontend + tarayıcı. `./run_demo.sh synthetic|webcam|esp32|stop`
- **`web/serve.py`** portable (hardcoded path yok, `__file__` + `directory=`)
- **`live.html`** v3.1.1 rozeti, kırık nav linkleri düzeldi, başlangıç pill rengi doğru, Mesafe (m) + Risk Yoğunluğu (%) alanları eklendi, distance estimasyonu canlı gösteriliyor.

### Arduino Düzeltmeleri
- `mega_robot_l298n.ino`: `MIN_DRIVE_SPEED` artık uygulanıyor (motor uğurdamıyor, hareket ediyor)
- `esp32_cam_stream.ino`: `/stream` ve `/healthz` için CORS OPTIONS handler'ı eklendi

### Konfigürasyon
- Yeni bölümler (config.yaml & config_mac.yaml): `distance:`, `heatmap:`, `notify:`, `sim:`
- `tracking.stable_grace_frames` eklendi
- `ai.hsv_required/hsv_refine` sentetik için varsayılan **kapalı** (gerçek kamerada açılabilir)
- CSV header genişledi: `primary_distance_m, stable_fire, heatmap_max`
- `requirements.txt`: kullanılmayan `gdown`/`py7zr` kaldırıldı, `pytest` eklendi

---

## v3.1.0 — Mayıs 2026
- Arduino Mega v3: non-blocking servo sweep, fire alert LED/buzzer, STATUS heartbeat, satır biriktiren parser, READY handshake
- ESP32-CAM v3: WiFi auto-reconnect, runtime framesize (`/resolution`), frame fail watchdog, CORS, heartbeat LED
- web_app.py v3: kaynak seçici (webcam | esp32 | synthetic), `/command`, `/snapshot`, `/config`, heat+voltage telemetri canlı
- live.html v3: dinamik conf threshold tick, heat & voltage göstergesi, klavye + on-screen manuel sürüş, snapshot indirme, kaynak değiştirici
- pc_vision_controller: otonom modda stable-fire → Arduino `F` sinyali (rate-limited), STATUS heartbeat parse, READY handshake, temiz kapanış

## v3.0.0 — Mayıs 2026
- Tam refactor: `ai/`, `sim/`, `utils/`, `configs/` modüllerine bölündü
- YAML konfigürasyon sistemi
- Eğitim pipeline (D-Fire + FASDD indirici), evaluation modülü
- **Sentetik yangın sahnesi simülatörü** (donanımsız tam sistem testi)
- **IoU multi-target tracker** (kararlı hedef seçimi)
- CSV telemetri logu, komut yumuşatma, smoke vs fire önceliği

## v2.0.0 — Mart 2026
- YOLOv8 entegrasyonu (HSV renk filtresi atıldı)
- Animasyonlu HUD, target lock overlay

## v1.0.0 — Şubat 2026
- İlk sürüm: HSV renk tespiti, durum makinesi, ESP32-CAM stream, Arduino motor kontrolü
