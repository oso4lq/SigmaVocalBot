# Handles the /start command, displays user classes, membership points, and action options.

import logging
from datetime import datetime
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommandScopeChat,
    BotCommand,
    Update,
)
from telegram.ext import CallbackContext
from .firebase_utils import (
    get_user_by_telegram_username, 
    get_classes_by_ids
)
from .utils import ST_PETERSBURG


async def start(update: Update, context: CallbackContext):
    db = context.bot_data['db']
    user = None
    chat_id = None

    # Check if the update is from a message or a callback query
    if update.message:
        user = update.message.from_user
        chat_id = update.message.chat_id
    elif update.callback_query:
        user = update.callback_query.from_user
        chat_id = update.callback_query.message.chat_id
    else:
        # Handle unexpected update types
        logging.error("Update does not contain a message or callback_query")
        return

    username = user.full_name or user.username or 'пользователь'

    # Send greeting message
    await context.bot.send_message(chat_id=chat_id, text=f"Добрый день, {username}!")

    # Fetch UserData from Firestore
    try:
        logging.info(f"Looking up user with telegram username: {user.username}")
        user_data = get_user_by_telegram_username(db, user.username)
        logging.info(f"User data found: {user_data}")

        if user_data: # User was found scenario

            # Get info if user is admin
            is_admin = user_data.get('isadmin', False)
            # Get created by this user class IDs
            classes_ids = user_data.get('classes', [])

            # Set commands based on user status
            commands = [
                BotCommand('newclass', 'Записаться на новое занятие'),
                BotCommand('cancelclass', 'Отменить занятие'),
                BotCommand('cancel', 'Отменить команду')
            ]
            if is_admin:
                commands.append(BotCommand('schedule', 'Расписание преподавателя'))

            await context.bot.set_my_commands(
                commands,
                scope=BotCommandScopeChat(update.effective_chat.id)
            )

            if classes_ids:
                # Fetch user's classes
                classes = get_classes_by_ids(db, classes_ids)
                classes_text = ''
                for class_data in classes:
                    # Convert UTC startdate to Saint Petersburg time zone
                    utc_start = datetime.fromisoformat(class_data['startdate'].replace('Z', '+00:00'))
                    spb_start = utc_start.astimezone(ST_PETERSBURG)
                    formatted_start = spb_start.strftime('%d.%m.%Y %H:%M')
                    classes_text += f"- {formatted_start} | статус: {class_data['status']}\n"
                await context.bot.send_message(chat_id=chat_id, text=f"Ваши занятия:\n{classes_text}")
            else:
                await context.bot.send_message(chat_id=chat_id, text="У вас нет запланированных занятий.")

            # Display membership points
            membership_points = user_data.get('membership', 0)
            if membership_points:
                await context.bot.send_message(chat_id=chat_id, text=f"Занятий в абонементе: {membership_points}")
            else:
                await context.bot.send_message(chat_id=chat_id, text="Занятий в абонементе: 0. Чтобы приобрести абонемент, свяжитесь с преподавателем.")

            # Present options
            keyboard = [
                [InlineKeyboardButton("Записаться на новое занятие", callback_data='NEWCLASS')],
                [InlineKeyboardButton("Отменить занятие", callback_data='CANCELCLASS')],
            ]

            # If user is admin, add the "See my schedule" button
            if is_admin:
                keyboard.append([InlineKeyboardButton("Расписание преподавателя", callback_data='SCHEDULE')])

            # Add the Cancel button
            keyboard.append([InlineKeyboardButton("Отмена", callback_data='CANCEL')])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(chat_id=chat_id, text="Выберите действие:", reply_markup=reply_markup)

        else: # User not found scenario

            # Set commands for new users
            await context.bot.set_my_commands(
                [
                    BotCommand('newrequest', 'Оставить заявку на первое занятие'),
                    BotCommand('cancel', 'Отменить команду')
                ],
                scope=BotCommandScopeChat(update.effective_chat.id)
            )

            # Suggest to leave a request as a new user
            await context.bot.send_message(
                chat_id=chat_id,
                text="Похоже, вашего юзернейма пока нет в нашей базе данных. Хотите оставить заявку на первое занятие в ΣΙΓΜΑ?"
            )

            # Option buttons
            keyboard = [
                [InlineKeyboardButton("Оставить заявку", callback_data='NEWREQUEST')],
                [InlineKeyboardButton("Отмена", callback_data='CANCEL')]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(chat_id=chat_id, text="Пожалуйста, выберите действие:", reply_markup=reply_markup)

    except Exception as e:
        logging.error(f"Error in start handler: {e}")
        await context.bot.send_message(chat_id=chat_id, text="Произошла ошибка при получении ваших данных. Повторите попытку позже.")
