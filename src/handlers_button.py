# Handles generic button callbacks not managed by ConversationHandler instances.

from telegram.ext import CallbackContext
from telegram import Update
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
from telegram.ext import ConversationHandler

async def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'CANCEL':
        # Optionally, you can send a cancellation message
        await query.edit_message_text(text="Operation cancelled.")
        return ConversationHandler.END
    else:
        # Handle other generic buttons if any
        await query.edit_message_text(text="Unknown action. Please try again.")
        return ConversationHandler.END
