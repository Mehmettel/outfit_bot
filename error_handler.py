import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import (
    TelegramError,
    Forbidden,
    NetworkError,
    BadRequest,
    TimedOut
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ErrorHandler:
    def __init__(self):
        self.error_messages = {
            'database': "❌ A database error occurred. Please try again later.",
            'api': "❌ An error occurred while processing your request. Please try again.",
            'network': "❌ A network error occurred. Please check your connection and try again.",
            'photo': "❌ An error occurred while processing your photo. Please try again.",
            'timeout': "❌ The request timed out. Please try again.",
            'permission': "❌ I don't have permission to perform this action.",
            'general': "❌ An error occurred. Please try again later."
        }
    
    async def send_error_message(self, update: Update, error_type: str = 'general'):
        """Send error message based on update type"""
        try:
            message = self.error_messages.get(error_type, self.error_messages['general'])
            
            if update.callback_query:
                await update.callback_query.message.reply_text(message)
            elif update.message:
                await update.message.reply_text(message)
            elif update.edited_message:
                await update.edited_message.reply_text(message)
            else:
                logger.error(f"Could not send error message: Unknown update type")
                
        except Exception as e:
            logger.error(f"Error sending error message: {str(e)}")
    
    async def handle_error(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """General error handler"""
        try:
            error = context.error
            
            if isinstance(error, (NetworkError, TimedOut)):
                await self.handle_network_error(update, error)
            elif isinstance(error, BadRequest):
                await self.handle_bad_request(update, error)
            elif isinstance(error, Forbidden):
                await self.handle_forbidden_error(update, error)
            else:
                logger.error(f"Update {update} caused error: {str(error)}")
                await self.send_error_message(update)
                
        except Exception as e:
            logger.error(f"Error in error handler: {str(e)}")
    
    async def handle_database_error(self, update: Update, error: Exception):
        """Database error handler"""
        logger.error(f"Database error: {str(error)}")
        await self.send_error_message(update, 'database')
    
    async def handle_api_error(self, update: Update, error: Exception):
        """API error handler"""
        logger.error(f"API error: {str(error)}")
        await self.send_error_message(update, 'api')
    
    async def handle_network_error(self, update: Update, error: Exception):
        """Network error handler"""
        logger.error(f"Network error: {str(error)}")
        await self.send_error_message(update, 'network')
    
    async def handle_photo_error(self, update: Update, error: Exception):
        """Photo processing error handler"""
        logger.error(f"Photo processing error: {str(error)}")
        await self.send_error_message(update, 'photo')
    
    async def handle_forbidden_error(self, update: Update, error: Exception):
        """Permission error handler"""
        logger.error(f"Permission error: {str(error)}")
        await self.send_error_message(update, 'permission')
    
    async def handle_bad_request(self, update: Update, error: Exception):
        """Bad request error handler"""
        logger.error(f"Bad request error: {str(error)}")
        await self.send_error_message(update, 'general') 