# api/index.py

import os
import logging
import telegram
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from telegram import Update
from fastapi import FastAPI, Request
from firebase_utils import initialize_firebase
from handlers_button import button_handler, cancel_command
from handlers_start import start
from handlers_newclass import newclass_conv_handler
from handlers_newrequest import newrequest_conv_handler
from handlers_cancelclass import cancelclass_conv_handler
from handlers_schedule import schedule_conv_handler
from dotenv import load_dotenv
from telegram.ext import ContextTypes

# Load environment variables
load_dotenv()

# Access environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set in the environment variables.")

# Initialize Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Initialize Firebase
db = initialize_firebase()

# Initialize the Telegram Bot Application
application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

# Store db in bot_data for access in handlers
application.bot_data['db'] = db

# Register Handlers
application.add_handler(CommandHandler('start', start))
application.add_handler(CommandHandler('cancel', cancel_command))
application.add_handler(newclass_conv_handler())
application.add_handler(newrequest_conv_handler())
application.add_handler(cancelclass_conv_handler())
application.add_handler(schedule_conv_handler())
application.add_handler(CallbackQueryHandler(button_handler, pattern='^(CANCEL|SKIP)$'))

# Error Handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="An unexpected error occurred. Please try again later."
        )

application.add_error_handler(error_handler)

# Create FastAPI app
app = FastAPI()

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = telegram.Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"status": "OK"}

# Health check endpoint (optional)
@app.get("/")
async def root():
    return {"status": "OK"}
