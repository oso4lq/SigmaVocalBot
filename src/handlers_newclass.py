# Handles the NEWCLASS conversation for booking new classes, including membership point usage.

import logging
from datetime import datetime, timedelta
from telegram import (
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    Update
)
from telegram.ext import (
    CallbackContext, 
    ConversationHandler, 
    CallbackQueryHandler, 
    MessageHandler, 
    filters
)
from firebase_utils import (
    get_user_by_telegram_username, 
    get_occupied_time_slots
    )
from utils import (
    convert_to_utc, 
    ST_PETERSBURG
)
from handlers_button import button_handler

# Define Conversation States for NEWCLASS
SELECT_DATE, SELECT_TIME, ENTER_MESSAGE = range(3)

async def newclass_start(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.edit_message_text(text="Please select a day.")

    # Generate available dates
    dates_buttons = []
    today = datetime.now(ST_PETERSBURG)
    for i in range(1, 8):
        day = today + timedelta(days=i)
        if day.weekday() < 5:  # Exclude weekends (0=Monday, ..., 6=Sunday)
            display_date_str = day.strftime('%d.%m.%Y')  # DD.MM.YYYY
            callback_date_str = day.strftime('%Y-%m-%d')  # YYYY-MM-DD
            dates_buttons.append(
                [InlineKeyboardButton(display_date_str, callback_data=f"DATE_{callback_date_str}")]
            )

    dates_buttons.append([InlineKeyboardButton("Cancel", callback_data='CANCEL')])
    reply_markup = InlineKeyboardMarkup(dates_buttons)
    await context.bot.send_message(chat_id=query.message.chat_id, text="Available dates:", reply_markup=reply_markup)
    return SELECT_DATE

async def select_date(update: Update, context: CallbackContext):
    query = update.callback_query
    selected_date = query.data.split('_')[1]
    context.user_data['selected_date'] = selected_date
    logging.info(f"Selected date: {selected_date}")
    await query.edit_message_text(text=f"Selected date: {selected_date}\nPlease select a time slot.")

    # Generate time slots
    times_buttons = []
    db = context.bot_data['db']
    occupied_slots = get_occupied_time_slots(db, selected_date)

    for hour in range(8, 20):
        time_slot = f"{hour:02d}:00"
        if time_slot not in occupied_slots:
            times_buttons.append(
                [InlineKeyboardButton(time_slot, callback_data=f"TIME_{time_slot}")]
            )

    times_buttons.append([InlineKeyboardButton("Cancel", callback_data='CANCEL')])
    reply_markup = InlineKeyboardMarkup(times_buttons)
    await context.bot.send_message(chat_id=query.message.chat_id, text="Available time slots:", reply_markup=reply_markup)
    return SELECT_TIME

async def select_time(update: Update, context: CallbackContext):
    query = update.callback_query
    selected_time = query.data.split('_')[1]
    context.user_data['selected_time'] = selected_time
    logging.info(f"Selected time: {selected_time}")
    # Present message input with SKIP button
    keyboard = [
        [InlineKeyboardButton("SKIP", callback_data='SKIP')],
        [InlineKeyboardButton("Cancel", callback_data='CANCEL')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=f"Selected time: {selected_time}\nPlease enter any additional message or press 'SKIP' to continue.",
        reply_markup=reply_markup
    )
    return ENTER_MESSAGE

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
            'status': 'в ожидании',
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

async def enter_message(update: Update, context: CallbackContext):
    user_message = update.message.text
    if user_message.lower() != 'skip':
        context.user_data['message'] = user_message
    else:
        context.user_data['message'] = ''

    user = update.message.from_user
    db = context.bot_data['db']

    try:
        # Get user data from Firestore
        user_data = get_user_by_telegram_username(db, user.username)
        if not user_data:
            await update.message.reply_text("User data not found. Please ensure your Telegram username is linked to your account.")
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

        await update.message.reply_text("Your class was saved. Please wait for the confirmation.")

    except Exception as e:
        logging.error(f"Error in enter_message handler: {e}")
        await update.message.reply_text("There was an error saving your class. Please try again.")

    return ConversationHandler.END

def newclass_conv_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(newclass_start, pattern='^NEWCLASS$')],
        states={
            SELECT_DATE: [CallbackQueryHandler(select_date, pattern='^DATE_')],
            SELECT_TIME: [CallbackQueryHandler(select_time, pattern='^TIME_')],
            ENTER_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_message),
                CallbackQueryHandler(skip_message, pattern='^SKIP$')
            ]
        },
        fallbacks=[CallbackQueryHandler(button_handler, pattern='^CANCEL$')],
    )
