# 👔 Outfit Bot - Personal Style Assistant

Telegram üzerinden çalışan, Google Gemini AI ile kıyafet fotoğraflarını analiz eden kişisel stil asistanı.

## ✨ Özellikler

- **4 Analiz Modu:**
  - 👔 Business Wardrobe - Profesyonel iş kombinleri
  - 💰 Budget Style - Ekonomik ve şık öneriler
  - 🎯 Trend Analyst - Güncel moda trendleri
  - 🎉 Special Event - Düğün, mezuniyet vb. özel günler için

- **Favori Yönetimi:** Kombinleri kaydedin, sonradan görüntüleyin
- **Son Analiz:** /last komutu ile son analizi tekrar görüntüleyin
- **Fotoğraf İpuçları:** Daha iyi fotoğraflar için rehberlik

## 🚀 Kurulum

### Gereksinimler

- Python 3.11+
- Telegram Bot Token ([@BotFather](https://t.me/BotFather))
- Google Gemini API Key ([Google AI Studio](https://aistudio.google.com/))

### Adımlar

1. **Projeyi klonlayın:**
   ```bash
   git clone https://github.com/kullaniciadi/outfit_bot.git
   cd outfit_bot
   ```

2. **Sanal ortam oluşturun (önerilir):**
   ```bash
   python -m venv venv
   venv\Scripts\activate   # Windows
   # veya: source venv/bin/activate  # Linux/Mac
   ```

3. **Bağımlılıkları yükleyin:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Ortam değişkenlerini ayarlayın:**
   ```bash
   copy .env.example .env   # Windows
   # veya: cp .env.example .env  # Linux/Mac
   ```
   `.env` dosyasını düzenleyip `TELEGRAM_TOKEN` ve `GEMINI_API_KEY` değerlerinizi girin.

5. **Botu başlatın:**
   ```bash
   python main.py
   ```

## 📱 Komutlar

| Komut | Açıklama |
|-------|----------|
| /start | Botu başlat, mod seç |
| /help | Yardım menüsü |
| /tips | Fotoğraf çekim ipuçları |
| /faq | Sık sorulan sorular |
| /favorites | Favori kombinleri görüntüle |
| /save | Son analizi favorilere kaydet |
| /last | Son analizi göster |
| /delete_favorite \<id\> | Favori sil |
| /finish | Oturumu sonlandır |

## 📁 Proje Yapısı

```
outfit_bot/
├── main.py           # Ana uygulama (çalıştırılacak dosya)
├── mainsave.py       # Türkçe backup sürüm (kullanılmıyor)
├── database.py       # SQLite veritabanı işlemleri
├── error_handler.py  # Hata yönetimi
├── quick_actions.py  # Hızlı aksiyonlar (favori, son analiz)
├── requirements.txt
├── .env.example      # Ortam değişkenleri şablonu
└── README.md
```

## ⚠️ Önemli Notlar

- `.env` dosyası API anahtarlarınızı içerir - **asla** GitHub'a yüklemeyin!
- Veritabanı (`bot_data.db`) ilk çalıştırmada otomatik oluşturulur

## 📄 Lisans

MIT License
