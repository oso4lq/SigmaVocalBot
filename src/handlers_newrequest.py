# Handles the NEWREQUEST conversation for users to leave a request for their first class.

import logging
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackContext, 
    ConversationHandler, 
    CallbackQueryHandler, 
    MessageHandler, 
    filters
)
from firebase_utils import add_new_request
from handlers_button import button_handler
from firebase_utils import get_user_by_telegram_username
from utils import convert_to_utc

# Define Conversation States for NEWREQUEST
ENTER_NAME, ENTER_REQUEST_MESSAGE = range(2)

async def newrequest_start(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.edit_message_text(text="Please enter your name:")
    return ENTER_NAME

async def enter_name(update: Update, context: CallbackContext):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("You must enter your name before submitting the request.")
        return ENTER_NAME
    context.user_data['name'] = name
    await update.message.reply_text(
        "Please enter any message or press 'SKIP' to continue.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("SKIP", callback_data='SKIP')],
            [InlineKeyboardButton("Cancel", callback_data='CANCEL')]
        ])
    )
    return ENTER_REQUEST_MESSAGE

async def enter_request_message(update: Update, context: CallbackContext):
    user_message = update.message.text
    context.user_data['message'] = user_message  # Save the message
    
    # Save the request to Firestore
    user = update.message.from_user
    db = context.bot_data['db']
    try:
        request_data = {
            'name': context.user_data['name'],
            'telegram': user.username or '',  # Handle if username is None
            'email': '',  # Empty as per your Angular app
            'phone': '',  # Empty as per your Angular app
            'message': context.user_data['message'],
            'date': datetime.utcnow().isoformat(),
            'id': ''  # Placeholder; will be set in add_new_request
        }
        success = add_new_request(db, request_data)
        if success:
            await update.message.reply_text("Your request was saved. Please wait until the tutor contacts you.")
        else:
            await update.message.reply_text("There was an error saving your request. Please try again.")
    except Exception as e:
        logging.error(f"Error in enter_request_message handler: {e}")
        await update.message.reply_text("There was an error saving your request. Please try again.")
    return ConversationHandler.END

async def skip_message(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    context.user_data['message'] = ''  # Set message as empty
    await query.edit_message_text(text="Proceeding without an additional message.")
    
    # Save the request to Firestore
    user = query.from_user
    db = context.bot_data['db']
    try:
        request_data = {
            'name': context.user_data['name'],
            'telegram': user.username or '',  # Handle if username is None
            'email': '',  # Empty as per your Angular app
            'phone': '',  # Empty as per your Angular app
            'message': context.user_data['message'],
            'date': datetime.utcnow().isoformat(),
            'id': ''  # Placeholder; will be set in add_new_request
        }
        success = add_new_request(db, request_data)
        if success:
            await query.message.reply_text("Your request was saved. Please wait until the tutor contacts you.")
        else:
            await query.message.reply_text("There was an error saving your request. Please try again.")
    except Exception as e:
        logging.error(f"Error in skip_message handler: {e}")
        await query.message.reply_text("There was an error saving your request. Please try again.")
    return ConversationHandler.END

def newrequest_conv_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(newrequest_start, pattern='^NEWREQUEST$')],
        states={
            ENTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name)],
            ENTER_REQUEST_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_request_message),
                CallbackQueryHandler(skip_message, pattern='^SKIP$')  # Include skip_message handler
            ]
        },
        fallbacks=[CallbackQueryHandler(button_handler, pattern='^CANCEL$')],
    )