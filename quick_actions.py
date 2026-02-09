from typing import Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from database import Database

class QuickActions:
    def __init__(self, database: Database):
        self.db = database
        self.last_analyses = {}  # user_id: last_analysis
    
    def save_last_analysis(self, user_id: int, analysis: str):
        """Save last analysis to memory and database"""
        self.last_analyses[user_id] = analysis
        self.db.save_last_analysis(user_id, analysis)
    
    def get_last_analysis(self, user_id: int) -> Optional[str]:
        """Get last analysis from memory or database"""
        # First check memory (faster)
        if user_id in self.last_analyses:
            return self.last_analyses[user_id]
        # Fallback to database (persists across restarts)
        db_analysis = self.db.get_last_analysis(user_id)
        if db_analysis:
            self.last_analyses[user_id] = db_analysis
        return db_analysis
    
    def clear_last_analysis(self, user_id: int):
        """Clear last analysis from memory"""
        if user_id in self.last_analyses:
            del self.last_analyses[user_id]
    
    async def show_last_analysis(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show last analysis"""
        user_id = update.message.from_user.id
        last_analysis = self.get_last_analysis(user_id)
        
        if not last_analysis:
            await update.message.reply_text(
                "❌ No analysis found or last analysis not saved."
            )
            return
        
        # Quick action buttons
        keyboard = [
            [InlineKeyboardButton("⭐ Quick Save", callback_data='quick_save')],
            [InlineKeyboardButton("🔄 New Analysis", callback_data='new_analysis')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔍 Last Analysis:\n\n" + last_analysis,
            reply_markup=reply_markup
        )
    
    async def quick_save_favorite(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Quick save favorite"""
        user_id = update.callback_query.from_user.id
        last_analysis = self.get_last_analysis(user_id)
        
        if not last_analysis:
            await update.callback_query.message.reply_text(
                "❌ No analysis found to save."
            )
            return
        
        try:
            mode = self.db.get_user_preference(user_id) or 'general'
            self.db.add_favorite(user_id, last_analysis, mode)
            await update.callback_query.message.reply_text(
                "✨ Analysis successfully added to favorites!"
            )
        except Exception as e:
            await update.callback_query.message.reply_text(
                "❌ An error occurred while saving to favorites."
            ) 