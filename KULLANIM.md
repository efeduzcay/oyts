# OYTS — Kullanım (Sıfır Bilgi ile Çalıştırma)

Bu proje çift tıkla başlar. **Önerilen yol: tek arayüzlü launcher.**

## En kolay yol — Tek arayüz

| macOS              | Windows         | Ne yapar                                |
|--------------------|-----------------|-----------------------------------------|
| `Baslat.command`   | `Baslat.bat`    | Tek pencerede 3 buton (kameralı / simülasyon / durdur), durum göstergesi, "Tarayıcıyı Aç", log paneli |

Çift tıkla → küçük bir uygulama penceresi açılır → istediğin moda bas → her şey
otomatik. Tarayıcı, kütüphane kurulumu, izin paneli, hepsi launcher içinden.

## İleri kullanım — Doğrudan modlar

Eğer her seferinde doğrudan belirli bir modu açmak istersen:

### macOS

| Dosya                       | Ne yapar                                         |
|-----------------------------|--------------------------------------------------|
| `Baslat-Kamera.command`     | Webcam'le canlı yangın tespiti                   |
| `Baslat-Simulasyon.command` | Kamerasız sentetik yangın gösterimi              |
| `Durdur.command`            | Açık olan tüm sunucuları kapatır                 |

**İlk açılışta:**
1. macOS "tanımlanamayan geliştirici" diyebilir → Finder'da dosyaya
   **sağ tıklayıp "Aç" → "Aç"** deyin (sadece ilk seferde).
2. Terminal açılır, eksik kütüphaneler otomatik yüklenir (~1-3 dk).
3. Kamera ilk kez kullanılırken macOS izin sorar → "İzin Ver" deyin.
4. Tarayıcı kendiliğinden açılır, canlı görüntü gelir.

**Kamera izni daha sonra reddedilmişse:** Doctor otomatik olarak
**System Settings → Privacy & Security → Camera** panelini açar; listede
**Terminal** (veya başlatıcı uygulamayı) açın, Terminal'i Cmd+Q ile
tamamen kapatıp `Baslat-Kamera.command`'i tekrar çift tıklayın.

## Windows

| Dosya             | Ne yapar                            |
|-------------------|-------------------------------------|
| `run_webcam.bat`  | Webcam'le canlı yangın tespiti       |
| `run_sim.bat`     | Kamerasız sentetik yangın gösterimi  |
| `stop.bat`        | Açık olan tüm sunucuları kapatır     |

**İlk açılışta:**
1. Çift tıklayın.
2. SmartScreen uyarısı çıkarsa "Daha fazla bilgi → Yine de çalıştır" deyin.
3. Eksik kütüphaneler otomatik yüklenir (~2-5 dk).
4. Kamera izni sorulursa "İzin Ver" deyin.
5. Tarayıcı kendiliğinden açılır.

**Kamera izni reddedilmişse:** Doctor otomatik olarak
**Ayarlar → Gizlilik → Kamera** sayfasını açar; "Masaüstü uygulamalarının
kameraya erişmesine izin ver" açık olmalı.

## Gereksinim

Sadece **Python 3.9+** kurulu olmalı. Yoksa kurulum bağlantısı için:
<https://www.python.org/downloads/>

Kurarken **"Add Python to PATH"** kutusunu işaretleyin (Windows).

Gerisi (OpenCV, YOLO, Flask, model dosyası vs.) ilk açılışta otomatik gelir.

## Sorun mu var?

Terminal/CMD penceresindeki son satırı oku — ne yapacağın orada yazıyor.
Hiçbir şey olmuyorsa **`Durdur.command` / `stop.bat`** ile temizle, sonra
**Baslat-Simulasyon.command / run_sim.bat** (kamerasız) ile sistemin
çalıştığını doğrula. Yangın simülasyonu gelmiyorsa modeli kontrol et:

```
python -m utils.doctor
```

Bütün kontroller yeşilse sistem hazırdır.
