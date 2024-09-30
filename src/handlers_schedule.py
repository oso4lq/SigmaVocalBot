# Handles the SCHEDULE conversation: schedule for a day, switch between days, edit class status, delete class, refund policy.

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    CallbackQueryHandler,
    ConversationHandler,
    CallbackContext,
    CommandHandler,
)
from firebase_utils import get_classes_by_date, get_user_by_id, update_class_status
from handlers_button import button_handler, cancel_command
from utils import ST_PETERSBURG

# Define Conversation States
VIEW_SCHEDULE, EDIT_CLASS, EDIT_STATUS = range(3)


# Initiate the SCHEDULE command, setting the default date and displaying the schedule for that date.
async def schedule_start(update: Update, context: CallbackContext):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        chat_id = query.message.chat_id
    else:
        await update.message.reply_text("Загружаю расписание...")
        chat_id = update.message.chat_id

    db = context.bot_data['db']
    # Set default date to today in Saint Petersburg timezone
    today = datetime.now(ST_PETERSBURG).date()
    context.user_data['filter_by_this_date'] = today.isoformat()

    # Fetch and display the schedule
    await display_schedule(chat_id, context)
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
        await context.bot.send_message(chat_id=chat_id, text="В этот день у вас нет занятий.")

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
        text=f"Ваши занятия на {day_name}, {formatted_date}. Чтобы изменить статус или удалить, нажмите кнопку с этим занятием.",
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
        await query.edit_message_text(text="Занятие не найдено.")
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
    is_membership_used = 'да' if class_data.get('isMembershipUsed', False) else 'нет'
    message_text = (
        f"{formatted_start} | статус: {class_data['status']}\n"
        f"Ученик: {student_name}\n"
        f"Использован абонемент: {is_membership_used}\n"
        f"Сообщение: {class_data.get('message', '')}"
    )

    # Display options
    keyboard = [
        [InlineKeyboardButton("Изменить статус", callback_data='EDIT_STATUS')],
        [InlineKeyboardButton("Удалить занятие", callback_data='DELETE_CLASS')],
        [InlineKeyboardButton("Назад к расписанию", callback_data='BACK_TO_SCHEDULE')],
        [InlineKeyboardButton("Отмена", callback_data='CANCEL')]
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
        "Вы собираетесь изменить статус этого занятия:\n"
        f"{formatted_start} | статус: {class_data['status']}\n"
        f"Ученик: {student_name}"
    )

    # Display status options
    keyboard = [
        [InlineKeyboardButton("В ожидании", callback_data='STATUS_в ожидании')],
        [InlineKeyboardButton("Подтверждено", callback_data='STATUS_подтверждено')],
        [InlineKeyboardButton("Отменено", callback_data='STATUS_отменено')],
        [InlineKeyboardButton("Выполнено", callback_data='STATUS_выполнено')],
        [InlineKeyboardButton("Назад к расписанию", callback_data='BACK_TO_SCHEDULE')]
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
        await query.edit_message_text(text=f"Статус занятия изменён на: '{new_status}'.")
    except Exception as e:
        logging.error(f"Error updating class status: {e}")
        await query.edit_message_text(text="Произошла ошибка обновления статуса занятия. Попробуйте ещё раз.")

    # Optionally, End the conversation or Refresh the schedule
    # return ConversationHandler.END # End the conversation
    await display_schedule(query.message.chat_id, context)
    return VIEW_SCHEDULE  # Return to the schedule viewing state


# Prompt admin if they are sure to delete a class
async def delete_class_confirm(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    class_id = context.user_data['selected_class_id']

    await query.edit_message_text(
        text="Вы уверены, что хотите удалить это занятие?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Да, удалить", callback_data='CONFIRM_DELETE')],
            [InlineKeyboardButton("Нет, вернуться", callback_data='BACK_TO_SCHEDULE')]
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
            await query.edit_message_text(text="Занятие не найдено.")
            return ConversationHandler.END
        class_data = class_doc.to_dict()

        # Fetch user data
        user_data = get_user_by_id(db, class_data['userId'])
        if not user_data:
            await query.edit_message_text(text="Данные пользователя не найдены.")
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

        await query.edit_message_text(text="Занятие удалено, баллы абонемента скорректированы.")
    except Exception as e:
        logging.error(f"Error deleting class: {e}")
        await query.edit_message_text(text="Произошла ошибка при удалении занятия. Попробуйте ещё раз.")

    # Optionally, End the conversation or Refresh the schedule
    # return ConversationHandler.END # End the conversation
    await display_schedule(query.message.chat_id, context)
    return VIEW_SCHEDULE  # Return to the schedule viewing state


# Handler to Go Back to Schedule
async def back_to_schedule(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    # Clear selected class data
    context.user_data.pop('selected_class_id', None)
    context.user_data.pop('selected_class_data', None)

    # Edit message to remove previous content
    await query.edit_message_text(text="Возвращаюсь к расписанию...")

    # Display schedule
    await display_schedule(query.message.chat_id, context)
    return VIEW_SCHEDULE


# Define the Conversation Handler
def schedule_conv_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(schedule_start, pattern='^SCHEDULE$'),
            CommandHandler('schedule', schedule_start),
        ],
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
        fallbacks=[
            CallbackQueryHandler(button_handler, pattern='^CANCEL$'),
            CommandHandler('cancel', cancel_command),
        ],
    )
