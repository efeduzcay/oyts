// build_pptx.js — OYTS Sunumu (18+1 slayt) pptxgenjs ile üretir
// Çıktı: /Users/efeduzcay/Desktop/robot-3.0.0/sunum/OYTS_Sunum.pptx

const pptxgen = require("pptxgenjs");

const ROOT = "/Users/efeduzcay/Desktop/robot-3.0.0";
const OUT = ROOT + "/sunum/OYTS_Sunum.pptx";

// Renk paleti
const C = {
  navy:    "001F4D",  // koyu mavi (hero arka plan)
  blue:    "0047AB",  // ana mavi
  orange:  "FF6B35",  // vurgu turuncu
  bg:      "F8FAFF",  // light arka plan
  card:    "FFFFFF",  // beyaz kart
  text:    "1A202C",  // koyu metin
  muted:   "64748B",  // ikincil gri
  faint:   "94A3B8",  // soluk gri
  green:   "16A34A",
  red:     "DC2626",
  amber:   "F59E0B",
  border:  "E2E8F0",  // ince çizgi
};

const FONT_TITLE = "Calibri";
const FONT_BODY  = "Calibri";

// Setup
const p = new pptxgen();
p.layout = "LAYOUT_16x9";   // 10" x 5.625"
p.author = "Sema Nur Işık & Efe Düzçay";
p.title = "OYTS — Otonom Yangın Tespit Sistemi";
p.subject = "Piri Reis Üniversitesi BIP 2012 Bitirme Projesi";

const W = 10, H = 5.625;

// Yardımcı helpers
function lightBg(slide) { slide.background = { color: C.bg }; }
function darkBg(slide)  { slide.background = { color: C.navy }; }

// Sayfa üstüne küçük section eyebrow (turuncu, büyük harf)
function eyebrow(slide, text, x = 0.5, y = 0.4) {
  slide.addText(text.toUpperCase(), {
    x, y, w: 9, h: 0.3, fontSize: 11, bold: true,
    color: C.orange, charSpacing: 4, fontFace: FONT_BODY,
  });
}

// Büyük başlık
function bigTitle(slide, text, y = 0.7) {
  slide.addText(text, {
    x: 0.5, y, w: 9, h: 0.7, fontSize: 32, bold: true,
    color: C.text, fontFace: FONT_TITLE,
  });
}

// Footer (her slaytta sayfa no + proje adı)
function footer(slide, n, total = 19) {
  slide.addText(`OYTS · v3.1.1`, {
    x: 0.5, y: H - 0.3, w: 4, h: 0.25,
    fontSize: 9, color: C.faint, fontFace: FONT_BODY,
  });
  slide.addText(`${n} / ${total}`, {
    x: W - 1.2, y: H - 0.3, w: 0.7, h: 0.25,
    fontSize: 9, color: C.faint, align: "right", fontFace: FONT_BODY,
  });
}

// Kart shadow (mutate sorunu için fresh obj)
const cardShadow = () => ({
  type: "outer", color: "000000", blur: 8, offset: 2, angle: 90, opacity: 0.10,
});

// SLAYT 1 — KAPAK
{
  const s = p.addSlide();
  darkBg(s);

  // Sol blok — başlık
  s.addText("🔥", {
    x: 0.5, y: 1.3, w: 1.2, h: 1.2, fontSize: 80, color: C.orange,
  });
  s.addText("OYTS", {
    x: 0.5, y: 2.5, w: 6, h: 1.0, fontSize: 72, bold: true,
    color: "FFFFFF", fontFace: FONT_TITLE,
  });
  s.addText("Otonom Yangın Tespit Sistemi", {
    x: 0.5, y: 3.5, w: 7, h: 0.5, fontSize: 22,
    color: "FFFFFF", fontFace: FONT_TITLE, italic: true,
  });
  s.addText("YOLOv8  •  Bulanık Mantık  •  Simulated Annealing", {
    x: 0.5, y: 4.1, w: 8, h: 0.4, fontSize: 14,
    color: "CADCFC", charSpacing: 2, fontFace: FONT_BODY,
  });

  // Sağ alt — bilgi rozeti
  s.addShape(p.shapes.RECTANGLE, {
    x: W - 3.5, y: H - 1.5, w: 3.0, h: 1.0,
    fill: { color: "FFFFFF", transparency: 88 },
    line: { color: "FFFFFF", width: 0.5 },
  });
  s.addText([
    { text: "Piri Reis Üniversitesi", options: { bold: true, color: "FFFFFF", fontSize: 13, breakLine: true } },
    { text: "BIP 2012 · Bitirme Projesi", options: { color: "CADCFC", fontSize: 11, breakLine: true } },
    { text: "Sema Nur Işık & Efe Düzçay", options: { color: "FFFFFF", fontSize: 11, italic: true } },
  ], { x: W - 3.4, y: H - 1.4, w: 2.9, h: 0.9, margin: 0, fontFace: FONT_BODY });

  // Sürüm pill
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x: 0.5, y: 0.5, w: 1.5, h: 0.35, rectRadius: 0.18,
    fill: { color: C.orange }, line: { color: C.orange, width: 0 },
  });
  s.addText("v3.1.1", {
    x: 0.5, y: 0.5, w: 1.5, h: 0.35, fontSize: 11, bold: true,
    color: "FFFFFF", align: "center", valign: "middle", fontFace: FONT_BODY, margin: 0,
  });

  s.addNotes("Sunuma hoş geldiniz mesajıyla başlayın. Proje adı, üniversite ve ekip üyeleri vurgulayın. 'Bu projemiz BIP 2012 kapsamında geliştirdiğimiz otonom bir yangın tespit ve müdahale robotudur.' diyebilirsiniz. Süre: ~30 sn.");
}

// SLAYT 2 — PROJE TANITIMI
{
  const s = p.addSlide();
  lightBg(s);
  eyebrow(s, "Proje Tanıtımı");
  bigTitle(s, "Proje Nedir?");

  // Sol: 3 ana madde
  const items = [
    { ico: "🤖", h: "Otonom Robot", t: "Yangınları erken evrede tespit eden ve müdahale eden 3 katmanlı gömülü sistem" },
    { ico: "👁", h: "İnsan Bağımsız", t: "Sürekli izleme, karar verme ve müdahale — operatör gerekmez" },
    { ico: "🧠", h: "Akıllı Karar", t: "YOLOv8 + Bulanık Mantık + Simulated Annealing entegrasyonu" },
  ];
  items.forEach((it, i) => {
    const y = 1.8 + i * 0.95;
    s.addText(it.ico, { x: 0.5, y, w: 0.6, h: 0.7, fontSize: 28 });
    s.addText(it.h, { x: 1.15, y, w: 4.5, h: 0.35, fontSize: 16, bold: true, color: C.text, fontFace: FONT_TITLE });
    s.addText(it.t, { x: 1.15, y: y + 0.35, w: 4.5, h: 0.55, fontSize: 11, color: C.muted, fontFace: FONT_BODY });
  });

  // Sağ: 4 büyük istatistik kart
  const stats = [
    { n: "6.027", l: "satır Python kodu",  c: C.blue },
    { n: "1.034", l: "satır Arduino C++",  c: C.orange },
    { n: "50/50", l: "birim test geçer",   c: C.green },
    { n: "0.93",  l: "mAP50 (sentetik)",    c: C.amber },
  ];
  const sw = 1.85, sh = 1.5, sx = 5.9, sy = 1.7, gap = 0.15;
  stats.forEach((st, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = sx + col * (sw + gap), y = sy + row * (sh + gap);
    s.addShape(p.shapes.RECTANGLE, {
      x, y, w: sw, h: sh, fill: { color: C.card },
      line: { color: C.border, width: 0.5 }, shadow: cardShadow(),
    });
    s.addText(st.n, {
      x, y: y + 0.1, w: sw, h: 0.85, fontSize: 36, bold: true,
      color: st.c, align: "center", valign: "middle",
      fontFace: FONT_TITLE, margin: 0,
    });
    s.addText(st.l, {
      x, y: y + 0.95, w: sw, h: 0.45, fontSize: 11,
      color: C.muted, align: "center", valign: "top",
      fontFace: FONT_BODY, margin: 0,
    });
  });

  footer(s, 2);
  s.addNotes("Projemiz konferans salonu, depo, benzin istasyonu gibi yerlerde gece-gündüz devriye gezen bir robot. 7 bin satırı aşan kod ve 50 otomatik test ile profesyonel yazılım kalitesi hedefledik. Süre: ~40 sn.");
}

// SLAYT 3 — SORUN
{
  const s = p.addSlide();
  lightBg(s);
  eyebrow(s, "Sorun");
  bigTitle(s, "Yangın Neden Geç Tespit Edilir?");

  s.addText("Klasik sistemler dakikalar sonra tetiklenir; insan izlemeli; sabit nokta körlüğü var.", {
    x: 0.5, y: 1.45, w: 9, h: 0.4, fontSize: 13,
    color: C.muted, italic: true, fontFace: FONT_BODY,
  });

  // 3 sorun kartı
  const probs = [
    { ico: "⏱", h: "Geç Tespit", t: "Klasik duman dedektörleri alev sahneye çıktıktan sonra tetiklenir. Yangın yayılmış olur.", c: C.red },
    { ico: "👤", h: "İnsan Bağımlılığı", t: "CCTV sistemi varsa bile gece veya mesai dışında izleyen olmaz.", c: C.orange },
    { ico: "📍", h: "Sabit Nokta Körlüğü", t: "Sabit kameralar açı dışını göremez. Hareketli bir göz gerekli.", c: C.amber },
  ];
  const cw = 2.95, ch = 2.7, gap = 0.1;
  probs.forEach((it, i) => {
    const x = 0.5 + i * (cw + gap), y = 2.2;
    s.addShape(p.shapes.RECTANGLE, {
      x, y, w: cw, h: ch, fill: { color: C.card },
      line: { color: C.border, width: 0.5 }, shadow: cardShadow(),
    });
    // Üst aksan barı (sol)
    s.addShape(p.shapes.RECTANGLE, {
      x, y, w: 0.08, h: ch, fill: { color: it.c }, line: { color: it.c, width: 0 },
    });
    s.addText(it.ico, { x: x + 0.25, y: y + 0.25, w: 0.6, h: 0.6, fontSize: 30 });
    s.addText(it.h, { x: x + 0.25, y: y + 0.9, w: cw - 0.5, h: 0.4, fontSize: 17, bold: true, color: C.text, fontFace: FONT_TITLE });
    s.addText(it.t, { x: x + 0.25, y: y + 1.4, w: cw - 0.5, h: 1.2, fontSize: 12, color: C.muted, fontFace: FONT_BODY });
  });

  footer(s, 3);
  s.addNotes("Türkiye'de yılda 70 binin üzerinde yangın olayı yaşanıyor. Çoğu ilk dakikalarda fark edilseydi büyük hasara dönüşmezdi. Mevcut alarm sistemleri yetersiz ve insana bağımlı.");
}

// SLAYT 4 — MEVCUT ÇÖZÜMLER
{
  const s = p.addSlide();
  lightBg(s);
  eyebrow(s, "Pazar Analizi");
  bigTitle(s, "Mevcut Sistemler Yetersiz");

  // Karşılaştırma tablosu
  const rows = [
    [
      { text: "Sistem", options: { bold: true, color: "FFFFFF", fill: { color: C.blue } } },
      { text: "Hız", options: { bold: true, color: "FFFFFF", fill: { color: C.blue }, align: "center" } },
      { text: "Otonom mu?", options: { bold: true, color: "FFFFFF", fill: { color: C.blue }, align: "center" } },
      { text: "Hareketli mi?", options: { bold: true, color: "FFFFFF", fill: { color: C.blue }, align: "center" } },
      { text: "Maliyet", options: { bold: true, color: "FFFFFF", fill: { color: C.blue }, align: "center" } },
    ],
    ["Duman Dedektörü", { text: "Yavaş ✗", options: { color: C.red, align: "center" } }, { text: "Hayır", options: { align: "center" } }, { text: "Hayır", options: { align: "center" } }, { text: "Düşük", options: { align: "center" } }],
    ["CCTV + İnsan", { text: "Orta", options: { color: C.amber, align: "center" } }, { text: "Hayır ✗", options: { color: C.red, align: "center" } }, { text: "Hayır", options: { align: "center" } }, { text: "Yüksek", options: { align: "center" } }],
    ["AI Destekli CCTV", { text: "Hızlı", options: { color: C.green, align: "center" } }, { text: "Yarı", options: { align: "center" } }, { text: "Hayır ✗", options: { color: C.red, align: "center" } }, { text: "Çok Yüksek", options: { color: C.red, align: "center" } }],
    [
      { text: "OYTS (Bizim)", options: { bold: true, color: C.blue, fill: { color: "FFF7ED" } } },
      { text: "Hızlı ✓", options: { color: C.green, bold: true, align: "center", fill: { color: "FFF7ED" } } },
      { text: "Evet ✓", options: { color: C.green, bold: true, align: "center", fill: { color: "FFF7ED" } } },
      { text: "Evet ✓", options: { color: C.green, bold: true, align: "center", fill: { color: "FFF7ED" } } },
      { text: "Düşük-Orta", options: { color: C.green, bold: true, align: "center", fill: { color: "FFF7ED" } } },
    ],
  ];
  s.addTable(rows, {
    x: 0.5, y: 1.7, w: 9, h: 3.2,
    fontSize: 13, fontFace: FONT_BODY, color: C.text,
    colW: [3.0, 1.5, 1.8, 1.8, 1.4],
    rowH: 0.55,
    border: { type: "solid", pt: 0.5, color: C.border },
    valign: "middle",
  });

  footer(s, 4);
  s.addNotes("Hem hızlı, hem tamamen otonom, hem hareketli ve ev/ofis ölçeğinde uygun fiyatlı bir çözüm yoktu. Profesyonel sistemler binlerce dolar. Biz bu boşluğu hedefledik.");
}

// SLAYT 5 — BİZİM ÇÖZÜMÜMÜZ
{
  const s = p.addSlide();
  lightBg(s);
  eyebrow(s, "Çözümümüz");
  bigTitle(s, "OYTS: Robot Otonom Yangınla Mücadele Eder");

  // 3 yetenek kartı
  const caps = [
    { ico: "👁", h: "GÖRÜYOR", t: "ESP32-CAM ile ortamı sürekli izler. YOLOv8 modeli saniyede 16+ kareyi analiz eder.", c: C.blue },
    { ico: "🧠", h: "KARAR VERİYOR", t: "Bulanık Mantık ile yangının önceliğini, SA ile en kısa rotayı hesaplar.", c: C.orange },
    { ico: "🎯", h: "MÜDAHALE EDİYOR", t: "Hedefe yaklaşır, sıcaklık 60°C eşiğini geçince güvenli müdahale başlar.", c: C.green },
  ];
  const cw = 2.95, ch = 2.5, gap = 0.1;
  caps.forEach((it, i) => {
    const x = 0.5 + i * (cw + gap), y = 1.8;
    s.addShape(p.shapes.RECTANGLE, {
      x, y, w: cw, h: ch, fill: { color: C.card },
      line: { color: C.border, width: 0.5 }, shadow: cardShadow(),
    });
    // ikon yuvarlağı
    s.addShape(p.shapes.OVAL, {
      x: x + cw/2 - 0.45, y: y + 0.3, w: 0.9, h: 0.9,
      fill: { color: it.c }, line: { color: it.c, width: 0 },
    });
    s.addText(it.ico, {
      x: x + cw/2 - 0.45, y: y + 0.3, w: 0.9, h: 0.9, fontSize: 32,
      align: "center", valign: "middle", color: "FFFFFF", margin: 0,
    });
    s.addText(it.h, {
      x, y: y + 1.3, w: cw, h: 0.4, fontSize: 16, bold: true,
      color: C.text, align: "center", fontFace: FONT_TITLE,
      charSpacing: 2,
    });
    s.addText(it.t, {
      x: x + 0.3, y: y + 1.75, w: cw - 0.6, h: 0.7, fontSize: 11,
      color: C.muted, align: "center", fontFace: FONT_BODY,
    });
  });

  // Alt vurgu
  s.addShape(p.shapes.RECTANGLE, {
    x: 0.5, y: 4.55, w: 9, h: 0.55,
    fill: { color: C.navy }, line: { color: C.navy, width: 0 },
  });
  s.addText("« Hiçbir insan müdahalesine gerek yok — robot kendi görür, karar verir, müdahale eder. »", {
    x: 0.5, y: 4.55, w: 9, h: 0.55, fontSize: 13, italic: true, bold: true,
    color: "FFFFFF", align: "center", valign: "middle",
    fontFace: FONT_BODY, margin: 0,
  });

  footer(s, 5);
  s.addNotes("Sistemimizin 3 yeteneği: görme, karar verme, müdahale. ESP32 her saniye onlarca frame yollar, model analiz eder, FSM komut üretir. Süre: ~40 sn.");
}

// SLAYT 6 — MİMARİ 3 KATMAN
{
  const s = p.addSlide();
  lightBg(s);
  eyebrow(s, "Mimari");
  bigTitle(s, "Üç Katman, Üç Sorumluluk");

  // Diyagram: PC üstte, ESP ve Mega altta
  // PC katmanı
  const pcX = 2.5, pcY = 1.7, pcW = 5, pcH = 0.9;
  s.addShape(p.shapes.RECTANGLE, {
    x: pcX, y: pcY, w: pcW, h: pcH,
    fill: { color: C.blue }, line: { color: C.blue, width: 0 },
    shadow: cardShadow(),
  });
  s.addText("PC · Python 3.10+", {
    x: pcX, y: pcY + 0.05, w: pcW, h: 0.4, fontSize: 16, bold: true,
    color: "FFFFFF", align: "center", fontFace: FONT_TITLE, margin: 0,
  });
  s.addText("YOLOv8  ·  Tracker  ·  Fuzzy  ·  SA  ·  FSM", {
    x: pcX, y: pcY + 0.45, w: pcW, h: 0.35, fontSize: 12,
    color: "CADCFC", align: "center", fontFace: FONT_BODY, margin: 0,
  });

  // Çizgiler (PC → ESP32, PC → Mega)
  s.addShape(p.shapes.LINE, {
    x: pcX + 1.0, y: pcY + pcH, w: -1.0, h: 1.0,
    line: { color: C.faint, width: 1.5, dashType: "dash" },
  });
  s.addShape(p.shapes.LINE, {
    x: pcX + pcW - 1.0, y: pcY + pcH, w: 1.0, h: 1.0,
    line: { color: C.faint, width: 1.5, dashType: "dash" },
  });
  s.addText("Wi-Fi · MJPEG", {
    x: 0.5, y: pcY + pcH + 0.05, w: 2.5, h: 0.3, fontSize: 9,
    color: C.muted, italic: true, fontFace: FONT_BODY, align: "center",
  });
  s.addText("USB Serial · 115200", {
    x: 7.0, y: pcY + pcH + 0.05, w: 2.5, h: 0.3, fontSize: 9,
    color: C.muted, italic: true, fontFace: FONT_BODY, align: "center",
  });

  // ESP32 ve Mega kutuları
  const lowerY = pcY + pcH + 1.0;
  // ESP32
  s.addShape(p.shapes.RECTANGLE, {
    x: 0.5, y: lowerY, w: 4.3, h: 1.6,
    fill: { color: C.card }, line: { color: C.border, width: 0.5 }, shadow: cardShadow(),
  });
  s.addShape(p.shapes.RECTANGLE, {
    x: 0.5, y: lowerY, w: 0.08, h: 1.6, fill: { color: C.orange }, line: { color: C.orange, width: 0 },
  });
  s.addText("ESP32-CAM", {
    x: 0.75, y: lowerY + 0.15, w: 4.0, h: 0.4, fontSize: 16, bold: true,
    color: C.text, fontFace: FONT_TITLE,
  });
  s.addText("Göz Katmanı", {
    x: 0.75, y: lowerY + 0.55, w: 4.0, h: 0.3, fontSize: 10,
    color: C.orange, bold: true, fontFace: FONT_BODY, charSpacing: 2,
  });
  s.addText("• MJPEG Wi-Fi stream\n• Telemetri (ısı, RSSI, PSRAM)\n• Runtime çözünürlük kontrolü", {
    x: 0.75, y: lowerY + 0.85, w: 4.0, h: 0.75, fontSize: 11,
    color: C.muted, fontFace: FONT_BODY,
  });

  // Mega
  s.addShape(p.shapes.RECTANGLE, {
    x: 5.2, y: lowerY, w: 4.3, h: 1.6,
    fill: { color: C.card }, line: { color: C.border, width: 0.5 }, shadow: cardShadow(),
  });
  s.addShape(p.shapes.RECTANGLE, {
    x: 5.2, y: lowerY, w: 0.08, h: 1.6, fill: { color: C.blue }, line: { color: C.blue, width: 0 },
  });
  s.addText("Arduino Mega 2560", {
    x: 5.45, y: lowerY + 0.15, w: 4.0, h: 0.4, fontSize: 16, bold: true,
    color: C.text, fontFace: FONT_TITLE,
  });
  s.addText("Beyin & Kas Katmanı", {
    x: 5.45, y: lowerY + 0.55, w: 4.0, h: 0.3, fontSize: 10,
    color: C.blue, bold: true, fontFace: FONT_BODY, charSpacing: 2,
  });
  s.addText("• 4WD motor + servo kontrolü\n• Voltaj izleme + yangın alarm\n• STATUS heartbeat + watchdog", {
    x: 5.45, y: lowerY + 0.85, w: 4.0, h: 0.75, fontSize: 11,
    color: C.muted, fontFace: FONT_BODY,
  });

  footer(s, 6);
  s.addNotes("3 katmanlı modüler tasarım. Her katman izole test edilebilir. PC kameraya MJPEG ile, Mega'ya USB serial ile bağlı. ESP32 ve Mega birbirine kablo ile bağlı DEĞİL — ikisi de aynı PC ile konuşur.");
}

// SLAYT 7 — DONANIM BİLEŞENLERİ
{
  const s = p.addSlide();
  lightBg(s);
  eyebrow(s, "Donanım");
  bigTitle(s, "Bileşenler ve Maliyet");

  // Sol: tablo
  const rows = [
    [
      { text: "Bileşen", options: { bold: true, color: "FFFFFF", fill: { color: C.blue } } },
      { text: "Model", options: { bold: true, color: "FFFFFF", fill: { color: C.blue } } },
    ],
    ["Kamera modülü", "ESP32-CAM (AI Thinker)"],
    ["Mikrodenetleyici", "Arduino Mega 2560"],
    ["Motor sürücüsü", "L298N Dual H-Bridge"],
    ["Şasi", "4WD TT Motor Platform"],
    ["Servo motor", "SG90 / MG90S"],
    ["Güç kaynağı", "3S LiPo 11.1V + 5V UBEC"],
    ["İşlem birimi", "PC (Mac / Windows)"],
  ];
  s.addTable(rows, {
    x: 0.5, y: 1.7, w: 5.3, h: 3.0,
    fontSize: 11, fontFace: FONT_BODY, color: C.text,
    colW: [2.0, 3.3], rowH: 0.36,
    border: { type: "solid", pt: 0.5, color: C.border },
    valign: "middle",
  });

  // Sağ: maliyet kartı
  s.addShape(p.shapes.RECTANGLE, {
    x: 6.2, y: 1.7, w: 3.3, h: 2.2,
    fill: { color: C.orange }, line: { color: C.orange, width: 0 }, shadow: cardShadow(),
  });
  s.addText("TOPLAM MALİYET", {
    x: 6.2, y: 1.85, w: 3.3, h: 0.35, fontSize: 12, bold: true,
    color: "FFFFFF", align: "center", charSpacing: 3, fontFace: FONT_BODY, margin: 0,
  });
  s.addText("~600-800 TL", {
    x: 6.2, y: 2.25, w: 3.3, h: 1.0, fontSize: 42, bold: true,
    color: "FFFFFF", align: "center", valign: "middle", fontFace: FONT_TITLE, margin: 0,
  });
  s.addText("(PC hariç)", {
    x: 6.2, y: 3.35, w: 3.3, h: 0.3, fontSize: 11,
    color: "FFE4D6", italic: true, align: "center", fontFace: FONT_BODY,
  });

  // Vurgu rozet
  s.addShape(p.shapes.RECTANGLE, {
    x: 6.2, y: 4.0, w: 3.3, h: 0.9,
    fill: { color: C.card }, line: { color: C.border, width: 0.5 },
  });
  s.addText("✓ Hobi elektronik mağazalarında bulunur\n✓ Tekrarlanabilir tasarım", {
    x: 6.3, y: 4.05, w: 3.1, h: 0.8, fontSize: 10,
    color: C.text, fontFace: FONT_BODY, valign: "middle",
  });

  footer(s, 7);
  s.addNotes("Tüm bileşenler yaygın ve uygun fiyatlı. Bilinçli seçim — başka öğrenciler de aynı projeyi tekrarlayabilsin. PC hariç toplam 600-800 TL.");
}

// SLAYT 8 — KATMAN 1: ESP32-CAM
{
  const s = p.addSlide();
  lightBg(s);
  eyebrow(s, "Katman 1 · Göz");
  bigTitle(s, "ESP32-CAM — Görüntü Akışı ve Telemetri");

  // Sol: özellik listesi
  const feats = [
    ["📡", "Wi-Fi MJPEG Stream", "Gerçek zamanlı 30 fps yayın, kameranın doğal FPS limiti"],
    ["🔄", "WiFi Auto-Reconnect", "Bağlantı düşerse non-blocking state machine ile yeniden bağlanır"],
    ["⚙️", "Runtime Çözünürlük", "/resolution endpoint ile QVGA → UXGA arası anlık değişim"],
    ["📊", "JSON Telemetri", "IP, RSSI, PSRAM, FPS, sıcaklık, heap, frame count"],
    ["🛡", "Frame Fail Watchdog", "N kare üst üste başarısız olursa soft restart"],
  ];
  feats.forEach((f, i) => {
    const y = 1.75 + i * 0.65;
    s.addText(f[0], { x: 0.5, y, w: 0.5, h: 0.5, fontSize: 22 });
    s.addText(f[1], { x: 1.05, y, w: 4.5, h: 0.3, fontSize: 13, bold: true, color: C.text, fontFace: FONT_TITLE });
    s.addText(f[2], { x: 1.05, y: y + 0.3, w: 4.5, h: 0.35, fontSize: 10, color: C.muted, fontFace: FONT_BODY });
  });

  // Sağ: kod örneği (terminal benzeri)
  s.addShape(p.shapes.RECTANGLE, {
    x: 6.0, y: 1.7, w: 3.7, h: 3.3,
    fill: { color: "1F2937" }, line: { color: "1F2937", width: 0 }, shadow: cardShadow(),
  });
  s.addText("[HTTP] Endpoints", {
    x: 6.15, y: 1.8, w: 3.5, h: 0.3, fontSize: 11, bold: true,
    color: C.orange, charSpacing: 2, fontFace: "Consolas",
  });
  s.addText([
    { text: "GET /stream",     options: { color: "10B981", bold: true, breakLine: true } },
    { text: "  → MJPEG video akışı", options: { color: "CBD5E1", fontSize: 10, breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 8 } },
    { text: "GET /telemetry",  options: { color: "10B981", bold: true, breakLine: true } },
    { text: "  → JSON: ip, rssi, fps...", options: { color: "CBD5E1", fontSize: 10, breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 8 } },
    { text: "GET /resolution?", options: { color: "10B981", bold: true, breakLine: true } },
    { text: "      value=hd", options: { color: "10B981", bold: true, breakLine: true } },
    { text: "  → runtime çözünürlük", options: { color: "CBD5E1", fontSize: 10, breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 8 } },
    { text: "GET /snapshot",   options: { color: "10B981", bold: true, breakLine: true } },
    { text: "  → tek-kare JPEG indir", options: { color: "CBD5E1", fontSize: 10 } },
  ], {
    x: 6.15, y: 2.2, w: 3.5, h: 2.7, fontSize: 11,
    fontFace: "Consolas", color: "F8FAFC",
  });

  footer(s, 8);
  s.addNotes("ESP32-CAM bir mini-web sunucu gibi. PC doğrudan stream izler, JSON telemetri çeker. Bağlantı düşse otomatik bağlanır. CORS açık → GitHub Pages bile bağlanabilir.");
}

// SLAYT 9 — KATMAN 2: ARDUINO MEGA
{
  const s = p.addSlide();
  lightBg(s);
  eyebrow(s, "Katman 2 · Beyin & Kas");
  bigTitle(s, "Arduino Mega 2560 — Hareket ve Alarm");

  // 4 özellik kategorisi 2x2
  const cats = [
    { ico: "⚙️", h: "Motor Kontrolü", t: "L298N H-Bridge ile 4WD diferansiyel sürüş.\nPWM hız kontrolü (60-255).\nNon-blocking servo sweep." },
    { ico: "🛡", h: "Güvenlik", t: "500 ms komut zaman aşımı → otomatik dur.\nVoltaj izleme (A0, voltaj bölücü).\nDüşük pil uyarısı." },
    { ico: "🚨", h: "Alarm", t: "Fire LED (D13) + opsiyonel buzzer.\n5 sn sinyal gelmezse alarm söner.\nFlash + ses kombinasyonu." },
    { ico: "📡", h: "İletişim", t: "STATUS heartbeat (1 sn).\nYapısal protokol: CMD:X;SPD:N.\nREADY handshake boot sinyali." },
  ];
  const cw = 4.4, ch = 1.5, gap = 0.15;
  cats.forEach((it, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = 0.5 + col * (cw + gap), y = 1.7 + row * (ch + gap);
    s.addShape(p.shapes.RECTANGLE, {
      x, y, w: cw, h: ch, fill: { color: C.card },
      line: { color: C.border, width: 0.5 }, shadow: cardShadow(),
    });
    s.addText(it.ico, { x: x + 0.15, y: y + 0.15, w: 0.6, h: 0.6, fontSize: 24 });
    s.addText(it.h, { x: x + 0.8, y: y + 0.12, w: cw - 1.0, h: 0.4, fontSize: 14, bold: true, color: C.text, fontFace: FONT_TITLE });
    s.addText(it.t, { x: x + 0.8, y: y + 0.55, w: cw - 1.0, h: 0.9, fontSize: 10, color: C.muted, fontFace: FONT_BODY });
  });

  // Alt — protokol örneği
  s.addShape(p.shapes.RECTANGLE, {
    x: 0.5, y: 4.85, w: 9.0, h: 0.5,
    fill: { color: "1F2937" }, line: { color: "1F2937", width: 0 },
  });
  s.addText([
    { text: "PC→Arduino: ", options: { color: C.orange, bold: true } },
    { text: "CMD:FORWARD;SPD:180;ARM:UP   ", options: { color: "10B981" } },
    { text: "FIRE:ON   ", options: { color: "FBBF24" } },
    { text: "QUERY:STATUS", options: { color: "CBD5E1" } },
  ], {
    x: 0.7, y: 4.85, w: 8.8, h: 0.5, fontSize: 11,
    fontFace: "Consolas", valign: "middle", margin: 0,
  });

  footer(s, 9);
  s.addNotes("Arduino Mega projenin omurgası. Önemli nokta: hiçbir komut bloklamaz. Servo hareket ederken bile motor zaman aşımı ve voltaj okuma çalışır. Yapısal protokol PC ile sağlam iletişim kurar.");
}

// SLAYT 10 — KATMAN 3: PC + YOLOv8
{
  const s = p.addSlide();
  lightBg(s);
  eyebrow(s, "Katman 3 · Karar");
  bigTitle(s, "PC Tarafı — Yapay Zekâ Karar Zinciri");

  // Üst: pipeline akışı
  const pipe = ["YOLOv8", "Validator", "Tracker", "Fuzzy", "SA", "FSM"];
  const pw = 1.3, ph = 0.65, py = 1.75, pad = 0.15;
  const totalW = pipe.length * pw + (pipe.length - 1) * pad;
  const startX = (W - totalW) / 2;
  pipe.forEach((step, i) => {
    const x = startX + i * (pw + pad);
    s.addShape(p.shapes.RECTANGLE, {
      x, y: py, w: pw, h: ph,
      fill: { color: i === 0 ? C.orange : C.blue }, line: { color: C.blue, width: 0 },
    });
    s.addText(step, {
      x, y: py, w: pw, h: ph, fontSize: 12, bold: true,
      color: "FFFFFF", align: "center", valign: "middle",
      fontFace: FONT_BODY, margin: 0,
    });
    // Ok
    if (i < pipe.length - 1) {
      s.addText("→", {
        x: x + pw, y: py, w: pad, h: ph, fontSize: 14, bold: true,
        color: C.muted, align: "center", valign: "middle", margin: 0,
      });
    }
  });

  // Alt: 13 AI modülü grid
  s.addText("13 ayrı AI modülü — her biri tek sorumluluk", {
    x: 0.5, y: 2.7, w: 9, h: 0.3, fontSize: 11, italic: true,
    color: C.muted, align: "center", fontFace: FONT_BODY,
  });

  const mods = [
    "tracker.py", "heatmap.py", "distance.py",
    "fire_validator.py", "bright_flame_detector.py", "sim_detector.py",
    "webhook.py", "train.py", "train_roboflow.py",
    "evaluate.py", "prepare_dataset.py", "finetune_synthetic.py",
    "download_model.py",
  ];
  const mw = 1.65, mh = 0.4, mgap = 0.1;
  const cols = 5;
  mods.forEach((m, i) => {
    const col = i % cols, row = Math.floor(i / cols);
    const x = 0.5 + col * (mw + mgap), y = 3.15 + row * (mh + mgap);
    s.addShape(p.shapes.RECTANGLE, {
      x, y, w: mw, h: mh, fill: { color: C.card },
      line: { color: C.border, width: 0.5 },
    });
    s.addText(m, {
      x, y, w: mw, h: mh, fontSize: 9, color: C.text,
      align: "center", valign: "middle", fontFace: "Consolas", margin: 0,
    });
  });

  // Alt vurgu — tech
  s.addText("Python 3.10  ·  YOLOv8 (Ultralytics)  ·  PyTorch (MPS / CUDA)  ·  OpenCV  ·  Flask", {
    x: 0.5, y: H - 0.65, w: 9, h: 0.3, fontSize: 11,
    color: C.blue, italic: true, align: "center", fontFace: FONT_BODY,
  });

  footer(s, 10);
  s.addNotes("PC tarafı projemizin beynidir. Sadece YOLO değil — çıktıyı filtreleyen, takip eden, önceliklendiren, robot komutuna çeviren tüm zinciri biz yazdık. 13 modül, her biri tek sorumluluğa sahip.");
}

// SLAYT 11 — YOLOv8
{
  const s = p.addSlide();
  lightBg(s);
  eyebrow(s, "Algoritma 1");
  bigTitle(s, "YOLOv8 — Derin Öğrenme Tabanlı Tespit");

  // Sol: model bilgileri
  s.addText("MODEL", { x: 0.5, y: 1.7, w: 4, h: 0.3, fontSize: 11, bold: true, color: C.orange, charSpacing: 3, fontFace: FONT_BODY });
  s.addText([
    { text: "Mimari: ", options: { bold: true, color: C.text } },
    { text: "YOLOv8s (Small) — 11.1M parametre", options: { color: C.muted, breakLine: true } },
    { text: "Çözünürlük: ", options: { bold: true, color: C.text } },
    { text: "640×640", options: { color: C.muted, breakLine: true } },
    { text: "Inference hızı: ", options: { bold: true, color: C.text } },
    { text: "16+ FPS (MPS), 3-5 FPS (CPU)", options: { color: C.muted, breakLine: true } },
    { text: "Sınıflar: ", options: { bold: true, color: C.text } },
    { text: "fire, smoke, default", options: { color: C.muted } },
  ], {
    x: 0.5, y: 2.05, w: 4.5, h: 1.6, fontSize: 11, fontFace: FONT_BODY,
  });

  s.addText("FINE-TUNE STRATEJİSİ", { x: 0.5, y: 3.7, w: 4.5, h: 0.3, fontSize: 11, bold: true, color: C.orange, charSpacing: 3, fontFace: FONT_BODY });
  s.addText([
    { text: "freeze=10 ", options: { bold: true, color: C.text } },
    { text: "(backbone dondurulur, sadece head öğrenir)", options: { color: C.muted, breakLine: true } },
    { text: "lr0=1e-4 ", options: { bold: true, color: C.text } },
    { text: "(catastrophic forgetting önleme)", options: { color: C.muted, breakLine: true } },
    { text: "patience=15 ", options: { bold: true, color: C.text } },
    { text: "(plato gelince erken durdurma)", options: { color: C.muted } },
  ], {
    x: 0.5, y: 4.05, w: 4.5, h: 1.2, fontSize: 10, fontFace: FONT_BODY,
  });

  // Sağ: dataset + mAP karşılaştırma
  s.addText("DATASET VE BAŞARIM", { x: 5.5, y: 1.7, w: 4, h: 0.3, fontSize: 11, bold: true, color: C.orange, charSpacing: 3, fontFace: FONT_BODY });
  const datasets = [
    [
      { text: "Dataset", options: { bold: true, color: "FFFFFF", fill: { color: C.blue } } },
      { text: "Boyut", options: { bold: true, color: "FFFFFF", fill: { color: C.blue }, align: "center" } },
      { text: "mAP50", options: { bold: true, color: "FFFFFF", fill: { color: C.blue }, align: "center" } },
    ],
    ["D-Fire + FASDD", { text: "25 K", options: { align: "center" } }, { text: "0.55", options: { align: "center" } }],
    ["+ 5 K sentetik (FT)", { text: "30 K", options: { align: "center" } }, { text: "0.93", options: { color: C.green, bold: true, align: "center" } }],
    ["+ 2 K Roboflow", { text: "32 K", options: { align: "center" } }, { text: "0.60 (real)", options: { color: C.orange, bold: true, align: "center" } }],
  ];
  s.addTable(datasets, {
    x: 5.5, y: 2.05, w: 4.0, h: 1.8,
    fontSize: 10, fontFace: FONT_BODY, color: C.text,
    colW: [1.9, 1.0, 1.1], rowH: 0.4,
    border: { type: "solid", pt: 0.5, color: C.border },
    valign: "middle",
  });

  // Eğitim süresi vurgusu
  s.addShape(p.shapes.RECTANGLE, {
    x: 5.5, y: 4.05, w: 4.0, h: 1.0,
    fill: { color: C.navy }, line: { color: C.navy, width: 0 },
  });
  s.addText("⏱  Eğitim Süresi", {
    x: 5.6, y: 4.1, w: 3.8, h: 0.3, fontSize: 11, bold: true,
    color: C.orange, fontFace: FONT_BODY,
  });
  s.addText("~1 saat (Apple M4 MPS, 15 epoch, freeze=10)", {
    x: 5.6, y: 4.4, w: 3.8, h: 0.3, fontSize: 12,
    color: "FFFFFF", fontFace: FONT_BODY,
  });
  s.addText("→ 269% mAP50 iyileşmesi", {
    x: 5.6, y: 4.7, w: 3.8, h: 0.3, fontSize: 11, italic: true,
    color: "CADCFC", fontFace: FONT_BODY,
  });

  footer(s, 11);
  s.addNotes("YOLOv8 gerçek zamanlı obje tespiti için tasarlanmış. Biz kendi sentetik dataset'imizle fine-tune ettik — mAP50 0.55'ten 0.93'e yükseldi. Backbone freeze ederek gerçek dünya bilgisini koruduk.");
}

// SLAYT 12 — BULANIK MANTIK
{
  const s = p.addSlide();
  lightBg(s);
  eyebrow(s, "Algoritma 2");
  bigTitle(s, "Bulanık Mantık — Önceliklendirme");

  // Sol: neden bulanık?
  s.addText("NEDEN BULANIK?", { x: 0.5, y: 1.7, w: 4.5, h: 0.3, fontSize: 11, bold: true, color: C.orange, charSpacing: 3, fontFace: FONT_BODY });
  s.addText("Yangının \"büyüklük\" sınırı keskin değildir.\n5000 piksel hem orta hem küçük olabilir.\n\nBulanık mantık derecelendirilmiş üyelikle karar verir — bir alev %60 MEDIUM + %40 SMALL olabilir.", {
    x: 0.5, y: 2.05, w: 4.5, h: 1.8, fontSize: 11,
    color: C.muted, fontFace: FONT_BODY,
  });

  // Defuzzification formülü
  s.addShape(p.shapes.RECTANGLE, {
    x: 0.5, y: 4.0, w: 4.5, h: 1.05,
    fill: { color: C.navy }, line: { color: C.navy, width: 0 },
  });
  s.addText("DEFUZZIFICATION (Mamdani)", {
    x: 0.65, y: 4.1, w: 4.2, h: 0.3, fontSize: 10, bold: true,
    color: C.orange, charSpacing: 2, fontFace: FONT_BODY,
  });
  s.addText("P  =  Σ(μᵢ × vᵢ)  /  Σ(μᵢ)", {
    x: 0.65, y: 4.45, w: 4.2, h: 0.5, fontSize: 22, bold: true,
    color: "FFFFFF", align: "center", fontFace: "Consolas",
  });

  // Sağ: üyelik fonksiyonu tablosu
  s.addText("ÜYELİK FONKSIYONLARI (TRAPEZOIDAL)", { x: 5.5, y: 1.7, w: 4.5, h: 0.3, fontSize: 11, bold: true, color: C.orange, charSpacing: 3, fontFace: FONT_BODY });
  const fuzzy = [
    [
      { text: "Küme", options: { bold: true, color: "FFFFFF", fill: { color: C.blue } } },
      { text: "Aralık (piksel²)", options: { bold: true, color: "FFFFFF", fill: { color: C.blue }, align: "center" } },
      { text: "Skor", options: { bold: true, color: "FFFFFF", fill: { color: C.blue }, align: "center" } },
    ],
    [{ text: "SMALL",  options: { bold: true, color: C.muted } }, { text: "[0, 0, 2K, 3K]",       options: { align: "center" } }, { text: "0.15", options: { align: "center" } }],
    [{ text: "MEDIUM", options: { bold: true, color: C.amber } }, { text: "[2K, 3K, 10K, 12K]",   options: { align: "center" } }, { text: "0.45", options: { align: "center" } }],
    [{ text: "LARGE",  options: { bold: true, color: C.orange } }, { text: "[10K, 12K, 24K, 28K]", options: { align: "center" } }, { text: "0.78", options: { align: "center" } }],
    [{ text: "HUGE",   options: { bold: true, color: C.red } }, { text: "[24K, 28K, 60K, 60K]",  options: { align: "center" } }, { text: "1.00", options: { color: C.red, bold: true, align: "center" } }],
  ];
  s.addTable(fuzzy, {
    x: 5.5, y: 2.05, w: 4.0, h: 2.4,
    fontSize: 10, fontFace: FONT_BODY, color: C.text,
    colW: [1.1, 1.9, 1.0], rowH: 0.4,
    border: { type: "solid", pt: 0.5, color: C.border },
    valign: "middle",
  });

  // Örnek
  s.addShape(p.shapes.RECTANGLE, {
    x: 5.5, y: 4.55, w: 4.0, h: 0.55,
    fill: { color: "FFF7ED" }, line: { color: C.orange, width: 0.5 },
  });
  s.addText("Örnek: 3K piksel → μ_SMALL=0.5 + μ_MEDIUM=0.5 → P=0.30", {
    x: 5.5, y: 4.55, w: 4.0, h: 0.55, fontSize: 10,
    color: C.text, align: "center", valign: "middle",
    italic: true, fontFace: FONT_BODY, margin: 0,
  });

  footer(s, 12);
  s.addNotes("Bulanık mantık insan gibi düşünme imkânı verir. Bir alev hem küçük hem orta olabilir. Mamdani modeli en yaygın bulanık çıkarsama yöntemidir.");
}

// SLAYT 13 — SIMULATED ANNEALING
{
  const s = p.addSlide();
  lightBg(s);
  eyebrow(s, "Algoritma 3");
  bigTitle(s, "Simulated Annealing — Rota Optimizasyonu");

  // Sol: problem
  s.addText("PROBLEM", { x: 0.5, y: 1.7, w: 4.5, h: 0.3, fontSize: 11, bold: true, color: C.orange, charSpacing: 3, fontFace: FONT_BODY });
  s.addText("3-5 yangın aynı anda → hangisine önce gitmeli?", {
    x: 0.5, y: 2.0, w: 4.5, h: 0.4, fontSize: 13, bold: true,
    color: C.text, fontFace: FONT_BODY,
  });

  s.addText("Brute force (tüm permütasyonlar):", {
    x: 0.5, y: 2.5, w: 4.5, h: 0.3, fontSize: 11,
    color: C.muted, fontFace: FONT_BODY,
  });

  // İki istatistik
  s.addShape(p.shapes.RECTANGLE, {
    x: 0.5, y: 2.85, w: 2.15, h: 1.0,
    fill: { color: C.card }, line: { color: C.border, width: 0.5 },
  });
  s.addText("120", { x: 0.5, y: 2.9, w: 2.15, h: 0.55, fontSize: 32, bold: true, color: C.green, align: "center", fontFace: FONT_TITLE, margin: 0 });
  s.addText("5 yangın", { x: 0.5, y: 3.5, w: 2.15, h: 0.3, fontSize: 10, color: C.muted, align: "center", fontFace: FONT_BODY });

  s.addShape(p.shapes.RECTANGLE, {
    x: 2.85, y: 2.85, w: 2.15, h: 1.0,
    fill: { color: C.card }, line: { color: C.border, width: 0.5 },
  });
  s.addText("3.6M", { x: 2.85, y: 2.9, w: 2.15, h: 0.55, fontSize: 32, bold: true, color: C.red, align: "center", fontFace: FONT_TITLE, margin: 0 });
  s.addText("10 yangın · imkânsız", { x: 2.85, y: 3.5, w: 2.15, h: 0.3, fontSize: 10, color: C.muted, align: "center", fontFace: FONT_BODY });

  // SA parametreleri
  s.addText("SA PARAMETRELERİ", { x: 0.5, y: 4.05, w: 4.5, h: 0.3, fontSize: 11, bold: true, color: C.orange, charSpacing: 3, fontFace: FONT_BODY });
  s.addText("T_start=5000  ·  α=0.995  ·  max_iter=3000", {
    x: 0.5, y: 4.4, w: 4.5, h: 0.3, fontSize: 12, bold: true,
    color: C.text, fontFace: "Consolas",
  });
  s.addText("Sonuç: 5-10 yangın için milisaniyeler içinde optimuma yakın çözüm (%95+)", {
    x: 0.5, y: 4.75, w: 4.5, h: 0.4, fontSize: 10, italic: true,
    color: C.muted, fontFace: FONT_BODY,
  });

  // Sağ: Metropolis kabul kriteri (görsel)
  s.addShape(p.shapes.RECTANGLE, {
    x: 5.5, y: 1.7, w: 4.0, h: 3.4,
    fill: { color: C.navy }, line: { color: C.navy, width: 0 }, shadow: cardShadow(),
  });
  s.addText("METROPOLIS KABUL KRİTERİ", {
    x: 5.6, y: 1.85, w: 3.8, h: 0.3, fontSize: 11, bold: true,
    color: C.orange, charSpacing: 2, fontFace: FONT_BODY,
  });

  // Formül
  s.addText("P(kabul) = e^(-ΔC / T)", {
    x: 5.6, y: 2.25, w: 3.8, h: 0.5, fontSize: 22, bold: true,
    color: "FFFFFF", align: "center", fontFace: "Consolas",
  });

  // Algoritma adımları
  s.addText([
    { text: "1. ", options: { color: C.orange, bold: true } },
    { text: "Mevcut çözümü değiştir", options: { color: "FFFFFF", breakLine: true } },
    { text: "2. ", options: { color: C.orange, bold: true } },
    { text: "Yeni daha iyiyse → KABUL", options: { color: "FFFFFF", breakLine: true } },
    { text: "3. ", options: { color: C.orange, bold: true } },
    { text: "Kötüyse → P ihtimaliyle yine kabul", options: { color: "FFFFFF", breakLine: true } },
    { text: "4. ", options: { color: C.orange, bold: true } },
    { text: "T = T × α   (sıcaklığı düşür)", options: { color: "FFFFFF" } },
  ], {
    x: 5.7, y: 3.0, w: 3.7, h: 2.0, fontSize: 12, fontFace: FONT_BODY,
  });

  footer(s, 13);
  s.addNotes("SA, NP-zor problemleri yaklaşık çözmek için kullanılan klasik algoritma. Robot tüm yangınları minimum mesafeyle ziyaret etmeli. Algoritma rasgele kötü hamleleri kabul ederek local minimum tuzaklarından kaçar.");
}

// SLAYT 14 — MULTI-SIGNAL VALIDATOR
{
  const s = p.addSlide();
  lightBg(s);
  eyebrow(s, "Akıllı Filtreleme");
  // Daha kısa başlık — tek satıra sığar
  bigTitle(s, "Multi-Signal Validator");

  s.addText("YOLO tek başına yetmez: kırmızı foto, ten, kırmızı duvar yangın sanılabilir.", {
    x: 0.5, y: 1.45, w: 9, h: 0.4, fontSize: 13,
    color: C.muted, italic: true, fontFace: FONT_BODY,
  });

  // 4 sinyal kartı
  const sig = [
    { ico: "💡", h: "bright_core",  w: "0.45", t: "V≥245 piksel oranı — gerçek alevin beyaz çekirdeği" },
    { ico: "📈", h: "temporal",     w: "0.25", t: "Son N frame'de ROI içi piksel değişimi" },
    { ico: "🌀", h: "motion",       w: "0.20", t: "Frame-to-frame absolute difference" },
    { ico: "🎨", h: "saturation",   w: "0.10", t: "Alev rengi konformanı (H + S + V profili)" },
  ];
  const cw = 2.2, ch = 1.55, gap = 0.1;
  sig.forEach((it, i) => {
    const x = 0.5 + i * (cw + gap), y = 2.0;
    s.addShape(p.shapes.RECTANGLE, {
      x, y, w: cw, h: ch,
      fill: { color: C.card }, line: { color: C.border, width: 0.5 }, shadow: cardShadow(),
    });
    s.addText(it.ico, { x: x + 0.1, y: y + 0.1, w: 0.6, h: 0.5, fontSize: 22 });
    // ağırlık rozeti sağ üst
    s.addShape(p.shapes.RECTANGLE, {
      x: x + cw - 0.7, y: y + 0.15, w: 0.55, h: 0.3,
      fill: { color: C.orange }, line: { color: C.orange, width: 0 },
    });
    s.addText(it.w, {
      x: x + cw - 0.7, y: y + 0.15, w: 0.55, h: 0.3, fontSize: 11, bold: true,
      color: "FFFFFF", align: "center", valign: "middle", fontFace: FONT_BODY, margin: 0,
    });
    s.addText(it.h, {
      x: x + 0.1, y: y + 0.6, w: cw - 0.2, h: 0.3, fontSize: 12, bold: true,
      color: C.blue, fontFace: "Consolas",
    });
    s.addText(it.t, {
      x: x + 0.1, y: y + 0.95, w: cw - 0.2, h: 0.55, fontSize: 9,
      color: C.muted, fontFace: FONT_BODY,
    });
  });

  // Sonuç matrisi tablo
  s.addText("SONUÇ MATRISI", { x: 0.5, y: 3.75, w: 9, h: 0.3, fontSize: 11, bold: true, color: C.orange, charSpacing: 3, fontFace: FONT_BODY });
  const results = [
    [
      { text: "Senaryo", options: { bold: true, color: "FFFFFF", fill: { color: C.blue } } },
      { text: "Composite", options: { bold: true, color: "FFFFFF", fill: { color: C.blue }, align: "center" } },
      { text: "Karar", options: { bold: true, color: "FFFFFF", fill: { color: C.blue }, align: "center" } },
      { text: "Senaryo", options: { bold: true, color: "FFFFFF", fill: { color: C.blue } } },
      { text: "Composite", options: { bold: true, color: "FFFFFF", fill: { color: C.blue }, align: "center" } },
      { text: "Karar", options: { bold: true, color: "FFFFFF", fill: { color: C.blue }, align: "center" } },
    ],
    [
      "Gerçek çakmak (titrer)", { text: "0.66", options: { align: "center" } }, { text: "✓ KABUL", options: { color: C.green, bold: true, align: "center" } },
      "Statik kırmızı foto", { text: "0.12", options: { align: "center" } }, { text: "✗ RED", options: { color: C.red, bold: true, align: "center" } },
    ],
    [
      "Yangın videosu", { text: "0.55", options: { align: "center" } }, { text: "✓ KABUL", options: { color: C.green, bold: true, align: "center" } },
      "Yüz / cilt", { text: "0.14", options: { align: "center" } }, { text: "✗ RED", options: { color: C.red, bold: true, align: "center" } },
    ],
  ];
  s.addTable(results, {
    x: 0.5, y: 4.1, w: 9.0, h: 1.0,
    fontSize: 10, fontFace: FONT_BODY, color: C.text,
    colW: [1.85, 0.85, 0.8, 1.85, 0.85, 0.8], rowH: 0.33,
    border: { type: "solid", pt: 0.5, color: C.border },
    valign: "middle",
  });

  footer(s, 14);
  s.addNotes("Bu modülü biz tasarladık. Gerçek alevin 4 fiziksel özelliği: beyaz çekirdek, içten titreme, hareket, karakteristik renk profili. Fotoğraf veya cilt bu kombinasyonun tümünü gösteremez.");
}

// SLAYT 15 — SENTETİK SİMÜLASYON
{
  const s = p.addSlide();
  lightBg(s);
  eyebrow(s, "Test ortamı");
  bigTitle(s, "Sentetik Simülasyon — Donanımsız Geliştirme");

  // Sol: 8 katman + özellikler
  s.addText("8 RENDER KATMANI", { x: 0.5, y: 1.7, w: 4, h: 0.3, fontSize: 11, bold: true, color: C.orange, charSpacing: 3, fontFace: FONT_BODY });
  s.addText([
    { text: "1. ", options: { color: C.blue, bold: true } }, { text: "Arka plan (loş oda)", options: { color: C.text, breakLine: true } },
    { text: "2. ", options: { color: C.blue, bold: true } }, { text: "Yer ışık yansıması", options: { color: C.text, breakLine: true } },
    { text: "3. ", options: { color: C.blue, bold: true } }, { text: "Duman parçacık sistemi", options: { color: C.text, breakLine: true } },
    { text: "4. ", options: { color: C.blue, bold: true } }, { text: "Alev (noise + palette)", options: { color: C.text, breakLine: true } },
    { text: "5. ", options: { color: C.blue, bold: true } }, { text: "Heat haze (sıcaklık)", options: { color: C.text, breakLine: true } },
    { text: "6. ", options: { color: C.blue, bold: true } }, { text: "Kıvılcımlar", options: { color: C.text, breakLine: true } },
    { text: "7. ", options: { color: C.blue, bold: true } }, { text: "Bloom (HDR)", options: { color: C.text, breakLine: true } },
    { text: "8. ", options: { color: C.blue, bold: true } }, { text: "Tone mapping (ACES)", options: { color: C.text } },
  ], {
    x: 0.5, y: 2.05, w: 4.5, h: 2.7, fontSize: 11, fontFace: FONT_BODY,
  });

  // Sağ: sentetik sahne ekran görüntüsü
  try {
    s.addImage({
      path: ROOT + "/web/screenshots/demo_synthetic_3.jpg",
      x: 5.3, y: 1.7, w: 4.3, h: 2.6,
      sizing: { type: "contain", w: 4.3, h: 2.6 },
    });
  } catch (e) { /* skip if image missing */ }

  // Alt: performans + 5000 frame
  const sx = 5.3, sy = 4.45, sw = 2.05, sh = 0.65, sgap = 0.2;
  // Card 1
  s.addShape(p.shapes.RECTANGLE, {
    x: sx, y: sy, w: sw, h: sh, fill: { color: C.card }, line: { color: C.border, width: 0.5 },
  });
  s.addText("25-40", { x: sx, y: sy + 0.05, w: sw, h: 0.35, fontSize: 18, bold: true, color: C.green, align: "center", fontFace: FONT_TITLE, margin: 0 });
  s.addText("FPS (M1)", { x: sx, y: sy + 0.4, w: sw, h: 0.25, fontSize: 9, color: C.muted, align: "center", fontFace: FONT_BODY });

  // Card 2
  s.addShape(p.shapes.RECTANGLE, {
    x: sx + sw + sgap, y: sy, w: sw, h: sh, fill: { color: C.card }, line: { color: C.border, width: 0.5 },
  });
  s.addText("5.000", { x: sx + sw + sgap, y: sy + 0.05, w: sw, h: 0.35, fontSize: 18, bold: true, color: C.orange, align: "center", fontFace: FONT_TITLE, margin: 0 });
  s.addText("eğitim frame'i", { x: sx + sw + sgap, y: sy + 0.4, w: sw, h: 0.25, fontSize: 9, color: C.muted, align: "center", fontFace: FONT_BODY });

  // Alt vurgu
  s.addText("« Robot olmasa, kamera bozulsa bile sistem test edilebiliyor »", {
    x: 0.5, y: H - 0.65, w: 9, h: 0.3, fontSize: 11, italic: true,
    color: C.blue, align: "center", fontFace: FONT_BODY,
  });

  footer(s, 15);
  s.addNotes("Sentetik sahne projemizin gizli kahramanı. Bu sayede her şart altında sistemi test edebiliyoruz. Hatta YOLO modelimizi bu sahnelerden 5000 frame ile fine-tune ederek başarımını artırdık.");
}

// SLAYT 16 — YAZILIM + TESTLER
{
  const s = p.addSlide();
  lightBg(s);
  eyebrow(s, "Mühendislik Pratiği");
  bigTitle(s, "Profesyonel Yazılım Kalitesi");

  // 50/50 test büyük vurgusu
  s.addShape(p.shapes.RECTANGLE, {
    x: 0.5, y: 1.7, w: 3.5, h: 1.8,
    fill: { color: C.green }, line: { color: C.green, width: 0 }, shadow: cardShadow(),
  });
  s.addText("50/50", {
    x: 0.5, y: 1.8, w: 3.5, h: 0.9, fontSize: 64, bold: true,
    color: "FFFFFF", align: "center", valign: "middle",
    fontFace: FONT_TITLE, margin: 0,
  });
  s.addText("pytest geçer", {
    x: 0.5, y: 2.8, w: 3.5, h: 0.4, fontSize: 14, bold: true,
    color: "FFFFFF", align: "center", charSpacing: 2,
    fontFace: FONT_BODY, margin: 0,
  });
  s.addText("✓ otomatik doğrulama her commit'te", {
    x: 0.5, y: 3.15, w: 3.5, h: 0.3, fontSize: 10,
    color: "DCFCE7", align: "center", italic: true, fontFace: FONT_BODY,
  });

  // Sağ: test breakdown
  s.addText("TEST DAĞILIMI", { x: 4.3, y: 1.7, w: 5.2, h: 0.3, fontSize: 11, bold: true, color: C.orange, charSpacing: 3, fontFace: FONT_BODY });
  const tests = [
    [
      { text: "Dosya", options: { bold: true, color: "FFFFFF", fill: { color: C.blue } } },
      { text: "Test", options: { bold: true, color: "FFFFFF", fill: { color: C.blue }, align: "center" } },
      { text: "Kapsam", options: { bold: true, color: "FFFFFF", fill: { color: C.blue } } },
    ],
    [{ text: "tracker", options: { fontFace: "Consolas" } }, { text: "8", options: { align: "center" } }, "IoU, promotion, grace"],
    [{ text: "fuzzy_sa", options: { fontFace: "Consolas" } }, { text: "8", options: { align: "center" } }, "Üyelik, ordering"],
    [{ text: "decision", options: { fontFace: "Consolas" } }, { text: "7", options: { align: "center" } }, "FSM dallanmaları"],
    [{ text: "ai_modules", options: { fontFace: "Consolas" } }, { text: "11", options: { align: "center" } }, "Heatmap, distance..."],
    [{ text: "fire_validator", options: { fontFace: "Consolas" } }, { text: "6", options: { align: "center" } }, "4-sinyal validator"],
    [{ text: "scene_generator", options: { fontFace: "Consolas" } }, { text: "5", options: { align: "center" } }, "Sentetik render"],
    [{ text: "config_csv", options: { fontFace: "Consolas" } }, { text: "5", options: { align: "center" } }, "ConfigDict, CSV"],
  ];
  s.addTable(tests, {
    x: 4.3, y: 2.05, w: 5.2, h: 2.65,
    fontSize: 10, fontFace: FONT_BODY, color: C.text,
    colW: [1.9, 0.7, 2.6], rowH: 0.33,
    border: { type: "solid", pt: 0.5, color: C.border },
    valign: "middle",
  });

  // Alt: yazılım pratikleri tek satır
  s.addShape(p.shapes.RECTANGLE, {
    x: 0.5, y: 4.85, w: 9.0, h: 0.5,
    fill: { color: C.navy }, line: { color: C.navy, width: 0 },
  });
  s.addText("Type hints  ·  Docstrings  ·  Cross-platform  ·  YAML config  ·  REST API  ·  Webhook  ·  Tek komut demo", {
    x: 0.5, y: 4.85, w: 9.0, h: 0.5, fontSize: 11, italic: true,
    color: "CADCFC", align: "center", valign: "middle",
    fontFace: FONT_BODY, margin: 0,
  });

  footer(s, 16);
  s.addNotes("Sadece çalışan prototip değil — bakım yapılabilir, test edilebilir yazılım. 50 birim test her commit'te otomatik çalışır. Gerçek üretim kalitesi standardı.");
}

// SLAYT 17 — SONUÇLAR & DEMO
{
  const s = p.addSlide();
  lightBg(s);
  eyebrow(s, "Sonuçlar");
  bigTitle(s, "Başarım ve Canlı Demo");

  // Sol — metrikler grid (4 kart)
  const metrics = [
    { n: "0.93", l: "Sentetik mAP50", c: C.green },
    { n: "0.60", l: "Gerçek mAP50",   c: C.amber },
    { n: "16+",  l: "FPS (MPS M4)",   c: C.blue },
    { n: "<1s",  l: "Tespit gecikmesi", c: C.orange },
  ];
  const mw = 2.0, mh = 1.4, mgap = 0.15;
  metrics.forEach((m, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = 0.5 + col * (mw + mgap), y = 1.75 + row * (mh + mgap);
    s.addShape(p.shapes.RECTANGLE, {
      x, y, w: mw, h: mh,
      fill: { color: C.card }, line: { color: C.border, width: 0.5 }, shadow: cardShadow(),
    });
    s.addText(m.n, {
      x, y: y + 0.15, w: mw, h: 0.8, fontSize: 36, bold: true,
      color: m.c, align: "center", valign: "middle",
      fontFace: FONT_TITLE, margin: 0,
    });
    s.addText(m.l, {
      x, y: y + 0.95, w: mw, h: 0.4, fontSize: 11,
      color: C.muted, align: "center", fontFace: FONT_BODY, margin: 0,
    });
  });

  // Sağ: demo ekran görüntüsü
  try {
    s.addImage({
      path: ROOT + "/web/screenshots/demo_synthetic_1.jpg",
      x: 5.0, y: 1.75, w: 4.6, h: 2.7,
      sizing: { type: "contain", w: 4.6, h: 2.7 },
    });
  } catch (e) { /* skip */ }

  s.addText("Sistem 2 yangın tespit ediyor + heatmap + FIRE etiketi", {
    x: 5.0, y: 4.5, w: 4.6, h: 0.3, fontSize: 10, italic: true,
    color: C.muted, align: "center", fontFace: FONT_BODY,
  });

  // Alt: tek-komut demo — footer ile çakışmasın diye yukarı çek + alçalt
  s.addShape(p.shapes.RECTANGLE, {
    x: 0.5, y: 4.7, w: 9.0, h: 0.45,
    fill: { color: "1F2937" }, line: { color: "1F2937", width: 0 },
  });
  s.addText([
    { text: "$  ", options: { color: C.faint } },
    { text: "./run_demo.sh synthetic", options: { color: "10B981", bold: true } },
    { text: "    →  ", options: { color: C.faint } },
    { text: "tarayıcı otomatik açılır, demo başlar", options: { color: "CBD5E1", italic: true } },
  ], {
    x: 0.7, y: 4.7, w: 8.8, h: 0.45, fontSize: 11,
    fontFace: "Consolas", valign: "middle", margin: 0,
  });

  footer(s, 17);
  s.addNotes("3 farklı modda demo: sentetik, webcam, ESP32. Şimdi canlı demo yapacağım. Sistem 2 yangını otomatik tespit ediyor, mesafe ölçüyor, risk haritası gösteriyor.");
}

// SLAYT 18 — SONUÇ VE GELECEK
{
  const s = p.addSlide();
  lightBg(s);
  eyebrow(s, "Değerlendirme");
  bigTitle(s, "Sonuç ve Gelecek Çalışmalar");

  // Sol: kazanımlar
  s.addText("KAZANIMLAR", { x: 0.5, y: 1.7, w: 4.5, h: 0.3, fontSize: 11, bold: true, color: C.green, charSpacing: 3, fontFace: FONT_BODY });
  s.addText([
    { text: "✓ ", options: { color: C.green, bold: true } },
    { text: "7000+ satır kod, 50 birim test", options: { color: C.text, breakLine: true } },
    { text: "✓ ", options: { color: C.green, bold: true } },
    { text: "13 modüler AI bileşeni", options: { color: C.text, breakLine: true } },
    { text: "✓ ", options: { color: C.green, bold: true } },
    { text: "Hibrit: DL + klasik CV", options: { color: C.text, breakLine: true } },
    { text: "✓ ", options: { color: C.green, bold: true } },
    { text: "Çapraz platform (macOS, Windows)", options: { color: C.text, breakLine: true } },
    { text: "✓ ", options: { color: C.green, bold: true } },
    { text: "3 algoritma sınıfı entegrasyonu", options: { color: C.text } },
  ], {
    x: 0.5, y: 2.05, w: 4.5, h: 2.0, fontSize: 12, fontFace: FONT_BODY,
  });

  // Sol alt: sınırlamalar
  s.addText("SINIRLAMALAR", { x: 0.5, y: 4.2, w: 4.5, h: 0.3, fontSize: 11, bold: true, color: C.red, charSpacing: 3, fontFace: FONT_BODY });
  s.addText("• Çok küçük alev (<30px) zorlu — dataset sınırı\n• Aşırı parlak ortam kontrast düşürür\n• Wi-Fi mesafesi ~30-50 m (ESP32)", {
    x: 0.5, y: 4.5, w: 4.5, h: 0.9, fontSize: 10, color: C.muted, fontFace: FONT_BODY,
  });

  // Sağ: gelecek çalışmalar
  s.addText("GELECEK ÇALIŞMALAR", { x: 5.3, y: 1.7, w: 4.2, h: 0.3, fontSize: 11, bold: true, color: C.orange, charSpacing: 3, fontFace: FONT_BODY });
  const futures = [
    { ico: "🌡", t: "Termal kamera entegrasyonu" },
    { ico: "💨", t: "CO₂ söndürme mekanizması" },
    { ico: "🤝", t: "Çoklu robot koordinasyonu" },
    { ico: "🔁", t: "Active Learning MLOps pipeline" },
    { ico: "🏗", t: "Termoplastik 3D baskı şasi" },
  ];
  futures.forEach((f, i) => {
    const y = 2.05 + i * 0.55;
    s.addShape(p.shapes.RECTANGLE, {
      x: 5.3, y, w: 4.2, h: 0.45,
      fill: { color: C.card }, line: { color: C.border, width: 0.5 },
    });
    s.addText(f.ico, {
      x: 5.4, y, w: 0.5, h: 0.45, fontSize: 16,
      align: "left", valign: "middle", margin: 0,
    });
    s.addText(f.t, {
      x: 5.95, y, w: 3.5, h: 0.45, fontSize: 12,
      color: C.text, valign: "middle", fontFace: FONT_BODY, margin: 0,
    });
  });

  footer(s, 18);
  s.addNotes("Projemizi sadece bitirme tezi olarak değil, gerçek dünyada kullanılabilir bir prototip olarak tasarladık. Açık kaynak olarak yayınlıyoruz. Gelecekte termal kamera ve söndürme mekanizması ile tam fonksiyonel hale getirebiliriz.");
}

// SLAYT 19 — TEŞEKKÜRLER
{
  const s = p.addSlide();
  darkBg(s);

  // Büyük teşekkürler
  s.addText("Teşekkürler", {
    x: 0.5, y: 1.5, w: 9, h: 1.3, fontSize: 72, bold: true,
    color: "FFFFFF", align: "center", fontFace: FONT_TITLE,
  });

  s.addText("Sorularınız?", {
    x: 0.5, y: 2.9, w: 9, h: 0.6, fontSize: 24, italic: true,
    color: C.orange, align: "center", fontFace: FONT_TITLE,
  });

  // Alt — bilgiler
  s.addShape(p.shapes.RECTANGLE, {
    x: 1, y: 4.0, w: 8, h: 1.2,
    fill: { color: "FFFFFF", transparency: 92 },
    line: { color: "FFFFFF", width: 0.5 },
  });

  // Sol kolon
  s.addText([
    { text: "Sema Nur Işık", options: { color: "FFFFFF", bold: true, fontSize: 14, breakLine: true } },
    { text: "& Efe Düzçay",   options: { color: "FFFFFF", bold: true, fontSize: 14 } },
  ], {
    x: 1.3, y: 4.15, w: 3.5, h: 0.9, fontFace: FONT_BODY, valign: "middle",
  });

  // Sağ kolon - linkler
  s.addText([
    { text: "🐙 ", options: { fontSize: 11 } },
    { text: "github.com/efeduzcay/robotproje123", options: { color: "CADCFC", fontSize: 11, breakLine: true } },
    { text: "🌐 ", options: { fontSize: 11 } },
    { text: "mesleki-proje.github.io/web-sitesi", options: { color: "CADCFC", fontSize: 11, breakLine: true } },
    { text: "🏛 ", options: { fontSize: 11 } },
    { text: "Piri Reis Üniversitesi · BIP 2012", options: { color: "FFFFFF", fontSize: 11, italic: true } },
  ], {
    x: 5.0, y: 4.15, w: 4.0, h: 0.9, fontFace: FONT_BODY, valign: "middle",
  });

  s.addNotes("Sunum sonu. Soru-cevap için hazırız. Demo henüz açılmadıysa şimdi açıp gösterebiliriz.");
}


// Yaz
p.writeFile({ fileName: OUT }).then(() => {
  console.log(`✓ Çıktı: ${OUT}`);
}).catch((e) => {
  console.error("✗ Hata:", e);
  process.exit(1);
});
