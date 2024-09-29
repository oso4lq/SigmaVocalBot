# Handles the CANCELCLASS conversation, including displaying refund policy messages based on class details.

import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackContext, 
    ConversationHandler, 
    CallbackQueryHandler
)
from firebase_utils import get_user_by_telegram_username, delete_class
from firebase_utils import get_user_by_telegram_username, get_classes_by_ids
from handlers_button import button_handler
from utils import ST_PETERSBURG

# Define Conversation States for CANCELCLASS
SELECT_CLASS_TO_CANCEL, CONFIRM_CANCELLATION = range(2)

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
        context.user_data['selected_class_data'] = class_data  # Store for later use

        # Convert UTC startdate to Saint Petersburg time zone for display
        utc_start = datetime.fromisoformat(class_data['startdate'].replace('Z', '+00:00'))
        spb_start = utc_start.astimezone(ST_PETERSBURG)
        formatted_start = spb_start.strftime('%d.%m.%Y %H:%M')
        class_info = f"{formatted_start} | Status: {class_data['status']}"

        # Calculate hours difference
        utc_now = datetime.utcnow().replace(tzinfo=ZoneInfo('UTC'))
        hours_difference = (utc_start - utc_now).total_seconds() / 3600

        # Determine the message to display
        message = ''
        if (
            hours_difference <= 24 and
            class_data.get('isMembershipUsed', False) and
            class_data.get('status') == 'подтверждено'
        ):
            message = (
                "The teacher has already confirmed this class and it starts in less than 24 hours. "
                "By canceling this class, you will lose the class from your membership."
            )
        elif (
            class_data.get('isMembershipUsed', False) and
            class_data.get('status') != 'выполнено'
        ):
            message = "You can cancel a lesson without losing your membership points."
        else:
            message = ''

        # Append the message
        full_text = f"Are you sure you want to cancel this class?\n{class_info}"
        if message:
            full_text += f"\n\n{message}"

        await query.edit_message_text(
            text=full_text,
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
        # Get the latest class data
        class_doc_ref = db.collection('classes').document(class_id)
        class_doc = class_doc_ref.get()
        if not class_doc.exists:
            await query.edit_message_text(text="Class not found.")
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

        await query.edit_message_text(text="Your class has been cancelled.")

    except Exception as e:
        logging.error(f"Error in confirm_cancellation handler: {e}")
        await query.edit_message_text(text="There was an error cancelling your class. Please try again.")

    return ConversationHandler.END

def cancelclass_conv_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(cancelclass_start, pattern='^CANCELCLASS$')],
        states={
            SELECT_CLASS_TO_CANCEL: [CallbackQueryHandler(select_class_to_cancel, pattern='^CANCEL_')],
            CONFIRM_CANCELLATION: [CallbackQueryHandler(confirm_cancellation, pattern='^CONFIRM_CANCEL$')]
        },
        fallbacks=[CallbackQueryHandler(button_handler, pattern='^CANCEL$')],
    )
