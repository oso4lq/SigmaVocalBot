# Handles the NEWCLASS conversation for booking new classes, including membership point usage.

import logging
from datetime import datetime, timedelta
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
from firebase_utils import get_user_by_telegram_username, get_occupied_time_slots
from utils import convert_to_utc, reset_user_commands, ST_PETERSBURG
from handlers_button import button_handler, cancel_command
from handlers_start import start

# Define Conversation States for NEWCLASS
SELECT_DATE, SELECT_TIME, ENTER_MESSAGE = range(3)


# Entry point. Asks the user to select a date for the new class.
async def newclass_start(update: Update, context: CallbackContext):
    if update.callback_query:
        query = update.callback_query
        await query.edit_message_text(text="Please select a day.")
        chat_id = query.message.chat_id
    else:
        await update.message.reply_text("Please select a day.")
        chat_id = update.message.chat_id

    # Set commands relevant to NEWCLASS
    await context.bot.set_my_commands(
        [BotCommand('cancel', 'Cancel the operation')],
        scope=BotCommandScopeChat(chat_id)
    )

    # Generate available dates
    dates_buttons = []
    today = datetime.now(ST_PETERSBURG)
    for i in range(0, 7):
        day = today + timedelta(days=i)
        if day.weekday() < 5:  # Exclude weekends (0=Monday, ..., 6=Sunday)
            display_date_str = day.strftime('%d.%m.%Y')  # DD.MM.YYYY
            callback_date_str = day.strftime('%Y-%m-%d')  # YYYY-MM-DD
            dates_buttons.append(
                [InlineKeyboardButton(display_date_str, callback_data=f"DATE_{callback_date_str}")]
            )

    dates_buttons.append([InlineKeyboardButton("Cancel", callback_data='CANCEL')])
    reply_markup = InlineKeyboardMarkup(dates_buttons)
    # await context.bot.send_message(chat_id=query.message.chat_id, text="Available dates:", reply_markup=reply_markup)
    await context.bot.send_message(chat_id=chat_id, text="Available dates:", reply_markup=reply_markup)
    return SELECT_DATE


# Handles the date selection. Displays available time slots for the selected date. Filters time slots by current time.
async def select_date(update: Update, context: CallbackContext):
    query = update.callback_query
    selected_date = query.data.split('_')[1]
    context.user_data['selected_date'] = selected_date
    logging.info(f"Selected date: {selected_date}")
    selected_date_display = datetime.strptime(selected_date, '%Y-%m-%d').strftime('%d.%m.%Y')

    await query.edit_message_text(text=f"Selected date: {selected_date_display}\nPlease select a time slot.")

    # Generate time slots
    times_buttons = []
    db = context.bot_data['db']
    occupied_slots = get_occupied_time_slots(db, selected_date)

    # Determine if selected date is today
    today = datetime.now(ST_PETERSBURG).date()
    selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
    current_hour = datetime.now(ST_PETERSBURG).hour

    for hour in range(8, 20):
        # Skip past time slots if selected date is today
        if selected_date_obj == today and hour <= current_hour:
            continue

        start_time = f"{hour:02d}:00"
        end_time = f"{(hour + 1):02d}:00"
        time_slot_display = f"{start_time} - {end_time}"
        if start_time not in occupied_slots:
            times_buttons.append(
                [InlineKeyboardButton(time_slot_display, callback_data=f"TIME_{start_time}")]
            )

    if times_buttons:
        # Add 'Back to selecting a date' button
        times_buttons.append([InlineKeyboardButton("Back to selecting a date", callback_data='BACK_TO_DATE')])
        times_buttons.append([InlineKeyboardButton("Cancel", callback_data='CANCEL')])
        reply_markup = InlineKeyboardMarkup(times_buttons)
        await context.bot.send_message(chat_id=query.message.chat_id, text="Available time slots:", reply_markup=reply_markup)
    else:
        # If no time slots are available
        await context.bot.send_message(chat_id=query.message.chat_id, text="No available time slots for this date. Please select another date.")
        # Return to date selection
        return await back_to_date_selection(update, context)

    return SELECT_TIME


# Handles the time slot selection. Asks the user to enter an additional message or skip.
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


# Handles the case when the user skips entering an additional message. Saves the class and updates the database.
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

    # Reset commands based on user status
    await reset_user_commands(update, context)

    # Call the start function to display updated class list
    await start(update, context)

    return ConversationHandler.END


# Handles the user's additional message input. Saves the class and updates the database.
async def enter_message(update: Update, context: CallbackContext):
    user_message = update.message.text
    if user_message.lower() != 'skip':
        context.user_data['message'] = user_message # Save the message
    else:
        context.user_data['message'] = ''

    # Save the request to Firestore
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

        await update.message.reply_text("Your class was saved. Please wait for the confirmation.")

    except Exception as e:
        logging.error(f"Error in enter_message handler: {e}")
        await update.message.reply_text("There was an error saving your class. Please try again.")

    # Reset commands based on user status
    await reset_user_commands(update, context)

    # Call the start function to display updated class list
    await start(update, context)

    return ConversationHandler.END


# Handles the 'Back to selecting a date' action. Returns the user to the date selection.
async def back_to_date_selection(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text="Please select a day.")

    # Generate available dates
    dates_buttons = []
    today = datetime.now(ST_PETERSBURG)
    for i in range(0, 7):  # Start from 0 to include today
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


# Defines the ConversationHandler for the NEWCLASS flow. States: SELECT_DATE, SELECT_TIME and ENTER_MESSAGE.
def newclass_conv_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(newclass_start, pattern='^NEWCLASS$'),
            CommandHandler('newclass', newclass_start),
        ],
        states={
            SELECT_DATE: [
                CallbackQueryHandler(select_date, pattern='^DATE_'),
                CallbackQueryHandler(button_handler, pattern='^CANCEL$')
            ],
            SELECT_TIME: [
                CallbackQueryHandler(select_time, pattern='^TIME_'),
                CallbackQueryHandler(back_to_date_selection, pattern='^BACK_TO_DATE$'),
                CallbackQueryHandler(button_handler, pattern='^CANCEL$')
            ],
            ENTER_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_message),
                CallbackQueryHandler(skip_message, pattern='^SKIP$'),
                CallbackQueryHandler(button_handler, pattern='^CANCEL$')
            ]
        },
        fallbacks=[
            CallbackQueryHandler(button_handler, pattern='^CANCEL$'),
            CommandHandler('cancel', cancel_command),
        ],
    )
