# Arkadaşa Talimat — OYTS Windows .exe Üretimi

Selam! Bu klasör OYTS projesinin Windows .exe'sini üretmek için gerekli her şeyi içeriyor. **15-30 dakikalık iş**, adımlar net.

---

## Önkoşullar (bir kerelik kurulum)

### 1. Python 3.10+ kur
- https://www.python.org/downloads/ → "Download Python 3.10.x"
- ⚠️ Kurarken **"Add Python to PATH"** kutucuğunu işaretle

### 2. Inno Setup 6.3+ kur (installer için)
- https://jrsoftware.org/isdl.php → "Download Inno Setup 6.x"
- Varsayılan dizine kur (`C:\Program Files (x86)\Inno Setup 6\`)

### 3. Görsel Studio Build Tools (opsiyonel)
- Çoğu pakette gerek yok. Eğer `pip install` sırasında "Microsoft Visual C++ 14.0 is required" hatası alırsan:
- https://visualstudio.microsoft.com/visual-cpp-build-tools/

---

## Build Adımları

### 1. Projeyi indir
```cmd
git clone https://github.com/efeduzcay/robotproje123.git
cd robotproje123
```

(Veya zip'i çöz.)

### 2. Build klasörüne gir
```cmd
cd build_windows
```

### 3. Tek komutla build
```cmd
build_windows.bat
```

Bu komut sırasıyla:
1. Python venv oluşturur
2. requirements.txt + pyinstaller kurar
3. PyInstaller ile `.exe` paketler → `dist\OYTS\OYTS.exe`
4. Inno Setup varsa installer derler → `Output\OYTS-Setup-3.1.1.exe`

**İlk çalıştırma 5-10 dk** sürer (torch + ultralytics büyük, 1.5 GB indirir).
İkinci çalıştırmadan sonra 1-2 dk.

---

## Çıktı

İki şey üretilir:

### `dist\OYTS\OYTS.exe`
Doğrudan çalışan .exe. Klasör içinde **~400-600 MB** dosya var (torch, ultralytics, model). Tek başına taşınabilir.

```cmd
dist\OYTS\OYTS.exe              REM Sentetik mod (varsayılan)
dist\OYTS\OYTS.exe --source webcam
dist\OYTS\OYTS.exe --source esp32
```

### `Output\OYTS-Setup-3.1.1.exe`
Inno Setup installer (~250 MB sıkıştırılmış). Hoca'ya bunu ver — çift tıkla, sihirbaz açılır, Türkçe arayüz, masaüstüne kısayol oluşturur.

---

## Test

`.exe`'yi çalıştırınca:
1. Konsol penceresi açılır, başlangıç logları akar
2. ~3 saniye sonra tarayıcı otomatik açılır: `http://127.0.0.1:8765/index.html`
3. Sağ üstte **🔴 Canlı Demo** butonu → demo sayfası
4. Sentetik modda 2 yangın bbox görünmeli, FPS ~10

---

## Sorun çıkarsa

### "ModuleNotFoundError: No module named ..."
Eksik bir hidden import var. `oyts_launcher.spec` içinde `hiddenimports = [...]` listesine ekle, tekrar build et.

### "PyInstaller exited with code 1"
Genelde dependency çakışması. Şu komutu çalıştır:
```cmd
venv\Scripts\activate.bat
python -m pip install --upgrade ultralytics pyinstaller
build_windows.bat
```

### "Windows Defender SmartScreen engelledi"
İmzalı sertifika yok. Test için "More info" → "Run anyway".

### "Inno Setup bulunamadı"
`ISCC.exe`'nin yolu `oyts_setup.iss` veya `build_windows.bat` içinde sabit. Farklıysa düzelt:
```bat
set ISCC="C:\Senin\Yolun\ISCC.exe"
```

### Çok büyük dosya (~400 MB+)
PyInstaller torch'u içeri alıyor. Boyutu küçültmek için:
1. `oyts_launcher.spec` içinde `excludes = ["torch.distributions", "scipy.tests", ...]` listesi var
2. Daha agresif olmak için: `pip install torch --index-url https://download.pytorch.org/whl/cpu`
   (CUDA paketi 2GB; CPU-only ~200MB)

---

## Konsol penceresini gizle (opsiyonel)

PyInstaller spec'te `console=True` yazıyor — log görünür. Gizli istersen:
```python
# oyts_launcher.spec içinde:
exe = EXE(...
    console=False,  # ← True yerine False
    ...)
```

Ama log görünmeyince debug zor. Tavsiyem **bırak True**.

---

## Sorun yoksa bana bir ekran görüntüsü at, Hoca'ya verebilirsin 👍

— Efe
