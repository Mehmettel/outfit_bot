# GitHub'a Yükleme Talimatları

## 1. Git Kimlik Ayarları (İlk Kez)

Eğer daha önce yapmadıysanız, terminalde şu komutları çalıştırın:

```bash
git config --global user.email "sizin@email.com"
git config --global user.name "Adınız Soyadınız"
```

## 2. İlk Commit

```bash
cd "c:\Users\TEL\Desktop\file_pdf\Projeler ve yetkinlikler\outfit_bot"
git commit -m "Initial commit: Outfit Bot - Telegram style assistant with Gemini AI"
```

## 3. GitHub'da Yeni Repo Oluşturma

1. GitHub.com'a gidin ve giriş yapın
2. Sağ üstten **"+"** → **"New repository"** seçin
3. Repository adı: `outfit_bot` (veya istediğiniz isim)
4. **Public** seçin
5. **"Create repository"** butonuna tıklayın
6. **"Initialize this repository with a README"** seçmeyin (zaten var)

## 4. Projeyi GitHub'a Yükleme

GitHub'da oluşturduğunuz repo sayfasında gösterilen komutları kullanın:

```bash
git remote add origin https://github.com/KULLANICI_ADINIZ/outfit_bot.git
git branch -M main
git push -u origin main
```

**Not:** `KULLANICI_ADINIZ` yerine kendi GitHub kullanıcı adınızı yazın.

## Güvenlik Uyarısı

- .env dosyası **asla** GitHub'a yüklenmeyecek (.gitignore'da)
- Yeni bir ortamda çalıştırmak için: `.env.example`'ı `.env`'e kopyalayıp API anahtarlarınızı girin
