# This is the entry point of application. 

# It initializes environment variables, Firebase, the Telegram bot, 
# registers handlers from handlers.py, and starts the bot.

import os
import logging
from dotenv import load_dotenv
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler
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

# Initialize the Telegram Bot
updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# Register Handlers

# START Command Handler
dispatcher.add_handler(CommandHandler('start', lambda update, context: start(update, context, db)))

# Button Callback Handler
dispatcher.add_handler(CallbackQueryHandler(lambda update, context: button_handler(update, context, db)))

# NEWCLASS Conversation Handler
dispatcher.add_handler(newclass_conv_handler(db))

# NEWREQUEST Conversation Handler
dispatcher.add_handler(newrequest_conv_handler(db))

# CANCELCLASS Conversation Handler
dispatcher.add_handler(cancelclass_conv_handler(db))

# CANCEL Command Handler (optional if you have a separate /cancel command)
# Uncomment below if you want to handle /cancel command globally
# from telegram.ext import CommandHandler
# dispatcher.add_handler(CommandHandler('cancel', cancel))

# Error Handler
def error_handler(update, context):
    """Log the error and send a telegram message to notify the developer."""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    # Notify user
    if update and update.effective_chat:
        context.bot.send_message(chat_id=update.effective_chat.id, text="An unexpected error occurred. Please try again later.")

dispatcher.add_error_handler(error_handler)

# Start the Bot
if __name__ == '__main__':
    logger.info("Starting the bot...")
    updater.start_polling()
    updater.idle()
