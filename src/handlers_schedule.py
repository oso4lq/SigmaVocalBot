import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext, CallbackQueryHandler, ConversationHandler
from firebase_utils import get_classes_by_date, get_user_by_id, update_class_status
from utils import ST_PETERSBURG
from handlers_button import button_handler

# Define Conversation States
VIEW_SCHEDULE, EDIT_CLASS, EDIT_STATUS = range(3)


# Initiate the SCHEDULE command, setting the default date and displaying the schedule for that date.
async def schedule_start(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    db = context.bot_data['db']

    # Set default date to today in Saint Petersburg timezone
    today = datetime.now(ST_PETERSBURG).date()
    context.user_data['filter_by_this_date'] = today.isoformat()

    # Fetch and display the schedule
    await display_schedule(query.message.chat_id, context)
    return VIEW_SCHEDULE


# Fetch the classes for the specified date and display them as buttons.
async def display_schedule(chat_id, context: CallbackContext):
    db = context.bot_data['db']
    filter_date_str = context.user_data['filter_by_this_date']
    filter_date = datetime.fromisoformat(filter_date_str).date()

    # Fetch classes for the date
    classes = get_classes_by_date(db, filter_date_str)
    buttons = []

    if classes:
        for class_data in classes:
            # Convert UTC startdate to Saint Petersburg time zone
            utc_start = datetime.fromisoformat(class_data['startdate'].replace('Z', '+00:00'))
            spb_start = utc_start.astimezone(ST_PETERSBURG)
            formatted_start = spb_start.strftime('%d.%m.%Y %H:%M')

            # Get student name
            user_data = get_user_by_id(db, class_data['userId'])
            student_name = user_data.get('name', 'Unknown')

            # Create button text
            button_text = f"{formatted_start} | {class_data['status']} | {student_name}"
            buttons.append([InlineKeyboardButton(button_text, callback_data=f"CLASS_{class_data['id']}")])
    else:
        await context.bot.send_message(chat_id=chat_id, text="You don't have classes on this day.")

    # Add navigation buttons
    navigation_buttons = [
        InlineKeyboardButton("<", callback_data='PREV_DAY'),
        InlineKeyboardButton(">", callback_data='NEXT_DAY'),
        InlineKeyboardButton("Cancel", callback_data='CANCEL')
    ]

    buttons.append(navigation_buttons)

    # Format date
    day_name = filter_date.strftime('%A')
    formatted_date = filter_date.strftime('%d.%m.%Y')

    reply_markup = InlineKeyboardMarkup(buttons)
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"Your classes for {day_name}, {formatted_date}. To edit class status or delete it, press the button with this class.",
        reply_markup=reply_markup
    )


# Handlers for < and > buttons to navigate between dates.
async def navigate_date(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    data = query.data
    current_date = datetime.fromisoformat(context.user_data['filter_by_this_date'])

    if data == 'PREV_DAY':
        new_date = current_date - timedelta(days=1)
    elif data == 'NEXT_DAY':
        new_date = current_date + timedelta(days=1)
    else:
        return

    context.user_data['filter_by_this_date'] = new_date.date().isoformat()
    # Edit message to update schedule
    await query.edit_message_reply_markup(reply_markup=None)
    await display_schedule(query.message.chat_id, context)


# Handler for when an admin selects a class to edit.
async def select_class(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    class_id = query.data.split('_')[1]
    context.user_data['selected_class_id'] = class_id
    db = context.bot_data['db']

    # Fetch class data
    class_doc = db.collection('classes').document(class_id).get()
    if not class_doc.exists:
        await query.edit_message_text(text="Class not found.")
        return VIEW_SCHEDULE

    class_data = class_doc.to_dict()
    context.user_data['selected_class_data'] = class_data

    # Convert UTC startdate to Saint Petersburg time zone
    utc_start = datetime.fromisoformat(class_data['startdate'].replace('Z', '+00:00'))
    spb_start = utc_start.astimezone(ST_PETERSBURG)
    formatted_start = spb_start.strftime('%d.%m.%Y %H:%M')

    # Get student name
    user_data = get_user_by_id(db, class_data['userId'])
    student_name = user_data.get('name', 'Unknown')

    # Prepare class details
    is_membership_used = 'Yes' if class_data.get('isMembershipUsed', False) else 'No'
    message_text = (
        f"{formatted_start} | Status: {class_data['status']}\n"
        f"Student: {student_name}\n"
        f"Is membership used: {is_membership_used}\n"
        f"Message: {class_data.get('message', '')}"
    )

    # Display options
    keyboard = [
        [InlineKeyboardButton("Edit Status", callback_data='EDIT_STATUS')],
        [InlineKeyboardButton("Delete Class", callback_data='DELETE_CLASS')],
        [InlineKeyboardButton("Back to the Schedule", callback_data='BACK_TO_SCHEDULE')],
        [InlineKeyboardButton("Cancel", callback_data='CANCEL')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=message_text, reply_markup=reply_markup)
    return EDIT_CLASS


# Handler for editing the class status.
async def edit_status_start(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    class_data = context.user_data['selected_class_data']
    # Prepare class details
    # Convert UTC startdate to Saint Petersburg time zone
    utc_start = datetime.fromisoformat(class_data['startdate'].replace('Z', '+00:00'))
    spb_start = utc_start.astimezone(ST_PETERSBURG)
    formatted_start = spb_start.strftime('%d.%m.%Y %H:%M')

    # Get student name
    db = context.bot_data['db']
    user_data = get_user_by_id(db, class_data['userId'])
    student_name = user_data.get('name', 'Unknown')

    message_text = (
        "You are going to edit the status of this class:\n"
        f"{formatted_start} | Status: {class_data['status']}\n"
        f"Student: {student_name}"
    )

    # Display status options
    keyboard = [
        [InlineKeyboardButton("в ожидании", callback_data='STATUS_в ожидании')],
        [InlineKeyboardButton("подтверждено", callback_data='STATUS_подтверждено')],
        [InlineKeyboardButton("отменено", callback_data='STATUS_отменено')],
        [InlineKeyboardButton("выполнено", callback_data='STATUS_выполнено')],
        [InlineKeyboardButton("Back to the Schedule", callback_data='BACK_TO_SCHEDULE')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=message_text, reply_markup=reply_markup)
    return EDIT_STATUS


# Handler for updating the class status in Firestore.
async def update_status(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    new_status = query.data.split('_')[1]
    class_id = context.user_data['selected_class_id']
    db = context.bot_data['db']

    try:
        update_class_status(db, class_id, new_status)
        await query.edit_message_text(text=f"Class status updated to '{new_status}'.")
    except Exception as e:
        logging.error(f"Error updating class status: {e}")
        await query.edit_message_text(text="There was an error updating the class status. Please try again.")

    # Optionally, return to the schedule or end the conversation
    return ConversationHandler.END


# Prompt admin if they are sure to delete a class
async def delete_class_confirm(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    class_id = context.user_data['selected_class_id']

    await query.edit_message_text(
        text="Are you sure you want to delete this class?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Yes, Delete", callback_data='CONFIRM_DELETE')],
            [InlineKeyboardButton("No, Go Back", callback_data='BACK_TO_SCHEDULE')]
        ])
    )
    return EDIT_CLASS


# Delete Class Handler with membership points refund policy
async def delete_class(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    class_id = context.user_data['selected_class_id']
    db = context.bot_data['db']

    try:
        # Fetch class data
        class_doc_ref = db.collection('classes').document(class_id)
        class_doc = class_doc_ref.get()
        if not class_doc.exists:
            await query.edit_message_text(text="Class not found.")
            return ConversationHandler.END
        class_data = class_doc.to_dict()

        # Fetch user data
        user_data = get_user_by_id(db, class_data['userId'])
        if not user_data:
            await query.edit_message_text(text="User data not found.")
            return ConversationHandler.END

        # Calculate hours difference
        utc_now = datetime.utcnow().replace(tzinfo=ZoneInfo('UTC'))
        class_start = datetime.fromisoformat(class_data['startdate'].replace('Z', '+00:00'))
        hours_difference = (class_start - utc_now).total_seconds() / 3600

        # Determine if refund applies
        refund_membership = False
        if class_data.get('isMembershipUsed', False):
            if hours_difference >= 24:
                refund_membership = True
            elif class_data.get('status') in ['в ожидании', 'отменено']:
                refund_membership = True

        # Start a batch
        batch = db.batch()

        # Delete class document
        batch.delete(class_doc_ref)

        # Update user's classes array
        user_ref = db.collection('users').document(user_data['id'])
        updated_classes = user_data.get('classes', [])
        if class_id in updated_classes:
            updated_classes.remove(class_id)
        # Prepare user data update
        user_update_data = {'classes': updated_classes}
        if refund_membership:
            user_update_data['membership'] = user_data.get('membership', 0) + 1

        batch.update(user_ref, user_update_data)

        # Commit the batch
        batch.commit()

        await query.edit_message_text(text="Class has been deleted and membership points adjusted accordingly.")
    except Exception as e:
        logging.error(f"Error deleting class: {e}")
        await query.edit_message_text(text="There was an error deleting the class. Please try again.")

    return ConversationHandler.END


# Handler to Go Back to Schedule
async def back_to_schedule(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    # Clear selected class data
    context.user_data.pop('selected_class_id', None)
    context.user_data.pop('selected_class_data', None)
    # Edit message to remove previous content
    await query.edit_message_text(text="Returning to schedule...")
    # Display schedule
    await display_schedule(query.message.chat_id, context)
    return VIEW_SCHEDULE


# Define the Conversation Handler
def schedule_conv_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(schedule_start, pattern='^SCHEDULE$')],
        states={
            VIEW_SCHEDULE: [
                CallbackQueryHandler(navigate_date, pattern='^(PREV_DAY|NEXT_DAY)$'),
                CallbackQueryHandler(select_class, pattern='^CLASS_'),
                CallbackQueryHandler(button_handler, pattern='^CANCEL$'),
            ],
            EDIT_CLASS: [
                CallbackQueryHandler(edit_status_start, pattern='^EDIT_STATUS$'),
                CallbackQueryHandler(delete_class_confirm, pattern='^DELETE_CLASS$'),
                CallbackQueryHandler(delete_class, pattern='^CONFIRM_DELETE$'),
                CallbackQueryHandler(back_to_schedule, pattern='^BACK_TO_SCHEDULE$'),
                CallbackQueryHandler(button_handler, pattern='^CANCEL$'),
            ],
            EDIT_STATUS: [
                CallbackQueryHandler(update_status, pattern='^STATUS_'),
                CallbackQueryHandler(back_to_schedule, pattern='^BACK_TO_SCHEDULE$'),
                CallbackQueryHandler(button_handler, pattern='^CANCEL$'),
            ]
        },
        fallbacks=[CallbackQueryHandler(button_handler, pattern='^CANCEL$')],
    )
