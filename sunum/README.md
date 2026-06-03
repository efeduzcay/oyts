# Sunum Klasörü

Bu klasör BIP 2012 bitirme projesi sunumu için hazırlanan **metin + medya** içerir.

## İçerik

| Dosya | Açıklama |
|---|---|
| `sunum_metni.md` | **Ana sunum metni** — 18 slayt, başlık + içerik + konuşmacı notları |
| `README.md` | Bu dosya |

## Nasıl Kullanılır?

### 1. PowerPoint Oluştur
1. `sunum_metni.md` dosyasını oku
2. Her "# SLAYT N" bölümü bir PowerPoint slaydına denk gelir
3. Önerilen tasarım:
   - **Renkler:** Ana mavi `#0047AB`, vurgu turuncu `#FF6B35`
   - **Font:** Inter veya Montserrat
   - **Animasyon:** Hafif fade-in, alev için pulse
4. Görsellerinizi `web/photo/` ve `web/screenshots/` klasöründen alın

### 2. Speaker Notes Ekle
Her slayttaki "Konuşma Notu" bölümünü PowerPoint'in **Notes** alanına kopyalayın.

### 3. Demo Hazırlığı
Sunumdan önce terminal'de:
```bash
cd ~/Desktop/robot-3.0.0
./run_demo.sh synthetic
```

Tarayıcıyı **F11** ile full-screen yap. Slayt 17'ye geldiğinde Cmd+Tab ile geç.

## Sunum İstatistikleri

- **Slayt sayısı:** 18 (+ 1 bonus teşekkür)
- **Tahmini süre:** 9-13 dakika
- **Hedef kitle:** Akademik jüri + danışman hocalar

## İçerik Akışı

```
1.  Kapak
2.  Proje Tanıtımı
3.  Sorun
4.  Mevcut Çözümler
5.  OYTS Çözümümüz
6.  Mimari (3 katman)
7.  Donanım
8.  Katman 1: ESP32-CAM
9.  Katman 2: Arduino Mega
10. Katman 3: PC + YOLOv8
11. Algoritma 1: YOLOv8
12. Algoritma 2: Bulanık Mantık
13. Algoritma 3: Simulated Annealing
14. Multi-Signal Validator
15. Sentetik Simülasyon
16. Yazılım Mimarisi + Testler
17. Sonuçlar & Demo
18. Sonuç + Gelecek Çalışmalar
19. Teşekkürler (bonus)
```

## Renk Paleti (PowerPoint için)

| Renk | Hex | Kullanım |
|---|---|---|
| Ana Mavi | `#0047AB` | Başlıklar, vurgular |
| Koyu Mavi | `#001f4d` | Hero arka plan |
| Turuncu | `#FF6B35` | Aksent, CTA |
| Açık Mavi | `#F8FAFF` | Slayt arka planı |
| Koyu Metin | `#1a202c` | Gövde metin |
| Açık Gri | `#64748b` | İkincil metin |

## Görsel Kaynaklar

Görseller `web/` klasöründe:
- `web/photo/photo1.jpg` — Devre + bileşenler
- `web/photo/photo2.jpeg` — Robot şasi
- `web/photo/photo3.jpeg` — Robot bağlantı
- `web/screenshots/demo_synthetic_1.jpg` — Sistem çıktısı
- `web/screenshots/demo_synthetic_2.jpg` — Heatmap
- `web/screenshots/demo_synthetic_3.jpg` — Multi-track

## Sunumdan Sonra

Q&A için olası sorular ve cevaplar:
- **"Neden YOLOv8 ve başka bir model değil?"** → Hız + doğruluk dengesi, gerçek zamanlı edge cihaz için optimize
- **"Bulanık mantık yerine neden klasik kural yok?"** → Sınır belirsizliği problemi (1 pikselin kategori değiştirmesi)
- **"Sentetik veriyle eğitilen model gerçek dünyada çalışır mı?"** → Mixed eğitim ile evet, ama validator gerçek dünyada kritik
- **"Maliyet ne?"** → Donanım ~600-800 TL (PC hariç)
- **"Açık kaynak mı?"** → Evet, GitHub'da
- **"Sınırları neler?"** → Çok küçük alev (<30px), aşırı parlak ortam, Wi-Fi mesafesi
