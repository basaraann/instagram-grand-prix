# 🏁 Instagram Grand Prix

Instagram takipçilerini profil fotoğraflarıyla bir yarış pistine dizip yarıştıran, yarışı video olarak kaydeden tarayıcı tabanlı animasyon. Tek bir HTML dosyası, kurulum gerektirmez.

**Canlı demo:** https://basaraann.github.io/instagram-grand-prix/

## Özellikler

- **Pistler:** Monaco, Silverstone, İstanbul, Spa-Francorchamps, Suzuka, Nürburgring, ZigZag, Kalp Pisti, Sonsuzluk, Tornado, Hız Ovası
- **Temalar:** Çöl, Çim, Gece, Şehir
- **Kamera:** lideri takip eden yakın çekim veya tüm pisti gösteren geniş açı
- **Yarışçı sayısı:** 50 ile 500.000 arası; veri yüklenmezse `@takipci1`, `@takipci2`… isimli örnek yarışçılarla çalışır
- **Video:** yarışı `.webm` olarak kaydetme, kendi müziğini ve efekt videonu ekleme
- **Yazılar:** takipçi sayısı ve gün numarası ("342.234 FOLLOWER", "DAY 5") video üstünde gösterilir
- **Sonuçlar:** sıralamayı `.json` olarak indirme

## Hızlı başlangıç

`index.html` dosyasını Chrome'da aç (ya da yukarıdaki canlı demoyu kullan). React ve Tailwind CDN'den yüklendiği için internet bağlantısı gerekir.

Veri yüklemeden direkt başlatıp deneyebilirsin. Kendi takipçilerinle yarıştırmak için iki yol var:

1. **Sadece isimler:** Instagram'dan indirdiğin `followers_1.html` dosyasını sayfaya sürükle. Kullanıcı adları gelir, profil fotoğrafı gelmez (Instagram'ın dışa aktarımında fotoğraf yok).
2. **İsim + fotoğraf:** her dosyanın adı kullanıcı adı olacak şekilde (`kullaniciadi.jpg`) profil fotoğraflarından oluşan klasörü sayfaya sürükle. Bu klasörü `scraping/` içindeki botlarla oluşturabilirsin.

### Instagram verisini indirme

Instagram → Ayarlar → Hesaplar Merkezi → Bilgilerin ve izinlerin → Bilgilerini dışa aktar. Format olarak **HTML**, kapsam olarak **Takipçiler ve takip edilenler** seç. Gelen arşivdeki `followers_1.html` lazım olan dosya.

## `scraping/` klasörü

| Dosya | Ne yapar |
| --- | --- |
| `scrape_bot.py` | Selenium ile Chrome açar, sen elle giriş yaparsın, profilleri tek tek gezip fotoğrafları indirir. Yavaş ama basit. |
| `scrape_bot1.py` | Instaloader ile fotoğraf adreslerini toplar, aiohttp ile paralel indirir. Fotoğrafı bulunamayanlar için beyaz yer tutucu oluşturur. Daha hızlı. |
| `racerupdate.html` | Fotoğraf klasörünü güncel takipçi listesiyle karşılaştırır: yeni takipçileri (fotoğrafı eksik olanlar) ve takibi bırakanları gösterir, sadece güncel takipçilerden oluşan `racers_temizlenmis.zip` dosyasını indirir. |

İki bot da aynı klasördeki `followers_1.html`'i okur, fotoğrafları `racers/` klasörüne indirir ve `racer_data.json` dosyasını üretir (biçimi için `racer_data.example.json`'a bak).

```bash
cd scraping
pip install -r requirements.txt
python scrape_bot1.py
```

## Notlar

- Instagram, kullanım koşullarında otomatik veri toplamaya izin vermiyor; çok sayıda istek atan hesaplar geçici olarak kısıtlanabilir. Botları kendi sorumluluğunda ve kendi hesabının takipçileriyle kullan.
- `followers_1.html`, `racer_data.json` ve `racers/` başka insanların verisini içerdiği için `.gitignore` ile repoya dahil edilmez. Fork'larsan sen de yükleme.
