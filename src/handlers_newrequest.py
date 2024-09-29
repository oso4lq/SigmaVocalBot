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
    if user_message.lower() != 'skip':
        context.user_data['message'] = user_message
    else:
        context.user_data['message'] = ''
    # Save the request to Firestore
    user = update.message.from_user
    db = context.bot_data['db']
    try:
        request_data = {
            'name': context.user_data['name'],
            'telegram': user.username or '',  # Handle if username is None
            'email': '',  # If available
            'phone': '',  # If available
            'message': context.user_data['message'],
            'date': datetime.utcnow().isoformat()
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

def newrequest_conv_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(newrequest_start, pattern='^NEWREQUEST$')],
        states={
            ENTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name)],
            ENTER_REQUEST_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_request_message),
                CallbackQueryHandler(skip_message, pattern='^SKIP$')  # Ensure skip_message is imported if needed
            ]
        },
        fallbacks=[CallbackQueryHandler(button_handler, pattern='^CANCEL$')],
    )


# sample from NEWCLASS
async def skip_message(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    context.user_data['message'] = ''  # Set message as empty
    await query.edit_message_text(text="Proceeding without an additional message.")
    
    # Proceed to save the class
    user = query.from_user
    db = context.bot_data['db']

    try:
        # Get user data from Firestore
        user_data = get_user_by_telegram_username(db, user.username)
        if not user_data:
            await query.message.reply_text("User data not found. Please ensure your Telegram username is linked to your account.")
            return ConversationHandler.END

        # Check membership points
        membership_points = user_data.get('membership', 0)
        if membership_points > 0:
            is_membership_used = True
            membership_points -= 1  # Decrement membership points
        else:
            is_membership_used = False

        # Prepare class data
        class_data = {
            'id': '',  # Will be set in add_new_class
            'status': 'подтверждено' if is_membership_used else 'в ожидании',
            'startdate': convert_to_utc(context.user_data['selected_date'], context.user_data['selected_time']),
            'enddate': convert_to_utc(
                context.user_data['selected_date'], 
                context.user_data['selected_time'],
                add_hours=1
            ),
            'message': context.user_data['message'],
            'isMembershipUsed': is_membership_used,
            'userId': user_data['id'],  # Use userData.id from Firestore
        }

        # Start a batch
        batch = db.batch()

        # Create a new document reference for the class
        class_ref = db.collection('classes').document()
        class_data['id'] = class_ref.id

        # Add the class to the batch
        batch.set(class_ref, class_data)

        # Update user's classes list
        updated_classes = user_data.get('classes', [])
        updated_classes.append(class_ref.id)
        user_update_data = {
            'classes': updated_classes
        }
        if is_membership_used:
            user_update_data['membership'] = membership_points

        # Update user data in the batch
        user_ref = db.collection('users').document(user_data['id'])
        batch.update(user_ref, user_update_data)

        # Commit the batch
        batch.commit()

        await query.message.reply_text("Your class was saved. Please wait for the confirmation.")

    except Exception as e:
        logging.error(f"Error in skip_message handler: {e}")
        await query.message.reply_text("There was an error saving your class. Please try again.")

    return ConversationHandler.END
