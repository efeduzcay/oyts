/*
 * ============================================================
 *  mega_robot_l298n.ino  —  Yangın Tespit Robotu / Arduino Mega
 *  GELİŞTİRİLMİŞ SÜRÜM v3  (YOLOv8 entegrasyon hazır)
 * ============================================================
 *
 *  ⚠️ GÜÇ NOTU:
 *    Tüm GND'ler ortak olmalı (Mega + L298N + LiPo negatif)
 *    Servolar mümkünse AYRI 5V regülatörden beslensin.
 *
 *  Motor Bağlantısı:
 *    Sol 2 motor paralel → L298N OUT1/OUT2 (Kanal A)
 *    Sağ 2 motor paralel → L298N OUT3/OUT4 (Kanal B)
 *
 *  Voltaj Ölçümü:
 *    3S LiPo → Voltaj bölücü (R1=30kΩ, R2=10kΩ) → A0
 *    Bölücü oranı R2/(R1+R2) = 0.25 → 12.6V max → A0'da ~3.15V
 *
 *  v3 yenilikleri:
 *    • Non-blocking servo sweep — kontrol döngüsü hiç durmaz
 *    • PC'den 'F' / FIRE:ON komutu → fire-alert LED + buzzer pattern
 *    • Periyodik STATUS heartbeat (durum, hız, voltaj, kol açısı)
 *    • Satır biriktirme tabanlı seri parser (kısmi paketler güvenli)
 *    • Watchdog: komut zaman aşımında STOP + LED uyarı
 *    • ACK'lar tek format: ACK:<NAME>[:DETAY]
 *    • READY satırıyla boot sonrası PC handshake
 * ============================================================
 */

#include <Servo.h>

// L298N Pin Tanımları
#define ENA_PIN   9   // Kanal A PWM  — sol motorlar
#define IN1_PIN  22   // Kanal A yön
#define IN2_PIN  23   // Kanal A yön
#define ENB_PIN  10   // Kanal B PWM  — sağ motorlar
#define IN3_PIN  24   // Kanal B yön
#define IN4_PIN  25   // Kanal B yön

// Servo Pin Tanımları
#define SERVO_ARM_PIN   11
#define SERVO_GRIP_PIN  12
#define HAS_GRIP_SERVO  false   // tutucu servo varsa true yap

// Bildirim / Alarm Pinleri
#define FIRE_LED_PIN    13      // Mega built-in LED (görsel alarm)
#define BUZZER_PIN       8      // Aktif buzzer (-) GND'ye, (+) D8'e
#define HAS_BUZZER       false  // Buzzer takılıysa true yap

// Servo Açıları
#define ARM_UP_ANGLE      160
#define ARM_DOWN_ANGLE     30
#define GRIP_OPEN_ANGLE    90
#define GRIP_CLOSE_ANGLE   10

// Non-blocking Servo Sweep
#define SWEEP_STEP_DEG   2     // Her adım kaç derece
#define SWEEP_STEP_MS   12     // Adımlar arası bekleme (ms)

// Voltaj Ölçümü
#define VOLT_PIN          A0
#define VOLT_DIVIDER     4.0f   // (R1+R2)/R2 = (30k+10k)/10k
#define VOLT_REPORT_MS   2000   // Voltaj seri rapor aralığı
#define VOLT_LOW_THRESH   9.9f  // Bu voltajın altında uyarı ver (3S LiPo)

// Hız & Zaman Aşımı
#define DEFAULT_SPEED     180
#define MAX_SPEED         255
#define MIN_DRIVE_SPEED    60   // motor sürtünmesini yenmek için alt limit
#define TIMEOUT_MS        500   // ms – komut gelmezse STOP
#define STATUS_REPORT_MS  1000  // ms – STATUS heartbeat aralığı

// Fire Alert Pattern
#define ALERT_BLINK_MS     180  // LED yanıp-sönme periyodu
#define ALERT_BUZZ_MS      120  // Buzzer pulse süresi
#define ALERT_AUTO_OFF_MS 5000  // 5sn yeni FIRE sinyali gelmezse alarm kapat

// Objeler & Durum
Servo servoArm;
Servo servoGrip;

unsigned long lastCmdMs    = 0;
unsigned long lastVoltMs   = 0;
unsigned long lastStatusMs = 0;
int  currentSpeed          = DEFAULT_SPEED;
bool stopped               = true;
char lastCmdName[12]       = "BOOT";   // STATUS satırında raporlanır

// Non-blocking servo sweep state
struct SweepState {
  Servo* srv;
  int   target;
  int   step;
  unsigned long nextMs;
  bool  active;
};
SweepState armSweep  = {nullptr, ARM_UP_ANGLE, 0, 0, false};
SweepState gripSweep = {nullptr, GRIP_OPEN_ANGLE, 0, 0, false};

// Fire alert state
bool         alertActive    = false;
unsigned long alertLastSig  = 0;
unsigned long alertBlinkMs  = 0;
unsigned long alertBuzzMs   = 0;
bool         alertLedOn     = false;
bool         alertBuzOn     = false;

// Serial line buffer
const uint8_t LINE_BUF_MAX  = 96;
char    lineBuf[LINE_BUF_MAX];
uint8_t lineLen = 0;

// Voltaj filtresi (basit IIR)
float voltageFilt = 0.0f;

// Motor Kontrol
void setMotors(int leftDir, int rightDir, int spd) {
  spd = constrain(spd, 0, MAX_SPEED);
  // Sürtünmeyi yenmek için: 0 değilse en az MIN_DRIVE_SPEED.
  // PC tarafı yanlışlıkla çok düşük SPD gönderirse motor uğuldar, hareket etmez.
  if (spd > 0 && spd < MIN_DRIVE_SPEED) spd = MIN_DRIVE_SPEED;
  // Kanal A (sol)
  if      (leftDir > 0) { digitalWrite(IN1_PIN, HIGH); digitalWrite(IN2_PIN, LOW);  }
  else if (leftDir < 0) { digitalWrite(IN1_PIN, LOW);  digitalWrite(IN2_PIN, HIGH); }
  else                  { digitalWrite(IN1_PIN, LOW);  digitalWrite(IN2_PIN, LOW);  }
  // Kanal B (sağ)
  if      (rightDir > 0) { digitalWrite(IN3_PIN, HIGH); digitalWrite(IN4_PIN, LOW);  }
  else if (rightDir < 0) { digitalWrite(IN3_PIN, LOW);  digitalWrite(IN4_PIN, HIGH); }
  else                   { digitalWrite(IN3_PIN, LOW);  digitalWrite(IN4_PIN, LOW);  }

  analogWrite(ENA_PIN, (leftDir  == 0) ? 0 : spd);
  analogWrite(ENB_PIN, (rightDir == 0) ? 0 : spd);
}

void stopMotors() {
  setMotors(0, 0, 0);
  stopped = true;
}

// Non-blocking Servo Sweep
// startSweep: hedef açıya doğru sweep başlat. Tick'te tek adım atar.
void startSweep(SweepState& s, Servo* srv, int toAngle) {
  if (srv == nullptr) return;
  int from = srv->read();
  toAngle = constrain(toAngle, 0, 180);
  s.srv    = srv;
  s.target = toAngle;
  s.step   = (toAngle >= from) ? SWEEP_STEP_DEG : -SWEEP_STEP_DEG;
  s.nextMs = millis();
  s.active = (from != toAngle);
}

void tickSweep(SweepState& s) {
  if (!s.active) return;
  unsigned long now = millis();
  if (now < s.nextMs) return;
  int cur = s.srv->read();
  int next = cur + s.step;
  // Hedefe ulaştık mı?
  if ((s.step > 0 && next >= s.target) ||
      (s.step < 0 && next <= s.target)) {
    s.srv->write(s.target);
    s.active = false;
    return;
  }
  s.srv->write(next);
  s.nextMs = now + SWEEP_STEP_MS;
}

// Voltaj Ölçümü
float readBattVoltage() {
  int raw = analogRead(VOLT_PIN);
  float vPin = raw * (5.0f / 1023.0f);     // Arduino Mega 5V referans
  float v = vPin * VOLT_DIVIDER;
  // Basit IIR filtre (ADC gürültüsü için)
  voltageFilt = (voltageFilt < 0.1f) ? v : (voltageFilt * 0.8f + v * 0.2f);
  return voltageFilt;
}

void reportVoltage() {
  float v = readBattVoltage();
  Serial.print(F("VOLT:"));
  Serial.println(v, 2);
  if (v < VOLT_LOW_THRESH && v > 1.0f) {   // 1V altı = sensör yok
    Serial.println(F("WARN:BATT_LOW"));
  }
}

// Heartbeat Status
// STATUS:state=...,cmd=...,spd=...,arm=...,volt=...,alert=...
void reportStatus() {
  Serial.print(F("STATUS:state="));
  Serial.print(stopped ? F("STOP") : F("RUN"));
  Serial.print(F(",cmd="));
  Serial.print(lastCmdName);
  Serial.print(F(",spd="));
  Serial.print(currentSpeed);
  Serial.print(F(",arm="));
  Serial.print(servoArm.read());
  Serial.print(F(",volt="));
  Serial.print(voltageFilt, 2);
  Serial.print(F(",alert="));
  Serial.println(alertActive ? F("1") : F("0"));
}

// Fire Alert (PC'den 'F' / FIRE:ON)
void fireAlertOn() {
  alertActive   = true;
  alertLastSig  = millis();
}

void fireAlertOff() {
  alertActive = false;
  alertLedOn  = false;
  alertBuzOn  = false;
  digitalWrite(FIRE_LED_PIN, LOW);
  if (HAS_BUZZER) digitalWrite(BUZZER_PIN, LOW);
}

void tickAlert() {
  unsigned long now = millis();
  // Otomatik kapanma — PC sinyali kesilirse alarm söner
  if (alertActive && (now - alertLastSig > ALERT_AUTO_OFF_MS)) {
    fireAlertOff();
    Serial.println(F("ACK:ALERT_OFF_TIMEOUT"));
    return;
  }
  if (!alertActive) {
    if (alertLedOn) { digitalWrite(FIRE_LED_PIN, LOW); alertLedOn = false; }
    if (HAS_BUZZER && alertBuzOn) {
      digitalWrite(BUZZER_PIN, LOW); alertBuzOn = false;
    }
    return;
  }
  // LED yanıp-sönme
  if (now - alertBlinkMs >= ALERT_BLINK_MS) {
    alertBlinkMs = now;
    alertLedOn = !alertLedOn;
    digitalWrite(FIRE_LED_PIN, alertLedOn ? HIGH : LOW);
  }
  // Buzzer pulse (kısa sinyal yangın belirteci)
  if (HAS_BUZZER) {
    if (now - alertBuzzMs >= ALERT_BUZZ_MS) {
      alertBuzzMs = now;
      alertBuzOn = !alertBuzOn;
      digitalWrite(BUZZER_PIN, alertBuzOn ? HIGH : LOW);
    }
  }
}

// Basit Komut İşleyici
void handleSimpleCmd(char cmd) {
  switch (cmd) {
    case 'W':
      setMotors(1, 1, currentSpeed); stopped = false;
      strncpy(lastCmdName, "FORWARD", sizeof(lastCmdName));
      Serial.println(F("ACK:FORWARD"));
      break;
    case 'S':
      setMotors(-1, -1, currentSpeed); stopped = false;
      strncpy(lastCmdName, "BACK", sizeof(lastCmdName));
      Serial.println(F("ACK:BACK"));
      break;
    case 'A':
      setMotors(-1, 1, currentSpeed); stopped = false;
      strncpy(lastCmdName, "LEFT", sizeof(lastCmdName));
      Serial.println(F("ACK:LEFT"));
      break;
    case 'D':
      setMotors(1, -1, currentSpeed); stopped = false;
      strncpy(lastCmdName, "RIGHT", sizeof(lastCmdName));
      Serial.println(F("ACK:RIGHT"));
      break;
    case 'X':
      stopMotors();
      strncpy(lastCmdName, "STOP", sizeof(lastCmdName));
      Serial.println(F("ACK:STOP"));
      break;
    case 'K':
      startSweep(armSweep, &servoArm, ARM_DOWN_ANGLE);
      Serial.println(F("ACK:ARM_DOWN"));
      break;
    case 'L':
      startSweep(armSweep, &servoArm, ARM_UP_ANGLE);
      Serial.println(F("ACK:ARM_UP"));
      break;
    case 'O':
      if (HAS_GRIP_SERVO) {
        startSweep(gripSweep, &servoGrip, GRIP_OPEN_ANGLE);
        Serial.println(F("ACK:GRIP_OPEN"));
      } else { Serial.println(F("ACK:GRIP_SKIP")); }
      break;
    case 'P':
      if (HAS_GRIP_SERVO) {
        startSweep(gripSweep, &servoGrip, GRIP_CLOSE_ANGLE);
        Serial.println(F("ACK:GRIP_CLOSE"));
      } else { Serial.println(F("ACK:GRIP_SKIP")); }
      break;
    case 'V':
      reportVoltage();
      break;
    case 'B':   // 'B'eat / status snapshot anında
      reportStatus();
      break;
    case 'F':   // Fire alert ON (PC stable yangın gördü)
      fireAlertOn();
      Serial.println(F("ACK:FIRE_ON"));
      break;
    case 'N':   // 'N'o-fire (alarmı kapat)
      fireAlertOff();
      Serial.println(F("ACK:FIRE_OFF"));
      break;
    default:
      // bilinmeyen tek karakter — sessiz geç (gürültü olmasın)
      break;
  }
}

// Yapısal Protokol İşleyici
// Format örnekleri:
//   CMD:FORWARD;SPD:180;ARM:UP
//   FIRE:ON
//   FIRE:OFF
//   QUERY:STATUS
void handleStructuredCmd(const char* line) {
  // Parse: key=value çiftleri ';' ile ayrılır, anahtar-değer ':' ile
  char buf[LINE_BUF_MAX];
  strncpy(buf, line, sizeof(buf) - 1);
  buf[sizeof(buf) - 1] = '\0';

  char cmdVal[16] = "";
  char armVal[8]  = "";
  char fireVal[8] = "";
  char queryVal[12] = "";
  int  spdVal = currentSpeed;

  char* tok = strtok(buf, ";");
  while (tok != nullptr) {
    char* colon = strchr(tok, ':');
    if (colon != nullptr) {
      *colon = '\0';
      const char* key = tok;
      const char* val = colon + 1;
      // basit trim (önündeki boşluk)
      while (*val == ' ') val++;
      if      (strcasecmp(key, "CMD") == 0)  strncpy(cmdVal,  val, sizeof(cmdVal) - 1);
      else if (strcasecmp(key, "SPD") == 0)  spdVal = atoi(val);
      else if (strcasecmp(key, "ARM") == 0)  strncpy(armVal,  val, sizeof(armVal) - 1);
      else if (strcasecmp(key, "FIRE") == 0) strncpy(fireVal, val, sizeof(fireVal) - 1);
      else if (strcasecmp(key, "QUERY") == 0)strncpy(queryVal,val, sizeof(queryVal) - 1);
    }
    tok = strtok(nullptr, ";");
  }

  currentSpeed = constrain(spdVal, 0, MAX_SPEED);

  // FIRE komutları (CMD'den önce — bağımsız olarak işlenebilir)
  if (fireVal[0] != '\0') {
    if (strcasecmp(fireVal, "ON") == 0) {
      fireAlertOn();
      Serial.println(F("ACK:FIRE_ON"));
    } else if (strcasecmp(fireVal, "OFF") == 0) {
      fireAlertOff();
      Serial.println(F("ACK:FIRE_OFF"));
    }
  }

  // QUERY:STATUS
  if (strcasecmp(queryVal, "STATUS") == 0) {
    reportStatus();
  }

  // CMD (motor)
  if (cmdVal[0] != '\0') {
    if      (strcasecmp(cmdVal, "FORWARD") == 0) {
      setMotors( 1,  1, currentSpeed); stopped = false;
      strncpy(lastCmdName, "FORWARD", sizeof(lastCmdName));
      Serial.print(F("ACK:FORWARD SPD=")); Serial.println(currentSpeed);
    } else if (strcasecmp(cmdVal, "BACK") == 0) {
      setMotors(-1, -1, currentSpeed); stopped = false;
      strncpy(lastCmdName, "BACK", sizeof(lastCmdName));
      Serial.print(F("ACK:BACK SPD=")); Serial.println(currentSpeed);
    } else if (strcasecmp(cmdVal, "LEFT") == 0) {
      setMotors(-1,  1, currentSpeed); stopped = false;
      strncpy(lastCmdName, "LEFT", sizeof(lastCmdName));
      Serial.print(F("ACK:LEFT SPD=")); Serial.println(currentSpeed);
    } else if (strcasecmp(cmdVal, "RIGHT") == 0) {
      setMotors( 1, -1, currentSpeed); stopped = false;
      strncpy(lastCmdName, "RIGHT", sizeof(lastCmdName));
      Serial.print(F("ACK:RIGHT SPD=")); Serial.println(currentSpeed);
    } else if (strcasecmp(cmdVal, "STOP") == 0) {
      stopMotors();
      strncpy(lastCmdName, "STOP", sizeof(lastCmdName));
      Serial.println(F("ACK:STOP"));
    }
  }

  // ARM (servo)
  if (armVal[0] != '\0') {
    if      (strcasecmp(armVal, "UP")   == 0) startSweep(armSweep, &servoArm, ARM_UP_ANGLE);
    else if (strcasecmp(armVal, "DOWN") == 0) startSweep(armSweep, &servoArm, ARM_DOWN_ANGLE);
  }
}

// Serial line accumulator
// '\n' veya '\r' ile satır tamamlanır; tam satır parse edilir.
void processSerialByte(char ch) {
  if (ch == '\n' || ch == '\r') {
    if (lineLen == 0) return;
    lineBuf[lineLen] = '\0';
    lastCmdMs = millis();
    // Yapısal mı, tek karakter mi?
    if (strchr(lineBuf, ':') != nullptr) {
      handleStructuredCmd(lineBuf);
    } else if (lineLen == 1) {
      handleSimpleCmd(lineBuf[0]);
    } else {
      // tek-karakterli komutlar peşpeşe (örn "WAD")
      for (uint8_t i = 0; i < lineLen; i++) handleSimpleCmd(lineBuf[i]);
    }
    lineLen = 0;
  } else if (lineLen < LINE_BUF_MAX - 1) {
    lineBuf[lineLen++] = ch;
  } else {
    // taşma — at, sıfırla (gürültü/baud bozukluğu)
    lineLen = 0;
  }
}

// setup
void setup() {
  Serial.begin(115200);
  delay(80);
  Serial.println();
  Serial.println(F("[BOOT] Arduino Mega v3 (YOLOv8-ready) başlatılıyor..."));
  Serial.println(F("[BOOT] GND'ler ortak, servolar ayrı 5V regülatörden beslensin!"));

  pinMode(ENA_PIN, OUTPUT); pinMode(IN1_PIN, OUTPUT); pinMode(IN2_PIN, OUTPUT);
  pinMode(ENB_PIN, OUTPUT); pinMode(IN3_PIN, OUTPUT); pinMode(IN4_PIN, OUTPUT);
  pinMode(FIRE_LED_PIN, OUTPUT); digitalWrite(FIRE_LED_PIN, LOW);
  if (HAS_BUZZER) { pinMode(BUZZER_PIN, OUTPUT); digitalWrite(BUZZER_PIN, LOW); }
  stopMotors();

  servoArm.attach(SERVO_ARM_PIN);
  servoArm.write(ARM_UP_ANGLE);

  if (HAS_GRIP_SERVO) {
    servoGrip.attach(SERVO_GRIP_PIN);
    servoGrip.write(GRIP_OPEN_ANGLE);
  }

  // Self-test: kısa LED flash → görsel doğrulama
  for (uint8_t i = 0; i < 3; i++) {
    digitalWrite(FIRE_LED_PIN, HIGH); delay(80);
    digitalWrite(FIRE_LED_PIN, LOW);  delay(80);
  }

  // İlk voltaj okuması (filtreyi başlat)
  readBattVoltage();

  unsigned long now = millis();
  lastCmdMs    = now;
  lastVoltMs   = now;
  lastStatusMs = now;
  Serial.println(F("[BOOT] Hazır. Komut bekleniyor (W/A/S/D/X/K/L/O/P/V/B/F/N)"));
  Serial.println(F("[BOOT] Yapısal: CMD:FORWARD;SPD:180;ARM:UP  veya  FIRE:ON"));
  Serial.println(F("READY"));   // PC handshake için
}

// loop
void loop() {
  unsigned long now = millis();

  // 1) Seri girişi her tick'te oku — non-blocking
  while (Serial.available() > 0) {
    processSerialByte((char)Serial.read());
  }

  // 2) Zaman aşımı güvenliği
  if (!stopped && (now - lastCmdMs > TIMEOUT_MS)) {
    stopMotors();
    Serial.println(F("ACK:TIMEOUT_STOP"));
  }

  // 3) Servo sweep tick (non-blocking)
  tickSweep(armSweep);
  if (HAS_GRIP_SERVO) tickSweep(gripSweep);

  // 4) Fire-alert LED/buzzer tick
  tickAlert();

  // 5) Periyodik voltaj raporu
  if (now - lastVoltMs >= VOLT_REPORT_MS) {
    reportVoltage();
    lastVoltMs = now;
  }

  // 6) Heartbeat status
  if (now - lastStatusMs >= STATUS_REPORT_MS) {
    reportStatus();
    lastStatusMs = now;
  }
}
