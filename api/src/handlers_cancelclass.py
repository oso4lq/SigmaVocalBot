# Handles the CANCELCLASS conversation, including displaying refund policy messages based on class details.

import logging
from datetime import datetime
from zoneinfo import ZoneInfo
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
    CommandHandler,
)
from .firebase_utils import get_user_by_telegram_username, get_classes_by_ids
from .handlers_button import button_handler, cancel_command
from .utils import reset_user_commands, ST_PETERSBURG
from .handlers_start import start


# Define Conversation States for CANCELCLASS
SELECT_CLASS_TO_CANCEL, CONFIRM_CANCELLATION = range(2)


 # Entry point. Displays a list of the user's classes to select for cancellation.
async def cancelclass_start(update: Update, context: CallbackContext):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        user = query.from_user
        chat_id = query.message.chat_id
    else:
        user = update.message.from_user
        chat_id = update.message.chat_id
        await update.message.reply_text("Выберите занятие, которое вы хотите отменить:")

    # Set commands relevant to CANCELCLASS
    await context.bot.set_my_commands(
        [BotCommand('cancel', 'Отменить команду')],
        scope=BotCommandScopeChat(chat_id)
    )

    # Get user data
    db = context.bot_data['db']
    user_data = get_user_by_telegram_username(db, user.username)
    if not user_data:
        await context.bot.send_message(chat_id=chat_id, text="Данные пользователя не найдены.")
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
            class_info = f"{formatted_start} | статус: {class_data['status']}"
            classes_buttons.append(
                [InlineKeyboardButton(class_info, callback_data=f"CANCEL_{class_id}")]
            )
        classes_buttons.append([InlineKeyboardButton("Отмена", callback_data='CANCEL')])
        reply_markup = InlineKeyboardMarkup(classes_buttons)
        await query.edit_message_text(text="Выберите занятие, которое вы хотите отменить:", reply_markup=reply_markup)
        return SELECT_CLASS_TO_CANCEL
    else:
        await query.edit_message_text(text="У вас нет занятий.")
        return ConversationHandler.END


# Handles the selection of a class to cancel. Asks the user to confirm the cancellation.
async def select_class_to_cancel(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    class_id = query.data.split('_')[1]
    context.user_data['class_id_to_cancel'] = class_id
    db = context.bot_data['db']
    class_doc = db.collection('classes').document(class_id).get()
    
    if class_doc.exists:
        class_data = class_doc.to_dict()
        context.user_data['selected_class_data'] = class_data  # Store for later use

        # Convert UTC startdate to Saint Petersburg time zone for display
        utc_start = datetime.fromisoformat(class_data['startdate'].replace('Z', '+00:00'))
        spb_start = utc_start.astimezone(ST_PETERSBURG)
        formatted_start = spb_start.strftime('%d.%m.%Y %H:%M')
        class_info = f"{formatted_start} | статус: {class_data['status']}"

        # Calculate hours difference
        utc_now = datetime.utcnow().replace(tzinfo=ZoneInfo('UTC'))
        hours_difference = (utc_start - utc_now).total_seconds() / 3600

        # Determine the message to display based on refund policy
        message = ''
        if (
            hours_difference <= 24 and
            class_data.get('isMembershipUsed', False) and
            class_data.get('status') == 'подтверждено'
        ):
            message = (
                "Преподаватель уже подтвердил это занятие, и до его начала остаётся менее 24 часов. "
                "Отменив это занятие, вы потеряете занятие из абонемента."
            )
        elif (
            class_data.get('isMembershipUsed', False) and
            class_data.get('status') != 'выполнено'
        ):
            message = "Вы можете отменить урок без потери занятия из абонемента."
        else:
            message = ""

        # Append the message if applicable
        full_text = f"Вы уверены, что хотите отменить занятие?\n{class_info}"
        if message:
            full_text += f"\n\n{message}"

        # Display confirmation options
        await query.edit_message_text(
            text=full_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Да, отменить", callback_data='CONFIRM_CANCEL')],
                [InlineKeyboardButton("Нет, вернуться", callback_data='BACK_TO_CLASS_LIST')],
                [InlineKeyboardButton("Отмена", callback_data='CANCEL')]
            ])
        )
        return CONFIRM_CANCELLATION
    else:
        await query.edit_message_text(text="Занятие не найдено.")
        return ConversationHandler.END


#  Handles the confirmation of class cancellation. Updates the database accordingly.
async def confirm_cancellation(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    class_id = context.user_data.get('class_id_to_cancel')
    user = query.from_user
    if not class_id:
        await query.edit_message_text(text="Не выбрано занятие для отмены.")
        return ConversationHandler.END

    db = context.bot_data['db']

    # Get user data
    user_data = get_user_by_telegram_username(db, user.username)
    if not user_data:
        await query.edit_message_text(text="Данные пользователя не найдены.")
        return ConversationHandler.END

    try:
        # Get the latest class data
        class_doc_ref = db.collection('classes').document(class_id)
        class_doc = class_doc_ref.get()
        if not class_doc.exists:
            await query.edit_message_text(text="Занятие не найдено.")
            return ConversationHandler.END
        class_data = class_doc.to_dict()

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

        await query.edit_message_text(text="Ваше занятие отменено.")

    except Exception as e:
        logging.error(f"Error in confirm_cancellation handler: {e}")
        await query.edit_message_text(text="Произошла ошибка при отмене вашего занятия. Попробуйте ещё раз.")

    # Reset commands based on user status
    await reset_user_commands(update, context)

    # Call the start function to display updated class list
    await start(update, context)

    return ConversationHandler.END


# Handles the 'No, Go Back' action. Returns the user to the list of classes to select.
async def back_to_class_list(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    # Fetch user's classes
    user = query.from_user
    db = context.bot_data['db']
    user_data = get_user_by_telegram_username(db, user.username)
    if not user_data:
        await query.edit_message_text(text="Данные пользователя не найдены. Убедитесь, что ваш Telegram связан с учётной записью.")
        return ConversationHandler.END

    classes_ids = user_data.get('classes', [])
    if classes_ids:
        # Fetch user's classes
        classes = get_classes_by_ids(db, classes_ids)
        buttons = []
        for class_data in classes:
            # Convert UTC startdate to Saint Petersburg time zone
            utc_start = datetime.fromisoformat(class_data['startdate'].replace('Z', '+00:00'))
            spb_start = utc_start.astimezone(ST_PETERSBURG)
            formatted_start = spb_start.strftime('%d.%m.%Y %H:%M')
            button_text = f"{formatted_start} | Status: {class_data['status']}"
            buttons.append([InlineKeyboardButton(button_text, callback_data=f"CANCEL_{class_data['id']}")])

        buttons.append([InlineKeyboardButton("Cancel", callback_data='CANCEL')])
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.edit_message_text(text="Выберите занятие, которое вы хотите отменить:", reply_markup=reply_markup)
        return SELECT_CLASS_TO_CANCEL
    else:
        await query.edit_message_text(text="У вас нет занятий.")
        return ConversationHandler.END


# Defines the ConversationHandler for the CANCELCLASS flow. States: SELECT_CLASS_TO_CANCEL and CONFIRM_CANCELLATION.
def cancelclass_conv_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(cancelclass_start, pattern='^CANCELCLASS$'),
            CommandHandler('cancelclass', cancelclass_start)
        ],
        states={
            SELECT_CLASS_TO_CANCEL: [
                CallbackQueryHandler(select_class_to_cancel, pattern='^CANCEL_'),
                CallbackQueryHandler(button_handler, pattern='^CANCEL$')
            ],
            CONFIRM_CANCELLATION: [
                CallbackQueryHandler(confirm_cancellation, pattern='^CONFIRM_CANCEL$'),
                CallbackQueryHandler(back_to_class_list, pattern='^BACK_TO_CLASS_LIST$'),  # Added handler
                CallbackQueryHandler(button_handler, pattern='^CANCEL$')
            ],
        },
        fallbacks=[
            CallbackQueryHandler(button_handler, pattern='^CANCEL$'),
            CommandHandler('cancel', cancel_command),
        ],
    )
