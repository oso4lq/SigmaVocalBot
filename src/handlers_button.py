# Handles generic button callbacks not managed by ConversationHandler instances.

from telegram import (
    BotCommandScopeChat,
    BotCommand,
    Update,
)
from telegram.ext import (
    ConversationHandler,
    CallbackContext,
)


# Universal handler for buttons
async def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'CANCEL':
        # Send a cancellation message
        await query.edit_message_text(text="Operation cancelled.")

        # Reset commands to default (/start)
        await context.bot.set_my_commands(
            [BotCommand('start', 'Start the bot')],
            scope=BotCommandScopeChat(update.effective_chat.id)
        )
        return ConversationHandler.END
    elif data == 'SKIP':
        # Handle 'SKIP' action
        pass
    else:
        # Handle other generic buttons if any
        await query.edit_message_text(text="Unknown action. Please try again.")
        return ConversationHandler.END


# Runs the "/cancel" command
async def cancel_command(update: Update, context: CallbackContext):
    await update.message.reply_text("Operation cancelled.")

    # Reset commands to default (/start)
    await context.bot.set_my_commands(
        [BotCommand('start', 'Start the bot')],
        scope=BotCommandScopeChat(update.effective_chat.id)
    )
    return ConversationHandler.END