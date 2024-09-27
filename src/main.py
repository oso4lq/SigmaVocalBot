# This is the entry point of application. 

# It initializes environment variables, Firebase, the Telegram bot, 
# registers handlers from handlers.py, and starts the bot.

import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    CallbackQueryHandler,
    ContextTypes
)
from handlers import (
    start, 
    button_handler,
    newclass_conv_handler, 
    newrequest_conv_handler,
    cancelclass_conv_handler
)
from firebase_utils import initialize_firebase

# Load environment variables from .env file
load_dotenv()

# Access the environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set in the environment variables.")

if not GOOGLE_APPLICATION_CREDENTIALS:
    raise ValueError("GOOGLE_APPLICATION_CREDENTIALS is not set in the environment variables.")

# Initialize Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Firebase
db = initialize_firebase(GOOGLE_APPLICATION_CREDENTIALS)

# Initialize the Telegram Bot Application
application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

# Store db in bot_data for access in handlers
application.bot_data['db'] = db

# Register Handlers

# START Command Handler
application.add_handler(CommandHandler('start', start))

# NEWCLASS Conversation Handler
application.add_handler(newclass_conv_handler())

# NEWREQUEST Conversation Handler
application.add_handler(newrequest_conv_handler())

# CANCELCLASS Conversation Handler
application.add_handler(cancelclass_conv_handler())

# Button Callback Handler (Handles generic buttons not managed by ConversationHandlers)
application.add_handler(CallbackQueryHandler(button_handler, pattern='^(?!NEWCLASS$|CANCELCLASS$|NEWREQUEST$).*'))

# Error Handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log the error and send a telegram message to notify the developer."""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    # Notify user
    if isinstance(update, Update) and update.effective_chat:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="An unexpected error occurred. Please try again later.")

application.add_error_handler(error_handler)

# Start the Bot
if __name__ == '__main__':
    logger.info("Starting the bot...")
    application.run_polling()
