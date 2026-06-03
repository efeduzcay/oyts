OYTS - Otonom Yangin Tespit Sistemi
=====================================
Windows Edition - Kurulum ve Kullanim

KURULUM
-------
OYTS-Setup-3.1.1.exe dosyasini cift tikla, sihirbazdaki adimlari izle.
- Yonetici (admin) izni gerek YOK.
- Varsayilan kurulum dizini: C:\Users\<KullaniciAdi>\AppData\Local\OYTS
- Masaustune kisayol otomatik olusur (istersen kaldirilabilir).

CALISTIRMA
----------
3 farkli baslatma kisayolu vardir (Baslat menusunde OYTS klasoru icinde):

  1. OYTS (Simulasyon)    — Donanim gerekmez. Sentetik yangin sahnesi
                            uzerinde sistem calisir, taraicida acilir.

  2. OYTS (Webcam)        — Bilgisayar kamerasi kullanir.
                            Cakmak/mum/yangin videosu ile test edilebilir.

  3. OYTS (ESP32-CAM)     — Wi-Fi uzerinden ESP32-CAM stream'ine baglanir.
                            Once robot ESP32-CAM IP'sini configs/config_webcam.yaml
                            icinde guncelle (connection.stream_url).

UI ARAYUZU
----------
Calisma sirasinda otomatik acilan tarayicida:
  http://127.0.0.1:8765/index.html   - Tanitim sayfasi
  http://127.0.0.1:8765/live.html    - Canli demo + kontroller

Manuel surus icin:
  W/A/S/D : Ileri / Sol / Sag / Geri
  X       : Dur
  K / L   : Servo kol asagi / yukari

KAPATMA
-------
Konsol penceresini kapat (kosesindeki X) veya pencerenin icinde Ctrl+C bas.

YENI YANGIN MODELI
------------------
fire_model.pt dosyasini degistirebilirsin (yeni egitilmis bir model).
  C:\Users\<Sen>\AppData\Local\OYTS\python\fire_model.pt

Mevcut yedek modeller:
  fire_model_v3_real.pt        - orijinal real-only model
  fire_model_v311_mixed.pt     - sentetik+real karisik
  fire_model_roboflow.pt       - Roboflow dataset fine-tune (varsayilan)

KONFIGURASYON
-------------
configs/config_webcam.yaml     - Webcam/ESP32 modu icin
configs/config.yaml            - Sentetik modu icin

Onemli alanlar:
  ai.conf_threshold            - YOLO algilama esigi (0.10-0.40 arasi)
  ai.validator_bypass_conf     - Bu degerin ustunde validator atlanir
  fire_validator.min_score     - Validator composite esigi (0.15-0.45)
  bright_flame_detector.enabled- Cakmak gibi kucuk alev tespit modulu

DESTEK
------
Akademik proje - Piri Reis Universitesi BIP 2012
Gelistirici: Sema Nur Isik & Efe Duzcay
Repo: https://github.com/efeduzcay/robotproje123

SORUN GIDERME
-------------
1. "Windows Defender uyariyor"
   .exe imzasiz oldugu icin normal. "Yine de calistir" sec.

2. "Kamera acilmiyor"
   Windows Privacy & Security > Camera ayarlarinda OYTS'ye izin ver.

3. "Yangin algilamiyor"
   Cakmagi kameranin 20-30cm onunde, odanin isigi azaltilmis tut.

4. "Cok yavas"
   - 8GB+ RAM oneririz
   - GPU yoksa FPS ~3-5'tir (CPU)
   - imgsz 640 yerine 480 yaparsan ~2x hizlanir
     (configs/config_webcam.yaml > ai.imgsz)

5. "Backend acilmiyor"
   Port 5050 baska bir uygulamada olabilir. Diger uygulamayi kapat
   veya komut satirindan:
     OYTS.exe --backend-port 5051 --frontend-port 8766
