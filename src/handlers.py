# This module will contain all your command and conversation handlers. 
# It imports necessary functions from firebase_utils.py to interact with Firestore.

# Handler Functions: Each handler function is responsible for a specific part 
# of the conversation or command flow.

# Conversation Handlers: ConversationHandler objects manage multi-step interactions 
# like booking a new class or cancelling an existing one.

# Database Interactions: Handlers use functions from firebase_utils.py to interact with Firestore, 
# ensuring a clear separation of concerns.

# Error Handling: Errors are logged using Python's logging module, and users are notified appropriately.

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, Any
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup
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
    get_classes_by_ids, 
    get_occupied_time_slots,
    add_new_class, 
    update_user_classes, 
    add_new_request,
    remove_user_class, 
    delete_class,  # Newly added
    update_class_status,  # Can be removed if not used elsewhere
)

# Define Conversation States for NEWCLASS
SELECT_DATE, SELECT_TIME, ENTER_MESSAGE = range(3)

# Define Conversation States for NEWREQUEST
ENTER_NAME, ENTER_REQUEST_MESSAGE = range(2)

# Define Conversation States for CANCELCLASS
SELECT_CLASS_TO_CANCEL, CONFIRM_CANCELLATION = range(2)

# Define the time zone for Saint Petersburg
ST_PETERSBURG = ZoneInfo('Europe/Moscow')  # Saint Petersburg uses Moscow's time zone

# START Command Handler
async def start(update: Update, context: CallbackContext):
    db = context.bot_data['db']
    user = update.message.from_user
    username = user.full_name or user.username or 'there'
    chat_id = update.effective_chat.id

    # Send greeting message
    await context.bot.send_message(chat_id=chat_id, text=f"Hello, {username}!")

    # Fetch UserData from Firestore
    try:
        logging.info(f"Looking up user with telegram username: {user.username}")
        user_data = get_user_by_telegram_username(db, user.username)
        logging.info(f"User data found: {user_data}")
        if user_data:
            # User exists
            classes_ids = user_data.get('classes', [])
            if classes_ids:
                # Fetch user's classes
                classes = get_classes_by_ids(db, classes_ids)
                classes_text = ''
                for class_data in classes:
                    # Convert UTC startdate to Saint Petersburg time zone
                    utc_start = datetime.fromisoformat(class_data['startdate'].replace('Z', '+00:00'))
                    spb_start = utc_start.astimezone(ST_PETERSBURG)
                    formatted_start = spb_start.strftime('%d.%m.%Y %H:%M')
                    classes_text += f"- {formatted_start} | Status: {class_data['status']}\n"
                await context.bot.send_message(chat_id=chat_id, text=f"Your classes:\n{classes_text}")
                # Present options
                keyboard = [
                    [InlineKeyboardButton("Sign Up for New Class", callback_data='NEWCLASS')],
                    [InlineKeyboardButton("Cancel a Class", callback_data='CANCELCLASS')],
                    [InlineKeyboardButton("Cancel", callback_data='CANCEL')]
                ]
            else:
                await context.bot.send_message(chat_id=chat_id, text="You don't have any classes scheduled.")
                keyboard = [
                    [InlineKeyboardButton("Sign Up for New Class", callback_data='NEWCLASS')],
                    [InlineKeyboardButton("Cancel", callback_data='CANCEL')]
                ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(chat_id=chat_id, text="What would you like to do next?", reply_markup=reply_markup)
        else:
            # User not found
            await context.bot.send_message(
                chat_id=chat_id,
                text="It looks like your username is not in our database yet. Would you like to leave a request for your first class in Sigma?"
            )
            keyboard = [
                [InlineKeyboardButton("Leave a Request", callback_data='NEWREQUEST')],
                [InlineKeyboardButton("Cancel", callback_data='CANCEL')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(chat_id=chat_id, reply_markup=reply_markup)
    except Exception as e:
        logging.error(f"Error in start handler: {e}")
        await context.bot.send_message(chat_id=chat_id, text="An error occurred while fetching your data. Please try again later.")

# Button Handler (Handles generic buttons not managed by ConversationHandlers)
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

# NEWCLASS Handlers
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

# Handler for SKIP button in ENTER_MESSAGE state
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
            'isMembershipUsed': False,
            'userId': user_data['id'],  # Use userData.id from Firestore
        }

        # Add the new class to Firestore
        new_class_id = add_new_class(db, class_data)
        if new_class_id:
            # Update user's classes list
            success = update_user_classes(db, user_data['id'], new_class_id)
            if success:
                await query.message.reply_text("Your class was saved. Please wait for the confirmation.")
            else:
                await query.message.reply_text("Your class was saved, but we couldn't update your class list. Please contact support.")
        else:
            await query.message.reply_text("There was an error saving your class. Please try again.")

    except Exception as e:
        logging.error(f"Error in skip_message handler: {e}")
        await query.message.reply_text("There was an error saving your class. Please try again.")

    return ConversationHandler.END

# Handler for text input in ENTER_MESSAGE state
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
            'isMembershipUsed': False,
            'userId': user_data['id'],  # Use userData.id from Firestore
        }

        # Add the new class to Firestore
        new_class_id = add_new_class(db, class_data)
        if new_class_id:
            # Update user's classes list
            success = update_user_classes(db, user_data['id'], new_class_id)
            if success:
                await update.message.reply_text("Your class was saved. Please wait for the confirmation.")
            else:
                await update.message.reply_text("Your class was saved, but we couldn't update your class list. Please contact support.")
        else:
            await update.message.reply_text("There was an error saving your class. Please try again.")

    except Exception as e:
        logging.error(f"Error in enter_message handler: {e}")
        await update.message.reply_text("There was an error saving your class. Please try again.")

    return ConversationHandler.END

# Function to convert local time to UTC ISO8601 string
def convert_to_utc(date_str: str, time_str: str, add_hours: int = 0) -> str:
    """
    Converts a date and time string in 'YYYY-MM-DD' and 'HH:MM' format from
    Saint Petersburg time zone to UTC ISO8601 string.
    Optionally adds hours to the time.
    """
    local_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    local_dt = local_dt.replace(tzinfo=ST_PETERSBURG)
    if add_hours:
        local_dt += timedelta(hours=add_hours)
    utc_dt = local_dt.astimezone(ZoneInfo('UTC'))
    return utc_dt.isoformat()

# Define the NEWCLASS Conversation Handler
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

# NEWREQUEST Handlers
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

# Define the NEWREQUEST Conversation Handler
def newrequest_conv_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(newrequest_start, pattern='^NEWREQUEST$')],
        states={
            ENTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name)],
            ENTER_REQUEST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_request_message)]
        },
        fallbacks=[CallbackQueryHandler(button_handler, pattern='^CANCEL$')],
    )

# CANCELCLASS Handlers
async def cancelclass_start(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    db = context.bot_data['db']

    # Get user data
    user_data = get_user_by_telegram_username(db, user.username)
    if not user_data:
        await query.edit_message_text(text="User data not found.")
        return ConversationHandler.END

    classes_ids = user_data.get('classes', [])
    if classes_ids:
        # Fetch user's classes
        classes = get_classes_by_ids(db, classes_ids)
        classes_buttons = []
        for class_data in classes:
            class_id = class_data.get('id')
            # Convert UTC startdate to Saint Petersburg time zone for display
            utc_start = datetime.fromisoformat(class_data['startdate'].replace('Z', '+00:00'))
            spb_start = utc_start.astimezone(ST_PETERSBURG)
            formatted_start = spb_start.strftime('%d.%m.%Y %H:%M')
            class_info = f"{formatted_start} | Status: {class_data['status']}"
            classes_buttons.append(
                [InlineKeyboardButton(class_info, callback_data=f"CANCEL_{class_id}")]
            )
        classes_buttons.append([InlineKeyboardButton("Cancel", callback_data='CANCEL')])
        reply_markup = InlineKeyboardMarkup(classes_buttons)
        await query.edit_message_text(text="Choose a class you would like to cancel:", reply_markup=reply_markup)
        return SELECT_CLASS_TO_CANCEL
    else:
        await query.edit_message_text(text="You don't have any classes signed up for.")
        return ConversationHandler.END

async def select_class_to_cancel(update: Update, context: CallbackContext):
    query = update.callback_query
    class_id = query.data.split('_')[1]
    context.user_data['class_id_to_cancel'] = class_id
    db = context.bot_data['db']
    class_doc = db.collection('classes').document(class_id).get()
    if class_doc.exists:
        class_data = class_doc.to_dict()
        # Convert UTC startdate to Saint Petersburg time zone for display
        utc_start = datetime.fromisoformat(class_data['startdate'].replace('Z', '+00:00'))
        spb_start = utc_start.astimezone(ST_PETERSBURG)
        formatted_start = spb_start.strftime('%d.%m.%Y %H:%M')
        class_info = f"{formatted_start} | Status: {class_data['status']}"
        await query.edit_message_text(
            text=f"Are you sure you want to cancel this class?\n{class_info}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Yes, Cancel", callback_data='CONFIRM_CANCEL')],
                [InlineKeyboardButton("No, Go Back", callback_data='CANCEL')]
            ])
        )
        return CONFIRM_CANCELLATION
    else:
        await query.edit_message_text(text="Class not found.")
        return ConversationHandler.END

async def confirm_cancellation(update: Update, context: CallbackContext):
    query = update.callback_query
    class_id = context.user_data.get('class_id_to_cancel')
    user = query.from_user
    if not class_id:
        await query.edit_message_text(text="No class selected for cancellation.")
        return ConversationHandler.END

    db = context.bot_data['db']

    # Get user data
    user_data = get_user_by_telegram_username(db, user.username)
    if not user_data:
        await query.edit_message_text(text="User data not found.")
        return ConversationHandler.END

    try:
        # Remove class from user's classes
        success_remove = remove_user_class(db, user_data['id'], class_id)
        # Delete class document from Firestore
        success_delete = delete_class(db, class_id)
        if success_remove and success_delete:
            await query.edit_message_text(text="Your class has been cancelled.")
        else:
            await query.edit_message_text(text="There was an error cancelling your class. Please try again.")
    except Exception as e:
        logging.error(f"Error in confirm_cancellation handler: {e}")
        await query.edit_message_text(text="There was an error cancelling your class. Please try again.")

    return ConversationHandler.END

# Define the CANCELCLASS Conversation Handler
def cancelclass_conv_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(cancelclass_start, pattern='^CANCELCLASS$')],
        states={
            SELECT_CLASS_TO_CANCEL: [CallbackQueryHandler(select_class_to_cancel, pattern='^CANCEL_')],
            CONFIRM_CANCELLATION: [CallbackQueryHandler(confirm_cancellation, pattern='^CONFIRM_CANCEL$')]
        },
        fallbacks=[CallbackQueryHandler(button_handler, pattern='^CANCEL$')],
    )