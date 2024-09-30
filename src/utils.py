# Contains utility functions that are shared across multiple handler files

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import (
    BotCommandScopeChat,
    BotCommand,
    Update,
)
from telegram.ext import (
    CallbackContext
)
from firebase_utils import (
    get_user_by_telegram_username, 
)

# Define the time zone for Saint Petersburg
ST_PETERSBURG = ZoneInfo('Europe/Moscow')


# Converts a date and time string in 'YYYY-MM-DD' and 'HH:MM' format from Saint Petersburg 
# time zone to UTC ISO8601 string. Optionally adds hours to the time.
def convert_to_utc(date_str: str, time_str: str, add_hours: int = 0) -> str:
    local_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    local_dt = local_dt.replace(tzinfo=ST_PETERSBURG)
    if add_hours:
        local_dt += timedelta(hours=add_hours)
    utc_dt = local_dt.astimezone(ZoneInfo('UTC'))
    return utc_dt.isoformat()


# Helper function to reset commands
async def reset_user_commands(update: Update, context: CallbackContext):
    db = context.bot_data['db']
    user = update.message.from_user if update.message else update.callback_query.from_user
    user_data = get_user_by_telegram_username(db, user.username)
    if user_data:
        is_admin = user_data.get('isadmin', False)
        commands = [
            BotCommand('newclass', 'Sign up for a new class'),
            BotCommand('cancelclass', 'Cancel a class'),
            BotCommand('cancel', 'Cancel the operation')
        ]
        if is_admin:
            commands.append(BotCommand('schedule', 'See my schedule'))
        await context.bot.set_my_commands(
            commands,
            scope=BotCommandScopeChat(update.effective_chat.id)
        )
    else:
        await context.bot.set_my_commands(
            [
                BotCommand('newrequest', 'Leave a request for first class'),
                BotCommand('cancel', 'Cancel the operation')
            ],
            scope=BotCommandScopeChat(update.effective_chat.id)
        )