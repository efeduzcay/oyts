/*
 * ============================================================
 *  esp32_cam_stream.ino  —  Yangın Tespit Robotu / ESP32-CAM
 *  GELİŞTİRİLMİŞ SÜRÜM v3  (YOLOv8 entegrasyon hazır)
 * ============================================================
 *
 *  Arduino IDE Ayarları:
 *  ─────────────────────
 *  Board           : AI Thinker ESP32-CAM
 *  PSRAM           : Enabled
 *  Partition Scheme: Huge APP (3MB No OTA / 1MB SPIFFS)
 *  CPU Frequency   : 240 MHz
 *  Upload Speed    : 115200
 *  Flash Frequency : 80 MHz
 *  Flash Size      : 4MB (32Mb)
 *
 *  Upload Adımları (CH340G):
 *  1. GPIO0 – GND bağla (BOOT modu)
 *  2. RST'ye kısa GND dokun
 *  3. Arduino IDE'den Upload
 *  4. Bitti → GPIO0 kabloyu çıkar
 *  5. RST'ye kısa GND → çalışır
 *
 *  v3 yenilikleri:
 *    • WiFi auto-reconnect (non-blocking state machine)
 *    • /resolution endpoint → runtime'da framesize değişimi
 *      (YOLOv8 imgsz'iyle dinamik eşleştirme)
 *    • Stream artificial-delay azaltıldı → kameranın
 *      doğal FPS limiti devreye girer
 *    • Tüm endpointlerde CORS başlığı (live.html için)
 *    • Frame fetch fail watchdog → N başarısız sonra soft restart
 *    • Heartbeat LED (built-in flash LED, GPIO 4)
 *    • Daha geniş /telemetry: PSRAM, free heap, framesize adı
 *
 *  Değiştirilecek Ayarlar:
 *    WIFI_SSID / WIFI_PASS
 *    USE_MLX90614 / USE_AMG8833 → sensör varsa 1 yap
 * ============================================================
 */

// Wi-Fi Ayarları
#define WIFI_SSID  "SSID_BURAYA"
#define WIFI_PASS  "SIFRE_BURAYA"

// Isı Sensörü Scaffold (kullanmıyorsan 0 bırak)
#define USE_MLX90614  0
#define USE_AMG8833   0

// Kütüphaneler
#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>   // v6 – Library Manager'dan kur

#if USE_MLX90614
  #include <Adafruit_MLX90614.h>
  Adafruit_MLX90614 mlx;
#endif
#if USE_AMG8833
  #include <Adafruit_AMG88xx.h>
  Adafruit_AMG88xx amg;
#endif

// AI Thinker ESP32-CAM Pin Tanımları
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// Built-in flash LED (heartbeat)
#define FLASH_LED_PIN      4

// Stream ayarları
#define STREAM_INTER_FRAME_DELAY_MS  5    // artık sadece WDT yorma payı
#define FRAME_FAIL_LIMIT           60     // peşpeşe bu kadar fail → soft restart
#define WIFI_RECONNECT_MS         3000    // bağlantı düşerse yeniden deneme aralığı
#define WIFI_INIT_TIMEOUT_MS     20000    // ilk açılışta WiFi için max bekleme

// Global Durum
WebServer server(80);
unsigned long lastFrameTime = 0;
unsigned long frameCount    = 0;
float fpsEst                = 0.0f;
unsigned long startMs       = 0;
unsigned long lastWifiTryMs = 0;
unsigned long lastHbMs      = 0;
uint16_t frameFailCount     = 0;
uint32_t totalStreamFrames  = 0;
bool     ledOn              = false;

// Simülasyon ısısı
float simHeat    = 30.0f;
float simHeatDir = 0.05f;

// Framesize map (string ↔ enum)
struct FsEntry { const char* name; framesize_t val; uint16_t w; uint16_t h; };
static const FsEntry FS_TABLE[] = {
  {"qvga",  FRAMESIZE_QVGA,   320,  240},
  {"cif",   FRAMESIZE_CIF,    352,  288},
  {"vga",   FRAMESIZE_VGA,    640,  480},
  {"svga",  FRAMESIZE_SVGA,   800,  600},
  {"xga",   FRAMESIZE_XGA,   1024,  768},
  {"hd",    FRAMESIZE_HD,    1280,  720},
  {"sxga",  FRAMESIZE_SXGA,  1280, 1024},
  {"uxga",  FRAMESIZE_UXGA,  1600, 1200},
};
static const uint8_t FS_TABLE_LEN = sizeof(FS_TABLE) / sizeof(FS_TABLE[0]);

const FsEntry* findFs(const char* n) {
  for (uint8_t i = 0; i < FS_TABLE_LEN; i++)
    if (strcasecmp(n, FS_TABLE[i].name) == 0) return &FS_TABLE[i];
  return nullptr;
}
const FsEntry* findFsByEnum(framesize_t e) {
  for (uint8_t i = 0; i < FS_TABLE_LEN; i++)
    if (FS_TABLE[i].val == e) return &FS_TABLE[i];
  return nullptr;
}

// HTML Ana Sayfa
const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html><html><head>
<meta charset="UTF-8">
<title>ESP32-CAM Robot Stream v3</title>
<style>
  body{background:#111;color:#eee;font-family:sans-serif;text-align:center;padding:20px}
  a{color:#4af;display:block;margin:8px 0;font-size:1.1em}
  img{max-width:720px;border:2px solid #4af;display:block;margin:10px auto}
  .ctrl{margin:14px 0}
  input[type=range]{width:200px}
  select{padding:4px 8px;border-radius:4px}
  label{display:inline-block;width:120px;text-align:right;margin-right:8px}
  button{background:#0047AB;color:#fff;border:0;padding:8px 14px;border-radius:6px;cursor:pointer}
</style>
</head><body>
<h2>🔥 Yangın Tespit Robotu — ESP32-CAM v3</h2>
<img src="/stream" alt="MJPEG Stream">
<div class="ctrl">
  <label>Çözünürlük:</label>
  <select id="fs" onchange="fetch('/resolution?value='+this.value)">
    <option value="qvga">QVGA 320x240</option>
    <option value="vga" selected>VGA 640x480</option>
    <option value="svga">SVGA 800x600</option>
    <option value="hd">HD 1280x720</option>
    <option value="uxga">UXGA 1600x1200</option>
  </select>
</div>
<div class="ctrl">
  <label>Parlaklık:</label>
  <input type="range" id="br" min="-2" max="2" value="0" oninput="setSetting('brightness',this.value)">
  <span id="brv">0</span>
</div>
<div class="ctrl">
  <label>JPEG Kalite:</label>
  <input type="range" id="ql" min="4" max="63" value="12" oninput="setSetting('quality',this.value)">
  <span id="qlv">12</span>
</div>
<div class="ctrl">
  <button onclick="fetch('/snapshot').then(r=>r.blob()).then(b=>{let a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='snap.jpg';a.click()})">📸 Snapshot Al</button>
</div>
<a href="/telemetry">/telemetry — JSON</a>
<script>
function setSetting(k,v){
  document.getElementById(k=='brightness'?'brv':'qlv').textContent=v;
  fetch('/settings?'+k+'='+v);
}
</script>
</body></html>
)rawliteral";

// CORS yardımcısı
void sendCors() {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
}

void handleOptions() {
  sendCors();
  server.send(204);
}

// Kamera Başlatma
bool initCamera() {
  camera_config_t cfg;
  cfg.ledc_channel = LEDC_CHANNEL_0;
  cfg.ledc_timer   = LEDC_TIMER_0;
  cfg.pin_d0  = Y2_GPIO_NUM; cfg.pin_d1 = Y3_GPIO_NUM;
  cfg.pin_d2  = Y4_GPIO_NUM; cfg.pin_d3 = Y5_GPIO_NUM;
  cfg.pin_d4  = Y6_GPIO_NUM; cfg.pin_d5 = Y7_GPIO_NUM;
  cfg.pin_d6  = Y8_GPIO_NUM; cfg.pin_d7 = Y9_GPIO_NUM;
  cfg.pin_xclk     = XCLK_GPIO_NUM;
  cfg.pin_pclk     = PCLK_GPIO_NUM;
  cfg.pin_vsync    = VSYNC_GPIO_NUM;
  cfg.pin_href     = HREF_GPIO_NUM;
  cfg.pin_sscb_sda = SIOD_GPIO_NUM;
  cfg.pin_sscb_scl = SIOC_GPIO_NUM;
  cfg.pin_pwdn     = PWDN_GPIO_NUM;
  cfg.pin_reset    = RESET_GPIO_NUM;
  cfg.xclk_freq_hz = 20000000;
  cfg.pixel_format = PIXFORMAT_JPEG;

  if (psramFound()) {
    cfg.frame_size   = FRAMESIZE_VGA;   // başlangıç; runtime'da değiştirilebilir
    cfg.jpeg_quality = 12;
    cfg.fb_count     = 2;
    Serial.println(F("[CAM] PSRAM bulundu – VGA (640x480) başlangıç"));
  } else {
    cfg.frame_size   = FRAMESIZE_CIF;
    cfg.jpeg_quality = 20;
    cfg.fb_count     = 1;
    Serial.println(F("[CAM] PSRAM yok – CIF (352x288)"));
  }

  esp_err_t err = esp_camera_init(&cfg);
  if (err != ESP_OK) {
    Serial.printf("[CAM] HATA 0x%x\n", err);
    return false;
  }
  Serial.println(F("[CAM] Kamera başlatıldı."));
  return true;
}

// Isı Okuma
float readHeat() {
#if USE_MLX90614
  return mlx.readObjectTempC();
#elif USE_AMG8833
  float px[64]; amg.readPixels(px);
  float mx = -999;
  for (int i=0;i<64;i++) if(px[i]>mx) mx=px[i];
  return mx;
#else
  simHeat += simHeatDir;
  if (simHeat > 35.0f) simHeatDir = -0.03f;
  if (simHeat < 27.0f) simHeatDir =  0.03f;
  return simHeat;
#endif
}

// /settings Handler
void handleSettings() {
  sensor_t* s = esp_camera_sensor_get();
  bool changed = false;

  if (server.hasArg("brightness")) {
    int v = server.arg("brightness").toInt();
    s->set_brightness(s, constrain(v, -2, 2));
    changed = true;
  }
  if (server.hasArg("quality")) {
    int v = server.arg("quality").toInt();
    s->set_quality(s, constrain(v, 4, 63));
    changed = true;
  }
  if (server.hasArg("contrast")) {
    int v = server.arg("contrast").toInt();
    s->set_contrast(s, constrain(v, -2, 2));
    changed = true;
  }
  if (server.hasArg("saturation")) {
    int v = server.arg("saturation").toInt();
    s->set_saturation(s, constrain(v, -2, 2));
    changed = true;
  }
  if (server.hasArg("hmirror")) {
    s->set_hmirror(s, server.arg("hmirror").toInt() ? 1 : 0);
    changed = true;
  }
  if (server.hasArg("vflip")) {
    s->set_vflip(s, server.arg("vflip").toInt() ? 1 : 0);
    changed = true;
  }

  sendCors();
  server.send(200, "application/json",
    changed ? "{\"ok\":true}" : "{\"ok\":false,\"msg\":\"Parametre bulunamadi\"}");
}

// /resolution Handler
// /resolution?value=hd  veya  /resolution?w=1280&h=720 (en yakını)
void handleResolution() {
  sensor_t* s = esp_camera_sensor_get();
  const FsEntry* sel = nullptr;
  if (server.hasArg("value")) {
    sel = findFs(server.arg("value").c_str());
  } else if (server.hasArg("w") && server.hasArg("h")) {
    int w = server.arg("w").toInt();
    long best = LONG_MAX;
    for (uint8_t i = 0; i < FS_TABLE_LEN; i++) {
      long d = (long)abs((int)FS_TABLE[i].w - w);
      if (d < best) { best = d; sel = &FS_TABLE[i]; }
    }
  }
  sendCors();
  if (sel == nullptr) {
    server.send(400, "application/json",
      "{\"ok\":false,\"msg\":\"value veya w/h gerekli\"}");
    return;
  }
  if (s->set_framesize(s, sel->val) != 0) {
    server.send(500, "application/json", "{\"ok\":false,\"msg\":\"set_framesize basarisiz\"}");
    return;
  }
  String resp = String("{\"ok\":true,\"value\":\"") + sel->name +
                "\",\"w\":" + sel->w + ",\"h\":" + sel->h + "}";
  server.send(200, "application/json", resp);
}

// /snapshot Handler
void handleSnapshot() {
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    sendCors();
    server.send(503, "text/plain", "Kare alinamadi");
    return;
  }
  server.sendHeader("Content-Disposition", "inline; filename=snap.jpg");
  sendCors();
  server.send_P(200, "image/jpeg", (const char*)fb->buf, fb->len);
  esp_camera_fb_return(fb);
}

// /stream Handler
void handleStream() {
  WiFiClient client = server.client();
  String boundary = "FrameBoundary";
  client.print("HTTP/1.1 200 OK\r\n");
  client.print("Access-Control-Allow-Origin: *\r\n");
  client.print("Cache-Control: no-cache, no-store, must-revalidate\r\n");
  client.print("Pragma: no-cache\r\n");
  client.print("Content-Type: multipart/x-mixed-replace;boundary=" + boundary + "\r\n\r\n");

  while (client.connected()) {
    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) {
      frameFailCount++;
      if (frameFailCount > FRAME_FAIL_LIMIT) {
        Serial.println(F("[STREAM] Çok fazla frame fail → ESP restart"));
        delay(150);
        ESP.restart();
      }
      delay(20);
      continue;
    }
    frameFailCount = 0;
    totalStreamFrames++;

    // FPS tahmin
    unsigned long now = millis();
    frameCount++;
    if (now - lastFrameTime >= 1000) {
      fpsEst = (float)frameCount * 1000.0f / (now - lastFrameTime);
      frameCount = 0;
      lastFrameTime = now;
    }

    client.print("--" + boundary + "\r\n");
    client.print("Content-Type: image/jpeg\r\n");
    client.printf("Content-Length: %u\r\n\r\n", fb->len);
    client.write(fb->buf, fb->len);
    client.print("\r\n");
    esp_camera_fb_return(fb);

    // Çok kısa gevşeme — WDT için, gerçek fps'i camera limitlasın
    if (STREAM_INTER_FRAME_DELAY_MS) delay(STREAM_INTER_FRAME_DELAY_MS);
  }
}

// /telemetry Handler
void handleTelemetry() {
  sensor_t* s = esp_camera_sensor_get();
  framesize_t fs = (framesize_t)s->status.framesize;
  const FsEntry* fe = findFsByEnum(fs);

  StaticJsonDocument<512> doc;
  doc["ip"]             = WiFi.localIP().toString();
  doc["rssi"]           = WiFi.RSSI();
  doc["wifi_status"]    = (int)WiFi.status();
  doc["uptime_ms"]      = millis() - startMs;
  doc["frame_w"]        = fe ? fe->w : 0;
  doc["frame_h"]        = fe ? fe->h : 0;
  doc["framesize"]      = fe ? fe->name : "unknown";
  doc["fps_est"]        = fpsEst;
  doc["heat_c"]         = readHeat();
  doc["psram_found"]    = (bool)psramFound();
  doc["free_heap"]      = (uint32_t)ESP.getFreeHeap();
  doc["total_frames"]   = totalStreamFrames;
  doc["frame_fail"]     = frameFailCount;
  doc["jpeg_quality"]   = (int)s->status.quality;
  doc["brightness"]     = (int)s->status.brightness;

  String out; serializeJson(doc, out);
  sendCors();
  server.send(200, "application/json", out);
}

// /healthz
void handleHealth() {
  sendCors();
  server.send(200, "application/json", "{\"ok\":true}");
}

// WiFi Bağlantı (non-blocking yeniden bağlanma için)
bool wifiConnectBlocking(uint32_t timeoutMs) {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);             // stream gecikmesi azalır
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  uint32_t t0 = millis();
  Serial.printf("[WIFI] Bağlanılıyor: %s ", WIFI_SSID);
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - t0 > timeoutMs) {
      Serial.println(F("\n[WIFI] timeout"));
      return false;
    }
    Serial.print(".");
    delay(300);
  }
  Serial.println();
  Serial.print(F("[WIFI] OK  IP: "));
  Serial.println(WiFi.localIP());
  return true;
}

void tickWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  unsigned long now = millis();
  if (now - lastWifiTryMs < WIFI_RECONNECT_MS) return;
  lastWifiTryMs = now;
  Serial.println(F("[WIFI] Düştü → reconnect deneniyor..."));
  WiFi.disconnect();
  WiFi.reconnect();
}

// Heartbeat LED
void tickHeartbeat() {
  unsigned long now = millis();
  // WiFi yoksa hızlı blink, varsa yavaş nefes
  uint16_t period = (WiFi.status() == WL_CONNECTED) ? 1500 : 250;
  if (now - lastHbMs >= period) {
    lastHbMs = now;
    ledOn = !ledOn;
    // Built-in flash LED parlak — kısa pulse yeter
    digitalWrite(FLASH_LED_PIN, ledOn ? HIGH : LOW);
  }
}

// setup
void setup() {
  Serial.begin(115200);
  delay(80);
  Serial.println();
  Serial.println(F("[BOOT] ESP32-CAM v3 (YOLOv8-ready) başlatılıyor..."));
  startMs = millis();

  pinMode(FLASH_LED_PIN, OUTPUT);
  digitalWrite(FLASH_LED_PIN, LOW);

  if (!initCamera()) { while(true) delay(1000); }

#if USE_MLX90614
  if (!mlx.begin()) Serial.println(F("[SENSOR] MLX90614 bulunamadı!"));
  else              Serial.println(F("[SENSOR] MLX90614 hazır."));
#endif
#if USE_AMG8833
  if (!amg.begin()) Serial.println(F("[SENSOR] AMG8833 bulunamadı!"));
  else              Serial.println(F("[SENSOR] AMG8833 hazır."));
#endif

  if (!wifiConnectBlocking(WIFI_INIT_TIMEOUT_MS)) {
    Serial.println(F("[WIFI] BAĞLANAMADI – AP modu yok, runtime'da yeniden denenecek"));
  }

  String ip = WiFi.localIP().toString();
  Serial.println(F("─────────────────────────────────────"));
  Serial.printf("  http://%s/\n",            ip.c_str());
  Serial.printf("  http://%s/stream\n",      ip.c_str());
  Serial.printf("  http://%s/telemetry\n",   ip.c_str());
  Serial.printf("  http://%s/snapshot\n",    ip.c_str());
  Serial.printf("  http://%s/settings?brightness=1&quality=10\n", ip.c_str());
  Serial.printf("  http://%s/resolution?value=hd\n", ip.c_str());
  Serial.println(F("─────────────────────────────────────"));

  // Endpoint routing
  server.on("/",            HTTP_GET,  [](){ server.send_P(200, "text/html", INDEX_HTML); });
  server.on("/index",       HTTP_GET,  [](){ server.send_P(200, "text/html", INDEX_HTML); });
  server.on("/stream",      HTTP_GET,  handleStream);
  server.on("/snapshot",    HTTP_GET,  handleSnapshot);
  server.on("/telemetry",   HTTP_GET,  handleTelemetry);
  server.on("/settings",    HTTP_GET,  handleSettings);
  server.on("/resolution",  HTTP_GET,  handleResolution);
  server.on("/healthz",     HTTP_GET,  handleHealth);

  // CORS preflight
  server.on("/snapshot",    HTTP_OPTIONS, handleOptions);
  server.on("/telemetry",   HTTP_OPTIONS, handleOptions);
  server.on("/settings",    HTTP_OPTIONS, handleOptions);
  server.on("/resolution",  HTTP_OPTIONS, handleOptions);
  server.on("/stream",      HTTP_OPTIONS, handleOptions);
  server.on("/healthz",     HTTP_OPTIONS, handleOptions);

  // 404 → tek ortak handler
  server.onNotFound([](){
    sendCors();
    server.send(404, "application/json", "{\"ok\":false,\"msg\":\"not found\"}");
  });

  server.begin();
  Serial.println(F("[HTTP] Sunucu başlatıldı."));
  lastFrameTime = millis();
  lastWifiTryMs = millis();
  lastHbMs      = millis();
}

void loop() {
  server.handleClient();
  tickWifi();
  tickHeartbeat();
}
