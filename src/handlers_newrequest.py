# Handles the NEWREQUEST conversation for users to leave a request for their first class.

import logging
from datetime import datetime
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommandScopeChat,
    BotCommand,
    Update,
)
from telegram.ext import (
    CallbackQueryHandler,
    ConversationHandler,
    CallbackContext,
    MessageHandler,
    CommandHandler,
    filters,
)
from firebase_utils import add_new_request
from handlers_button import button_handler, cancel_command
from utils import reset_user_commands

# Define Conversation States for NEWREQUEST
ENTER_NAME, ENTER_REQUEST_MESSAGE = range(2)


 # Entry point. Asks the user to enter their name.
async def newrequest_start(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.edit_message_text(text="Please enter your name:")
    
    # Set commands relevant to NEWCLASS
    await context.bot.set_my_commands(
        [BotCommand('cancel', 'Cancel the operation')],
        scope=BotCommandScopeChat(update.effective_chat.id)
    )

    return ENTER_NAME


# Handles the name validation and saving. Asks the user to enter an additional message or skip.
async def enter_name(update: Update, context: CallbackContext):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("You must enter your name before submitting the request.")
        return ENTER_NAME
    context.user_data['name'] = name # Save the name
    await update.message.reply_text(
        "Please enter any message or press 'SKIP' to continue.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("SKIP", callback_data='SKIP')],
            [InlineKeyboardButton("Cancel", callback_data='CANCEL')]
        ])
    )
    return ENTER_REQUEST_MESSAGE


# Handles the case when the user skips entering an additional message. Saves the request and updates the database.
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

    # Reset commands based on user status
    await reset_user_commands(update, context)

    return ConversationHandler.END


# Handles the user's additional message input. Saves the request and updates the database.
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

    # Reset commands based on user status
    await reset_user_commands(update, context)

    return ConversationHandler.END


def newrequest_conv_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(newrequest_start, pattern='^NEWREQUEST$'),
            CommandHandler('newclass', newrequest_start),
        ],
        states={
            ENTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name)],
            ENTER_REQUEST_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_request_message),
                CallbackQueryHandler(skip_message, pattern='^SKIP$'),
            ]
        },
        fallbacks=[
            CallbackQueryHandler(button_handler, pattern='^CANCEL$'),
            CommandHandler('cancel', cancel_command),
        ],
    )