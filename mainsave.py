import os
from dotenv import load_dotenv
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
from PIL import Image
import io
import logging
import json
from datetime import datetime
from database import Database
from error_handler import ErrorHandler

# Veritabanı ve hata yönetimi bağlantıları
db = Database()
error_handler = ErrorHandler()

# Loglama ayarları
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_EVENT = 1

# Fotoğraf çekim ipuçları
PHOTO_TIPS = """
📸 Fotoğraf Çekim İpuçları:

1. İyi Aydınlatma:
   • Doğal gün ışığını tercih edin
   • Gölge oluşturmaktan kaçının

2. Doğru Açı:
   • Kıyafeti tam gösteren bir açı seçin
   • Yakın plan çekim yapın

3. Net Görüntü:
   • Kamerayı sabit tutun
   • Odaklamayı doğru yapın

4. Arka Plan:
   • Sade bir arka plan seçin
   • Dağınıklıktan kaçının
"""

# Sık sorulan sorular
FAQ = """
❓ Sık Sorulan Sorular:

1. Bot nasıl çalışır?
   • Fotoğrafınızı yapay zeka ile analiz eder
   • Seçtiğiniz moda göre öneriler sunar

2. Hangi modları kullanabilirim?
   • İş Gardırobu Asistanı
   • Ekonomik Stil Rehberi
   • Trend Analisti
   • Özel Durum Danışmanı

3. Favorileri nasıl kullanabilirim?
   • /save komutu ile kombini kaydedin
   • /favorites ile kayıtlarınızı görüntüleyin

4. Modu nasıl değiştirebilirim?
   • "Modu Değiştir" butonunu kullanın
   • veya /start ile yeniden başlayın
"""

# .env dosyasından API anahtarlarını yükle
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Gemini API yapılandırması
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Kullanıcı verilerini saklamak için dictionary'ler
user_preferences = {}
user_states = {}
user_events = {}
user_favorites = {}  # Kullanıcıların favori kombinlerini saklamak için

async def split_and_send_message(update: Update, text: str, reply_markup=None):
    """Uzun mesajları parçalara bölerek gönder"""
    MAX_MESSAGE_LENGTH = 4000  # Telegram sınırından biraz daha az
    
    # Mesajı paragraflarına böl
    paragraphs = text.split('\n\n')
    current_message = ""
    
    for paragraph in paragraphs:
        # Eğer paragraf eklendiğinde mesaj çok uzun olacaksa, mevcut mesajı gönder
        if len(current_message) + len(paragraph) + 2 > MAX_MESSAGE_LENGTH:
            await update.message.reply_text(current_message)
            current_message = paragraph
        else:
            if current_message:
                current_message += "\n\n"
            current_message += paragraph
    
    # Son mesajı reply_markup ile gönder
    if current_message:
        await update.message.reply_text(current_message, reply_markup=reply_markup)

async def save_favorite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Favori kombini kaydet"""
    try:
        user_id = update.message.from_user.id
        
        if hasattr(context.user_data, 'last_analysis'):
            mode = db.get_user_preference(user_id) or 'genel'
            db.add_favorite(user_id, context.user_data['last_analysis'], mode)
            await update.message.reply_text("✨ Bu kombin favorilerinize eklendi!")
        else:
            await update.message.reply_text("❌ Henüz kaydedilecek bir analiz bulunamadı.")
    except Exception as e:
        await error_handler.handle_database_error(update, e)

async def show_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Favori kombinleri göster"""
    try:
        user_id = update.message.from_user.id
        favorites = db.get_user_favorites(user_id)
        
        if not favorites:
            await update.message.reply_text("Henüz kaydedilmiş bir favoriniz bulunmuyor.")
            return
        
        # Sayfa başına gösterilecek favori sayısı
        FAVORITES_PER_PAGE = 2  # Sayfa başına favori sayısını azalttım
        
        # Toplam sayfa sayısını hesapla
        total_pages = (len(favorites) + FAVORITES_PER_PAGE - 1) // FAVORITES_PER_PAGE
        
        # Mevcut sayfayı al (varsayılan: 1)
        current_page = context.user_data.get('favorites_page', 1)
        
        # Sayfa için başlangıç ve bitiş indekslerini hesapla
        start_idx = (current_page - 1) * FAVORITES_PER_PAGE
        end_idx = min(start_idx + FAVORITES_PER_PAGE, len(favorites))
        
        # Sayfa içeriğini oluştur
        favorites_text = f"🌟 Favori Kombinleriniz (Sayfa {current_page}/{total_pages}):\n\n"
        
        for i, (fav_id, analysis, mode, created_at) in enumerate(favorites[start_idx:end_idx], start_idx + 1):
            favorites_text += f"Favori #{i} (ID: {fav_id})\n"
            favorites_text += f"Tarih: {created_at}\n"
            favorites_text += f"Mod: {mode.title()}\n"
            favorites_text += f"Analiz:\n{analysis}\n"
            favorites_text += "─" * 30 + "\n\n"
        
        # Sayfalama ve silme butonlarını oluştur
        keyboard = []
        
        # Silme butonları
        delete_buttons = [
            InlineKeyboardButton("🗑️ Tümünü Sil", callback_data='delete_all_favorites')
        ]
        keyboard.append(delete_buttons)
        
        # Sayfalama butonları
        if total_pages > 1:
            nav_buttons = []
            if current_page > 1:
                nav_buttons.append(InlineKeyboardButton("⬅️ Önceki", callback_data='prev_favorites'))
            if current_page < total_pages:
                nav_buttons.append(InlineKeyboardButton("Sonraki ➡️", callback_data='next_favorites'))
            keyboard.append(nav_buttons)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Silme talimatlarını ekle
        favorites_text += "\nBir favoriyi silmek için şu komutu kullanın:\n"
        favorites_text += "/delete_favorite <favori_id>\n"
        favorites_text += "Örnek: /delete_favorite 1"
        
        # Mesajı parçalara bölerek gönder
        await split_and_send_message(update, favorites_text, reply_markup)
    except Exception as e:
        await error_handler.handle_database_error(update, e)

async def delete_favorite_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Belirli bir favoriyi sil"""
    try:
        user_id = update.message.from_user.id
        
        if not context.args:
            await update.message.reply_text(
                "❌ Lütfen silmek istediğiniz favorinin ID'sini belirtin.\n"
                "Örnek: /delete_favorite 1"
            )
            return
        
        try:
            favorite_id = int(context.args[0])
            if db.delete_favorite(favorite_id, user_id):
                await update.message.reply_text(f"✅ {favorite_id} ID'li favori başarıyla silindi.")
            else:
                await update.message.reply_text("❌ Belirtilen ID'ye sahip bir favori bulunamadı.")
        except ValueError:
            await update.message.reply_text("❌ Geçersiz ID formatı. Lütfen sayısal bir ID girin.")
    except Exception as e:
        await error_handler.handle_database_error(update, e)

async def tips_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fotoğraf çekim ipuçlarını göster"""
    await update.message.reply_text(PHOTO_TIPS)

async def faq_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sık sorulan soruları göster"""
    await update.message.reply_text(FAQ)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot başlatıldığında çalışacak komut"""
    user_id = update.message.from_user.id
    db.set_user_state(user_id, True)
    
    commands = [
        BotCommand("start", "Stil asistanını başlat 👋"),
        BotCommand("help", "Yardım menüsünü göster ℹ️"),
        BotCommand("tips", "Fotoğraf çekim ipuçları 📸"),
        BotCommand("faq", "Sık sorulan sorular ❓"),
        BotCommand("favorites", "Favori kombinleriniz 🌟"),
        BotCommand("save", "Son analizi kaydedin ⭐"),
        BotCommand("finish", "Görüşmeyi sonlandır 👋")
    ]
    await context.bot.set_my_commands(commands)
    
    # Karşılama mesajı
    welcome_message = (
        f"Merhaba! Ben kişisel stil asistanınızım. 👋\n\n"
        f"Size nasıl yardımcı olabilirim?\n\n"
        f"📸 Fotoğraf çekim ipuçları için: /tips\n"
        f"❓ Sık sorulan sorular için: /faq\n"
        f"ℹ️ Yardım için: /help\n\n"
        f"Hadi başlayalım! Lütfen size en uygun profili seçin:"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("👔 İş Gardırobu", callback_data='professional'),
            InlineKeyboardButton("💰 Ekonomik Stil", callback_data='student')
        ],
        [InlineKeyboardButton("🎯 Trend Analisti", callback_data='fashion')],
        [InlineKeyboardButton("🎉 Özel Durum", callback_data='special_event')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yardım komutunu işle"""
    help_text = (
        "🤖 Stil Asistanı - Yardım Menüsü\n\n"
        "Kullanabileceğiniz komutlar:\n"
        "/start - Stil asistanını başlat\n"
        "/help - Bu yardım menüsünü göster\n"
        "/finish - Görüşmeyi sonlandır\n"
        "/favorites - Favori kombinlerinizi görüntüleyin\n"
        "/save - Son analizi favorilere kaydedin\n\n"
        "📸 Nasıl kullanılır:\n"
        "1. /start komutu ile botu başlatın\n"
        "2. Bir mod seçin (İş, Ekonomik, Trend veya Özel Durum)\n"
        "3. Özel Durum seçtiyseniz, etkinliğinizi yazın (düğün, mezuniyet vb.)\n"
        "4. Analiz edilecek kıyafet fotoğrafını gönderin\n"
        "5. Size özel kombin önerilerini alın\n"
        "6. İsterseniz modu değiştirip yeni öneriler alın\n"
        "7. /finish komutu ile görüşmeyi sonlandırın"
    )
    await update.message.reply_text(help_text)

async def finish_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bitiş komutunu işle"""
    user_id = update.message.from_user.id
    db.set_user_state(user_id, False)
    
    await update.message.reply_text(
        "Görüşme sonlandırıldı. 👋\n"
        "Tekrar görüşmek isterseniz /start komutunu kullanabilirsiniz.\n"
        "İyi günler dilerim! ✨"
    )

async def show_mode_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mod seçim menüsünü göster"""
    keyboard = [
        [
            InlineKeyboardButton("👔 İş Gardırobu", callback_data='professional'),
            InlineKeyboardButton("💰 Ekonomik Stil", callback_data='student')
        ],
        [InlineKeyboardButton("🎯 Trend Analisti", callback_data='fashion')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.message.reply_text(
        'Lütfen yeni bir mod seçin:\n\n'
        '👔 İş Gardırobu: Profesyonel görünüm ve ofis kombinleri\n'
        '💰 Ekonomik Stil: Uygun fiyatlı ve şık kombinler\n'
        '🎯 Trend Analisti: En son moda trendleri ve stil önerileri',
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buton tıklamalarını işle"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'delete_all_favorites':
        deleted_count = db.delete_all_favorites(query.from_user.id)
        if deleted_count > 0:
            await query.message.reply_text(f"✅ Tüm favorileriniz silindi. ({deleted_count} favori)")
        else:
            await query.message.reply_text("❌ Silinecek favori bulunamadı.")
        return
    
    if query.data == 'prev_favorites':
        context.user_data['favorites_page'] = max(1, context.user_data.get('favorites_page', 1) - 1)
        await show_favorites(update, context)
        return
        
    if query.data == 'next_favorites':
        context.user_data['favorites_page'] = context.user_data.get('favorites_page', 1) + 1
        await show_favorites(update, context)
        return
    
    if query.data == 'show_tips':
        await query.message.reply_text(PHOTO_TIPS)
        return
    
    if query.data == 'show_modes':
        await show_mode_selection(update, context)
        return
        
    if query.data == 'change_mode':
        await show_mode_selection(update, context)
        return
        
    if query.data == 'save_favorite':
        user_id = query.from_user.id
        if 'last_analysis' in context.user_data:
            mode = db.get_user_preference(user_id) or 'genel'
            db.add_favorite(user_id, context.user_data['last_analysis'], mode)
            await query.message.reply_text("✨ Bu kombin favorilerinize eklendi!")
        else:
            await query.message.reply_text("❌ Henüz kaydedilecek bir analiz bulunamadı.")
        return
        
    if query.data == 'special_event':
        db.set_user_preference(query.from_user.id, query.data)
        await query.edit_message_text(
            "🎉 Özel Durum modunu seçtiniz.\n\n"
            "Lütfen katılacağınız etkinliği yazın (örneğin: düğün, mezuniyet, iş görüşmesi, nişan vb.)"
        )
        return WAITING_FOR_EVENT
    
    # Diğer modlar için kullanıcı tercihini kaydet
    db.set_user_preference(query.from_user.id, query.data)
    
    messages = {
        'professional': '👔 İş Gardırobu Asistanı modunu seçtiniz.\n\n'
                       'Size profesyonel ve şık iş kombinleri önerebilirim.\n'
                       'Lütfen analiz etmemi istediğiniz kıyafet fotoğrafını gönderin.',
        'student': '💰 Ekonomik Stil Rehberi modunu seçtiniz.\n\n'
                  'Size uygun fiyatlı ve şık kombinler önerebilirim.\n'
                  'Lütfen analiz etmemi istediğiniz kıyafet fotoğrafını gönderin.',
        'fashion': '🎯 Trend Analisti modunu seçtiniz.\n\n'
                  'Size en son trendlere uygun kombinler önerebilirim.\n'
                  'Lütfen analiz etmemi istediğiniz kıyafet fotoğrafını gönderin.'
    }
    
    await query.edit_message_text(text=messages[query.data])

async def handle_event_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Özel durum metnini işle"""
    user_id = update.message.from_user.id
    event_text = update.message.text
    
    # Etkinliği kaydet
    db.set_user_event(user_id, event_text)
    
    await update.message.reply_text(
        f"🎉 '{event_text}' etkinliği için stil önerileri sunacağım.\n"
        "Şimdi lütfen analiz etmemi istediğiniz kıyafet fotoğrafını gönderin."
    )
    
    return ConversationHandler.END

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fotoğraf alındığında çalışacak fonksiyon"""
    try:
        user_id = update.message.from_user.id
        
        # Kullanıcı durumunu kontrol et
        if not db.get_user_state(user_id):
            await update.message.reply_text(
                "Üzgünüm, önce /start komutu ile botu başlatmanız ve bir mod seçmeniz gerekiyor. 🙏\n"
                "Yardım için /help komutunu kullanabilirsiniz."
            )
            return
            
        # Kullanıcının mod seçimini kontrol et
        user_mode = db.get_user_preference(user_id)
        if not user_mode:
            keyboard = [
                [InlineKeyboardButton("👉 Hemen Mod Seç", callback_data='show_modes')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Henüz bir mod seçmediniz. Analiz yapabilmem için önce bir mod seçmelisiniz.\n"
                "Mod seçimi için aşağıdaki butonu kullanabilir veya /start komutunu kullanabilirsiniz.",
                reply_markup=reply_markup
            )
            return

        # Fotoğraf boyut kontrolü
        photo = await update.message.photo[-1].get_file()
        if photo.file_size > 5000000:  # 5MB
            await update.message.reply_text(
                "⚠️ Fotoğraf boyutu çok büyük. Lütfen daha küçük boyutlu bir fotoğraf gönderin.\n"
                "İpuçları için /tips komutunu kullanabilirsiniz."
            )
            return

        await update.message.reply_text("🔍 Fotoğrafınızı analiz ediyorum...\n⏳ Bu işlem birkaç saniye sürebilir...")
        
        # Fotoğrafı al
        photo_bytes = await photo.download_as_bytearray()
        
        # Fotoğrafı PIL Image'a dönüştür
        image = Image.open(io.BytesIO(photo_bytes))
        
        # Kullanıcıya işlemin başladığını bildir
        await update.message.reply_text("🔍 Fotoğrafınızı analiz ediyorum...")
        
        # Moda göre özelleştirilmiş prompt
        prompts = {
            'professional': (
                "Bu fotoğraftaki kıyafeti profesyonel iş ortamı için analiz et ve uyumlu bir kombin öner. "
                "Lütfen şu formatta yanıt ver:\n"
                "1. Fotoğraftaki kıyafet: [detaylı açıklama]\n"
                "2. Önerilen iş kombini: [profesyonel ortama uygun kombin önerisi]\n"
                "3. Stil ipuçları: [iş ortamına uygun öneriler]\n"
                "Yanıtını Türkçe olarak ver."
            ),
            'student': (
                "Bu fotoğraftaki kıyafeti ekonomik ve şık bir tarz için analiz et ve uygun fiyatlı kombin öner. "
                "Lütfen şu formatta yanıt ver:\n"
                "1. Fotoğraftaki kıyafet: [detaylı açıklama]\n"
                "2. Önerilen ekonomik kombin: [uygun fiyatlı alternatiflerle kombin önerisi]\n"
                "3. Bütçe ipuçları: [ekonomik alışveriş önerileri]\n"
                "Yanıtını Türkçe olarak ver."
            ),
            'fashion': (
                "Bu fotoğraftaki kıyafeti en son trendlere göre analiz et ve modern bir kombin öner. "
                "Lütfen şu formatta yanıt ver:\n"
                "1. Fotoğraftaki kıyafet: [detaylı açıklama]\n"
                "2. Trend kombin önerisi: [güncel moda trendlerine uygun kombin]\n"
                "3. Sezonun trendleri: [mevcut sezon trendleri ile ilgili ipuçları]\n"
                "Yanıtını Türkçe olarak ver."
            ),
            'special_event': (
                f"Bu fotoğraftaki kıyafeti {db.get_user_event(user_id)} için analiz et ve uyumlu bir kombin öner. "
                "Lütfen şu formatta yanıt ver:\n"
                "1. Fotoğraftaki kıyafet: [detaylı açıklama]\n"
                "2. Etkinlik için önerilen kombin: [etkinliğe uygun kombin önerisi]\n"
                "3. Etkinlik stil ipuçları: [özel gün için öneriler]\n"
                "4. Aksesuar önerileri: [etkinliğe uygun aksesuarlar]\n"
                "Yanıtını Türkçe olarak ver."
            )
        }
        
        # Gemini API ile fotoğrafı analiz et
        response = model.generate_content([prompts[user_mode], image])
        
        # Gemini'den gelen yanıtı kaydet ve gönder
        context.user_data['last_analysis'] = response.text  # Son analizi sakla
        await update.message.reply_text(response.text)
        
        # Favori ve mod değiştirme seçeneklerini sun
        keyboard = [
            [InlineKeyboardButton("🔄 Modu Değiştir", callback_data='change_mode')],
            [InlineKeyboardButton("⭐ Favorilere Ekle", callback_data='save_favorite')],
            [InlineKeyboardButton("📸 Fotoğraf İpuçları", callback_data='show_tips')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "İşte size özel önerilerim! Başka ne yapmak istersiniz?",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        await error_handler.handle_error(update, context)

def main():
    """Bot'u başlat"""
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Hata yönetimi
    application.add_error_handler(error_handler.handle_error)
    
    # Özel durum konuşma işleyicisi
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern='^special_event$')],
        states={
            WAITING_FOR_EVENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_event_text)],
        },
        fallbacks=[],
    )
    
    # Komut işleyicileri
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("tips", tips_command))
    application.add_handler(CommandHandler("faq", faq_command))
    application.add_handler(CommandHandler("favorites", show_favorites))
    application.add_handler(CommandHandler("save", save_favorite))
    application.add_handler(CommandHandler("finish", finish_command))
    application.add_handler(CommandHandler("delete_favorite", delete_favorite_command))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Bot'u başlat
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
