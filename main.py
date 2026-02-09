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
from quick_actions import QuickActions
import sqlite3

# Initialize database and helper classes
db = Database()
error_handler = ErrorHandler()
quick_actions = QuickActions(db)

# Logging settings
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

# Photo shooting tips
PHOTO_TIPS = """
📸 Photo Shooting Tips:

1. Good Lighting:
   • Prefer natural daylight
   • Avoid creating shadows

2. Right Angle:
   • Choose an angle that shows the entire outfit
   • Take close-up shots

3. Clear Image:
   • Keep the camera steady
   • Focus correctly

4. Background:
   • Choose a simple background
   • Avoid clutter
"""

# Frequently asked questions
FAQ = """
❓ Frequently Asked Questions:

1. How does the bot work?
   • Analyzes your photo with AI
   • Provides suggestions based on your selected mode

2. What modes can I use?
   • Business Wardrobe Assistant
   • Budget Style Guide
   • Trend Analyst
   • Special Event Consultant

3. How can I use favorites?
   • Use /save command to save an outfit
   • Use /favorites to view your saved outfits

4. How can I change the mode?
   • Use the "Change Mode" button
   • or use /start to begin again
"""

# Load API keys from .env file
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Gemini API configuration
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Dictionaries to store user data
user_preferences = {}  # Store user preferences
user_states = {}      # Store user states
user_events = {}      # Store user events
user_favorites = {}   # Store user favorites

async def check_user_state(update: Update, user_id: int) -> bool:
    """Check user state"""
    if not db.get_user_state(user_id):
        await update.message.reply_text(
            "Sorry, you need to start the bot first with /start command. 🙏\n"
            "For help, use the /help command."
        )
        return False
    return True

async def save_favorite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save favorite outfit"""
    try:
        user_id = update.message.from_user.id
        if not await check_user_state(update, user_id):
            return
        
        if 'last_analysis' in context.user_data:
            mode = db.get_user_preference(user_id) or 'general'
            if db.add_favorite(user_id, context.user_data['last_analysis'], mode):
                await update.message.reply_text("✨ This outfit has been added to your favorites!")
            else:
                await update.message.reply_text("❌ An error occurred while adding to favorites.")
        else:
            await update.message.reply_text("❌ No analysis found to save.")
    except Exception as e:
        await error_handler.handle_database_error(update, e)

async def show_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show favorite outfits"""
    try:
        # Get user_id based on update type
        if update.message:
            user_id = update.message.from_user.id
            if not await check_user_state(update, user_id):
                return
        elif update.callback_query:
            user_id = update.callback_query.from_user.id
        else:
            logger.error("Invalid update type in show_favorites")
            await error_handler.send_error_message(update, "general")
            return

        try:
            # Get favorites from database
            favorites = db.get_user_favorites(user_id)
            
            if not favorites:
                message = "You don't have any saved favorites yet."
                if update.callback_query:
                    await update.callback_query.message.reply_text(message)
                else:
                    await update.message.reply_text(message)
                return
            
            # Calculate pagination
            FAVORITES_PER_PAGE = 1
            total_pages = (len(favorites) + FAVORITES_PER_PAGE - 1) // FAVORITES_PER_PAGE
            current_page = context.user_data.get('favorites_page', 1)
            
            # Ensure current page is valid
            if current_page > total_pages:
                current_page = 1
                context.user_data['favorites_page'] = 1
            
            # Calculate page indices
            start_idx = (current_page - 1) * FAVORITES_PER_PAGE
            end_idx = min(start_idx + FAVORITES_PER_PAGE, len(favorites))
            
            # Create favorites text
            favorites_text = f"🌟 Your Favorite Outfits (Page {current_page}/{total_pages}):\n\n"
            
            for i, (fav_id, analysis, mode, created_at) in enumerate(favorites[start_idx:end_idx], start_idx + 1):
                favorites_text += f"Favorite #{i} (ID: {fav_id})\n"
                favorites_text += f"Date: {created_at}\n"
                favorites_text += f"Mode: {mode.title()}\n"
                favorites_text += f"Analysis:\n{analysis}\n"
                favorites_text += "─" * 30 + "\n"
            
            # Add deletion instructions
            favorites_text += "\nTo delete a favorite:\n"
            favorites_text += "/delete_favorite <favorite_id>\n"
            favorites_text += "Example: /delete_favorite 1"
            
            # Create keyboard
            keyboard = []
            
            # Add delete all button
            delete_buttons = [
                InlineKeyboardButton("🗑️ Delete All", callback_data='delete_all_favorites')
            ]
            keyboard.append(delete_buttons)
            
            # Add navigation buttons if needed
            if total_pages > 1:
                nav_buttons = []
                if current_page > 1:
                    nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data='prev_favorites'))
                if current_page < total_pages:
                    nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data='next_favorites'))
                keyboard.append(nav_buttons)
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Handle long messages
            if len(favorites_text) > 4096:
                chunks = [favorites_text[i:i+4096] for i in range(0, len(favorites_text), 4096)]
                for i, chunk in enumerate(chunks):
                    if i == len(chunks) - 1:  # Last chunk
                        if update.callback_query:
                            await update.callback_query.message.edit_text(chunk, reply_markup=reply_markup)
                        else:
                            await update.message.reply_text(chunk, reply_markup=reply_markup)
                    else:  # Other chunks
                        if update.callback_query:
                            await update.callback_query.message.reply_text(chunk)
                        else:
                            await update.message.reply_text(chunk)
            else:
                if update.callback_query:
                    await update.callback_query.message.edit_text(favorites_text, reply_markup=reply_markup)
                else:
                    await update.message.reply_text(favorites_text, reply_markup=reply_markup)
                    
        except Exception as db_error:
            logger.error(f"Database error in show_favorites: {str(db_error)}")
            await error_handler.handle_database_error(update, db_error)
            
    except Exception as e:
        logger.error(f"Error in show_favorites: {str(e)}")
        await error_handler.handle_error(update, context)

async def delete_favorite_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a specific favorite"""
    try:
        user_id = update.message.from_user.id
        
        if not context.args:
            await update.message.reply_text(
                "❌ Please specify the ID of the favorite you want to delete.\n"
                "Example: /delete_favorite 1"
            )
            return
        
        try:
            favorite_id = int(context.args[0])
            if db.delete_favorite(favorite_id, user_id):
                await update.message.reply_text(f"✅ Favorite with ID {favorite_id} has been successfully deleted.")
            else:
                await update.message.reply_text("❌ No favorite found with the specified ID.")
        except ValueError:
            await update.message.reply_text("❌ Invalid ID format. Please enter a numeric ID.")
    except Exception as e:
        await error_handler.handle_database_error(update, e)

async def tips_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show photo shooting tips"""
    await update.message.reply_text(PHOTO_TIPS)

async def faq_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show frequently asked questions"""
    await update.message.reply_text(FAQ)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user_id = update.message.from_user.id
    db.set_user_state(user_id, True)
    
    commands = [
        BotCommand("start", "Start the style assistant 👋"),
        BotCommand("help", "Show help menu ℹ️"),
        BotCommand("tips", "Photo shooting tips 📸"),
        BotCommand("faq", "Frequently asked questions ❓"),
        BotCommand("favorites", "Your favorite outfits 🌟"),
        BotCommand("save", "Save last analysis ⭐"),
        BotCommand("last", "Show last analysis 🔍"),
        BotCommand("finish", "End conversation 👋")
    ]
    await context.bot.set_my_commands(commands)
    
    welcome_message = (
        f"Hello! I'm your personal style assistant. 👋\n\n"
        f"How can I help you?\n\n"
        f"📸 For photo shooting tips: /tips\n"
        f"❓ For frequently asked questions: /faq\n"
        f"ℹ️ For help: /help\n\n"
        f"Let's begin! Please select the most suitable profile for you:"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("👔 Business Wardrobe", callback_data='professional'),
            InlineKeyboardButton("💰 Budget Style", callback_data='student')
        ],
        [InlineKeyboardButton("🎯 Trend Analyst", callback_data='fashion')],
        [InlineKeyboardButton("🎉 Special Event", callback_data='special_event')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command handler"""
    help_text = (
        "🤖 Style Assistant - Help Menu\n\n"
        "Available commands:\n"
        "/start - Start the style assistant\n"
        "/help - Show this help menu\n"
        "/finish - End conversation\n"
        "/favorites - View your favorite outfits\n"
        "/save - Save last analysis\n"
        "/last - Show last analysis\n\n"
        "📸 How to use:\n"
        "1. Start the bot with /start command\n"
        "2. Select a mode (Business, Budget, Trend, or Special Event)\n"
        "3. If you chose Special Event, specify your event (wedding, graduation, etc.)\n"
        "4. Send a photo of the outfit for analysis\n"
        "5. Get personalized outfit suggestions\n"
        "6. Optionally change mode for new suggestions\n"
        "7. Use /finish command to end the conversation"
    )
    await update.message.reply_text(help_text)

async def finish_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finish command handler"""
    try:
        if not update.message:
            logger.error("No message object in finish_command")
            return
            
        user_id = update.message.from_user.id
        
        try:
            # Check user state first
            current_state = db.get_user_state(user_id)
            if not current_state:
                await update.message.reply_text(
                    "No active session found.\n"
                    "Use /start command to begin a new session."
                )
                return

            # Try each database operation separately
            success = True
            
            if not db.set_user_state(user_id, False):
                success = False
                logger.error(f"Failed to update user state: {user_id}")
            
            if not db.set_user_preference(user_id, None):
                success = False
                logger.error(f"Failed to clear user preference: {user_id}")
            
            if not db.set_user_event(user_id, ""):
                success = False
                logger.error(f"Failed to clear user event: {user_id}")
            
            # Clear context data
            if context.user_data:
                context.user_data.clear()
            
            # Clear quick actions data
            quick_actions.clear_last_analysis(user_id)
            
            # Clear user data from local dictionaries
            for user_dict in [user_preferences, user_states, user_events, user_favorites]:
                if user_id in user_dict:
                    del user_dict[user_id]
            
            if success:
                await update.message.reply_text(
                    "Session ended. 👋\n"
                    "Use /start command to talk again.\n"
                    "Have a great day! ✨"
                )
            else:
                await update.message.reply_text(
                    "Session ended but some data couldn't be cleared.\n"
                    "Please use /start command to begin a new session."
                )
            
        except sqlite3.Error as db_error:
            logger.error(f"Database error - finish_command: {str(db_error)}")
            await error_handler.handle_database_error(update, db_error)
            return
            
    except Exception as e:
        logger.error(f"General error - finish_command: {str(e)}")
        await error_handler.handle_error(update, context)
        return

async def show_mode_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show mode selection menu"""
    keyboard = [
        [
            InlineKeyboardButton("👔 Business Wardrobe", callback_data='professional'),
            InlineKeyboardButton("💰 Budget Style", callback_data='student')
        ],
        [InlineKeyboardButton("🎯 Trend Analyst", callback_data='fashion')],
        [InlineKeyboardButton("🎉 Special Event", callback_data='special_event')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.message.reply_text(
        'Please select a new mode:\n\n'
        '👔 Business Wardrobe: Professional looks and office outfits\n'
        '💰 Budget Style: Affordable and stylish combinations\n'
        '🎯 Trend Analyst: Latest fashion trends and style tips\n'
        '🎉 Special Event: Suggestions for weddings, graduations, and other events',
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Button callback handler"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    try:
        if query.data == 'delete_all_favorites':
            deleted_count = db.delete_all_favorites(user_id)
            if deleted_count > 0:
                await query.message.reply_text(f"✅ All your favorites have been deleted. ({deleted_count} favorites)")
            else:
                await query.message.reply_text("❌ No favorites found to delete.")
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
            if 'last_analysis' in context.user_data:
                mode = db.get_user_preference(user_id) or 'general'
                db.add_favorite(user_id, context.user_data['last_analysis'], mode)
                await query.message.reply_text("✨ This outfit has been added to your favorites!")
            else:
                await query.message.reply_text("❌ No analysis found to save.")
            return
            
        if query.data == 'special_event':
            db.set_user_state(user_id, True)
            db.set_user_preference(user_id, query.data)
            await query.edit_message_text(
                "🎉 You've selected Special Event mode.\n\n"
                "Please specify your event (e.g., wedding, graduation, job interview, engagement, etc.)"
            )
            return WAITING_FOR_EVENT
        
        if query.data == 'quick_save':
            await quick_actions.quick_save_favorite(update, context)
            return
        
        if query.data == 'new_analysis':
            await query.message.reply_text(
                "🔄 Please send a photo for new analysis."
            )
            return
        
        db.set_user_state(user_id, True)
        db.set_user_preference(user_id, query.data)
        
        messages = {
            'professional': '👔 You\'ve selected Business Wardrobe Assistant mode.\n\n'
                           'I can suggest professional and elegant business outfits.\n'
                           'Please send a photo of the outfit you\'d like me to analyze.',
            'student': '💰 You\'ve selected Budget Style Guide mode.\n\n'
                      'I can suggest affordable and stylish combinations.\n'
                      'Please send a photo of the outfit you\'d like me to analyze.',
            'fashion': '🎯 You\'ve selected Trend Analyst mode.\n\n'
                      'I can suggest outfits based on the latest trends.\n'
                      'Please send a photo of the outfit you\'d like me to analyze.'
        }
        
        await query.edit_message_text(text=messages[query.data])
        
    except Exception as e:
        await error_handler.handle_error(update, context)

async def handle_event_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle special event text"""
    try:
        user_id = update.message.from_user.id
        
        if not await check_user_state(update, user_id):
            return ConversationHandler.END
        
        event_text = update.message.text.strip()
        
        if not event_text:
            await update.message.reply_text(
                "❌ Please enter a valid event.\n"
                "Example: wedding, graduation, job interview, engagement, etc."
            )
            return WAITING_FOR_EVENT
        
        db.set_user_event(user_id, event_text)
        
        await update.message.reply_text(
            f"🎉 I'll provide style suggestions for your '{event_text}' event.\n"
            "Now please send a photo of the outfit you'd like me to analyze."
        )
        
        return ConversationHandler.END
        
    except Exception as e:
        await error_handler.handle_error(update, context)
        return ConversationHandler.END

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Photo handler"""
    try:
        user_id = update.message.from_user.id
        
        if not db.get_user_state(user_id):
            await update.message.reply_text(
                "Sorry, you need to start the bot first with /start command and select a mode. 🙏\n"
                "For help, use the /help command."
            )
            return
            
        user_mode = db.get_user_preference(user_id)
        if not user_mode:
            keyboard = [
                [InlineKeyboardButton("👉 Select Mode", callback_data='show_modes')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "You haven't selected a mode yet. Please select a mode for analysis.\n"
                "You can use the button below or /start command to select a mode.",
                reply_markup=reply_markup
            )
            return

        photo = await update.message.photo[-1].get_file()
        if photo.file_size > 5000000:  # 5MB
            await update.message.reply_text(
                "⚠️ Photo size is too large. Please send a smaller photo.\n"
                "For tips, use the /tips command."
            )
            return

        processing_message = await update.message.reply_text(
            "🔍 Analyzing your photo...\n⏳ This may take a few seconds..."
        )
        
        try:
            photo_bytes = await photo.download_as_bytearray()
            image = Image.open(io.BytesIO(photo_bytes))
            
            max_size = (800, 800)
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            prompts = {
                'professional': (
                    "Analyze this outfit for a professional business environment and suggest a matching combination. "
                    "Please respond in the following format:\n"
                    "1. Outfit in photo: [detailed description]\n"
                    "2. Suggested business outfit: [professional environment-appropriate combination]\n"
                    "3. Style tips: [business environment suggestions]"
                ),
                'student': (
                    "Analyze this outfit for an affordable and stylish look and suggest a budget-friendly combination. "
                    "Please respond in the following format:\n"
                    "1. Outfit in photo: [detailed description]\n"
                    "2. Suggested budget outfit: [affordable alternatives combination]\n"
                    "3. Budget tips: [budget shopping suggestions]"
                ),
                'fashion': (
                    "Analyze this outfit according to the latest trends and suggest a modern combination. "
                    "Please respond in the following format:\n"
                    "1. Outfit in photo: [detailed description]\n"
                    "2. Trend outfit suggestion: [current fashion trends combination]\n"
                    "3. Season trends: [current season trend tips]"
                ),
                'special_event': (
                    f"Analyze this outfit for {db.get_user_event(user_id)} and suggest a matching combination. "
                    "Please respond in the following format:\n"
                    "1. Outfit in photo: [detailed description]\n"
                    "2. Suggested event outfit: [event-appropriate combination]\n"
                    "3. Event style tips: [special occasion suggestions]\n"
                    "4. Accessory suggestions: [event-appropriate accessories]"
                )
            }

            try:
                response = model.generate_content([prompts[user_mode], image])
                analysis_text = response.text
                
                context.user_data['last_analysis'] = analysis_text
                quick_actions.save_last_analysis(user_id, analysis_text)
                
                await processing_message.delete()
                
                await update.message.reply_text(analysis_text)
                
                keyboard = [
                    [InlineKeyboardButton("⭐ Quick Save", callback_data='quick_save')],
                    [InlineKeyboardButton("🔄 Change Mode", callback_data='change_mode')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "Here are my suggestions! What would you like to do?",
                    reply_markup=reply_markup
                )
                
            except Exception as api_error:
                await error_handler.handle_api_error(update, api_error)
                
        except Exception as photo_error:
            await error_handler.handle_photo_error(update, photo_error)
            
    except Exception as e:
        await error_handler.handle_error(update, context)

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation handler"""
    await update.message.reply_text(
        "Operation cancelled. Use /start command to return to the main menu."
    )
    return ConversationHandler.END

def main():
    """Start the bot"""
    try:
        # Create application
        application = (
            Application.builder()
            .token(TELEGRAM_TOKEN)
            .connect_timeout(30)
            .read_timeout(30)
            .write_timeout(30)
            .pool_timeout(30)
            .build()
        )
        
        # Error handling
        application.add_error_handler(error_handler.handle_error)
        
        # Special event conversation handler
        conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(button_callback, pattern='^special_event$')],
            states={
                WAITING_FOR_EVENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_event_text)],
            },
            fallbacks=[CommandHandler('cancel', cancel_conversation)],
            allow_reentry=True
        )
        
        # Add command handlers
        handlers = [
            CommandHandler("start", start),
            CommandHandler("help", help_command),
            CommandHandler("tips", tips_command),
            CommandHandler("faq", faq_command),
            CommandHandler("favorites", show_favorites),
            CommandHandler("save", save_favorite),
            CommandHandler("last", quick_actions.show_last_analysis),
            CommandHandler("finish", finish_command),
            CommandHandler("delete_favorite", delete_favorite_command),
            conv_handler,
            CallbackQueryHandler(button_callback),
            MessageHandler(filters.PHOTO, handle_photo)
        ]
        
        for handler in handlers:
            application.add_handler(handler)
        
        # Signal handlers for graceful shutdown
        def shutdown(signum=None, frame=None):
            """Graceful shutdown function"""
            nonlocal application
            logger.info("Bot is shutting down...")
            try:
                application.stop()
                application.shutdown()
                logger.info("Bot has been successfully shut down.")
            except Exception as e:
                logger.error(f"Error occurred while shutting down bot: {str(e)}")
            finally:
                import sys
                sys.exit(0)

        # Catch signals
        import signal
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, shutdown)
        
        # Start bot
        logger.info("Bot is starting...")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            close_loop=False
        )
        
    except Exception as e:
        logger.error(f"Error occurred while starting bot: {str(e)}")
        if 'application' in locals():
            shutdown()

if __name__ == '__main__':
    main()
