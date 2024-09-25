import firebase_admin
from firebase_admin import credentials, firestore
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, ConversationHandler, MessageHandler, Filters

cred = credentials.Certificate('sigma-serviceAccountKey.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

TOKEN = '7215530612:AAFvaxWYTuBU02cwT2zHfCLuLqKpJ9YmtuA'

updater = Updater(token=TOKEN, use_context=True)
dispatcher = updater.dispatcher


# Implementing START Command
def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    username = user.full_name or user.username or 'there'
    chat_id = update.effective_chat.id

    # Send greeting message
    context.bot.send_message(chat_id=chat_id, text=f"Hello, {username}!")

    # Fetch UserData from Firestore
    try:
        users_ref = db.collection('users')
        query = users_ref.where('telegram', '==', user.username).stream()
        user_docs = list(query)
        if user_docs:
            # User exists
            user_data = user_docs[0].to_dict()
            classes_ids = user_data.get('classes', [])
            if classes_ids:
                # Fetch user's classes
                classes_text = ''
                for class_id in classes_ids:
                    class_doc = db.collection('classes').document(str(class_id)).get()
                    if class_doc.exists:
                        class_data = class_doc.to_dict()
                        classes_text += f"- {class_data['startdate']} | Status: {class_data['status']}\n"
                context.bot.send_message(chat_id=chat_id, text=f"Your classes:\n{classes_text}")
                # Present options
                keyboard = [
                    [InlineKeyboardButton("Sign Up for New Class", callback_data='NEWCLASS')],
                    [InlineKeyboardButton("Cancel a Class", callback_data='CANCELCLASS')],
                    [InlineKeyboardButton("Cancel", callback_data='CANCEL')]
                ]
            else:
                context.bot.send_message(chat_id=chat_id, text="You don't have any classes scheduled.")
                keyboard = [
                    [InlineKeyboardButton("Sign Up for New Class", callback_data='NEWCLASS')],
                    [InlineKeyboardButton("Cancel", callback_data='CANCEL')]
                ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            context.bot.send_message(chat_id=chat_id, text="What would you like to do next?", reply_markup=reply_markup)
        else:
            # User not found
            context.bot.send_message(
                chat_id=chat_id,
                text="It looks like your username is not in our database yet. Would you like to leave a request for your first class in Sigma?"
            )
            keyboard = [
                [InlineKeyboardButton("Leave a Request", callback_data='NEWREQUEST')],
                [InlineKeyboardButton("Cancel", callback_data='CANCEL')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            context.bot.send_message(chat_id=chat_id, reply_markup=reply_markup)
    except Exception as e:
        context.bot.send_message(chat_id=chat_id, text="An error occurred while fetching your data. Please try again later.")

# Add the Start Handler to the Dispatcher
dispatcher.add_handler(CommandHandler('start', start))


# Define a handler to manage button presses
def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = query.data

    if data == 'NEWCLASS':
        return newclass_start(update, context)
    elif data == 'CANCELCLASS':
        return cancelclass_start(update, context)
    elif data == 'NEWREQUEST':
        return newrequest_start(update, context)
    elif data == 'CANCEL':
        start(update, context)

# Add the Button Handler to the Dispatcher
dispatcher.add_handler(CallbackQueryHandler(button_handler))


# Implementing NEWCLASS Command
# Define Conversation States
SELECT_DATE, SELECT_TIME, ENTER_MESSAGE = range(3)

# Start New Class Booking
def newclass_start(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    query = update.callback_query
    query.edit_message_text(text="Please select a day.")

    # Generate available dates
    from datetime import datetime, timedelta

    dates_buttons = []
    today = datetime.now()
    for i in range(1, 8):
        day = today + timedelta(days=i)
        if day.weekday() < 5:  # Exclude weekends (0=Monday, ..., 6=Sunday)
            date_str = day.strftime('%Y-%m-%d')
            dates_buttons.append(
                [InlineKeyboardButton(date_str, callback_data=f"DATE_{date_str}")]
            )

    dates_buttons.append([InlineKeyboardButton("Cancel", callback_data='CANCEL')])
    reply_markup = InlineKeyboardMarkup(dates_buttons)
    context.bot.send_message(chat_id=chat_id, text="Available dates:", reply_markup=reply_markup)
    return SELECT_DATE

# Handle Date Selection
def select_date(update: Update, context: CallbackContext):
    query = update.callback_query
    selected_date = query.data.split('_')[1]
    context.user_data['selected_date'] = selected_date
    query.edit_message_text(text=f"Selected date: {selected_date}\nPlease select a time slot.")

    # Generate time slots
    times_buttons = []
    occupied_slots = []

    # Fetch occupied time slots from Firestore
    classes_ref = db.collection('classes')
    booked_classes = classes_ref.where('startdate', '>=', f"{selected_date}T00:00:00").where('startdate', '<=', f"{selected_date}T23:59:59").stream()
    for class_doc in booked_classes:
        class_data = class_doc.to_dict()
        time = class_data['startdate'].split('T')[1][:5]
        occupied_slots.append(time)

    for hour in range(8, 20):
        time_slot = f"{hour:02d}:00"
        if time_slot not in occupied_slots:
            times_buttons.append(
                [InlineKeyboardButton(time_slot, callback_data=f"TIME_{time_slot}")]
            )

    times_buttons.append([InlineKeyboardButton("Cancel", callback_data='CANCEL')])
    reply_markup = InlineKeyboardMarkup(times_buttons)
    context.bot.send_message(chat_id=query.message.chat_id, text="Available time slots:", reply_markup=reply_markup)
    return SELECT_TIME

# Handle Time Selection
def select_time(update: Update, context: CallbackContext):
    query = update.callback_query
    selected_time = query.data.split('_')[1]
    context.user_data['selected_time'] = selected_time
    query.edit_message_text(text=f"Selected time: {selected_time}\nPlease enter any additional message or type 'skip' to continue.")
    return ENTER_MESSAGE

# Handle Message Entry
def enter_message(update: Update, context: CallbackContext):
    user_message = update.message.text
    if user_message.lower() != 'skip':
        context.user_data['message'] = user_message
    else:
        context.user_data['message'] = ''
    # Proceed to save the class
    user = update.message.from_user

    # Assuming you have the user's ID stored or retrieved earlier
    try:
        class_data = {
            'status': 'Pending',
            'startdate': f"{context.user_data['selected_date']}T{context.user_data['selected_time']}:00Z",
            'enddate': f"{context.user_data['selected_date']}T{int(context.user_data['selected_time'][:2]) + 1:02d}:00:00Z",
            'message': context.user_data['message'],
            'isMembershipUsed': False,
            'userId': user.id  # Store Telegram user ID
        }
        new_class_ref = db.collection('classes').add(class_data)
        # Optionally update user's classes list
        user_ref = db.collection('users').document(str(user.id))
        user_ref.update({'classes': firestore.ArrayUnion([new_class_ref[1].id])})

        update.message.reply_text("Your class was saved. Please wait for the confirmation.")
    except Exception as e:
        update.message.reply_text("There was an error saving your class. Please try again.")
    return ConversationHandler.END

# Define the Conversation Handler
newclass_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(newclass_start, pattern='^NEWCLASS$')],
    states={
        SELECT_DATE: [CallbackQueryHandler(select_date, pattern='^DATE_')],
        SELECT_TIME: [CallbackQueryHandler(select_time, pattern='^TIME_')],
        ENTER_MESSAGE: [MessageHandler(Filters.text & ~Filters.command, enter_message)]
    },
    fallbacks=[CallbackQueryHandler(button_handler, pattern='^CANCEL$')],
)

# Add the NEW CLASS Handler to the Dispatcher
dispatcher.add_handler(newclass_conv_handler)


# Implementing NEWREQUEST Command
# Define Conversation States
ENTER_NAME, ENTER_REQUEST_MESSAGE = range(2)

# Start New Request
def newrequest_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.edit_message_text(text="Please enter your name:")
    return ENTER_NAME

# Handle Name Entry
def enter_name(update: Update, context: CallbackContext):
    name = update.message.text.strip()
    if not name:
        update.message.reply_text("You must enter your name before submitting the request.")
        return ENTER_NAME
    context.user_data['name'] = name
    update.message.reply_text("Please enter any message or type 'skip' to continue:")
    return ENTER_REQUEST_MESSAGE

# Handle Message Entry
def enter_request_message(update: Update, context: CallbackContext):
    message = update.message.text
    if message.lower() != 'skip':
        context.user_data['message'] = message
    else:
        context.user_data['message'] = ''
    # Save the request to Firestore
    user = update.message.from_user
    try:
        request_data = {
            'name': context.user_data['name'],
            'telegram': user.username,
            'email': '',  # If available
            'phone': '',  # If available
            'message': context.user_data['message'],
            'date': datetime.now().isoformat()
        }
        db.collection('requests').add(request_data)
        update.message.reply_text("Your request was saved. Please wait until the tutor contacts you.")
    except Exception as e:
        update.message.reply_text("There was an error saving your request. Please try again.")
    return ConversationHandler.END

# Define the Conversation Handler
newrequest_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(newrequest_start, pattern='^NEWREQUEST$')],
    states={
        ENTER_NAME: [MessageHandler(Filters.text & ~Filters.command, enter_name)],
        ENTER_REQUEST_MESSAGE: [MessageHandler(Filters.text & ~Filters.command, enter_request_message)]
    },
    fallbacks=[CallbackQueryHandler(button_handler, pattern='^CANCEL$')],
)

# Add the NEW REQUEST Handler to the Dispatcher
dispatcher.add_handler(newrequest_conv_handler)


# Implementing CANCELCLASS Command
# Define Conversation States
SELECT_CLASS_TO_CANCEL, CONFIRM_CANCELLATION = range(2)

# Start Class Cancellation
def cancelclass_start(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user = query.from_user
    user_ref = db.collection('users').document(str(user.id))
    user_doc = user_ref.get()
    if user_doc.exists:
        user_data = user_doc.to_dict()
        classes_ids = user_data.get('classes', [])
        if classes_ids:
            # Fetch user's classes
            classes_buttons = []
            for class_id in classes_ids:
                class_doc = db.collection('classes').document(class_id).get()
                if class_doc.exists:
                    class_data = class_doc.to_dict()
                    class_info = f"{class_data['startdate']} | Status: {class_data['status']}"
                    classes_buttons.append(
                        [InlineKeyboardButton(class_info, callback_data=f"CANCEL_{class_id}")]
                    )
            classes_buttons.append([InlineKeyboardButton("Cancel", callback_data='CANCEL')])
            reply_markup = InlineKeyboardMarkup(classes_buttons)
            query.edit_message_text(text="Choose a class you would like to cancel:", reply_markup=reply_markup)
            return SELECT_CLASS_TO_CANCEL
        else:
            query.edit_message_text(text="You don't have any classes signed up for.")
            return ConversationHandler.END
    else:
        query.edit_message_text(text="User data not found.")
        return ConversationHandler.END

# Handle Class Selection
def select_class_to_cancel(update: Update, context: CallbackContext):
    query = update.callback_query
    class_id = query.data.split('_')[1]
    context.user_data['class_id_to_cancel'] = class_id
    class_doc = db.collection('classes').document(class_id).get()
    if class_doc.exists:
        class_data = class_doc.to_dict()
        class_info = f"{class_data['startdate']} | Status: {class_data['status']}"
        query.edit_message_text(
            text=f"Are you sure you want to cancel this class?\n{class_info}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Yes, Cancel", callback_data='CONFIRM_CANCEL')],
                [InlineKeyboardButton("No, Go Back", callback_data='CANCEL')]
            ])
        )
        return CONFIRM_CANCELLATION
    else:
        query.edit_message_text(text="Class not found.")
        return ConversationHandler.END

# Handle Cancellation Confirmation
def confirm_cancellation(update: Update, context: CallbackContext):
    query = update.callback_query
    class_id = context.user_data['class_id_to_cancel']
    user = query.from_user
    try:
        # Remove class from user's classes
        user_ref = db.collection('users').document(str(user.id))
        user_ref.update({'classes': firestore.ArrayRemove([class_id])})
        # Update class status to 'Cancelled' or delete
        class_ref = db.collection('classes').document(class_id)
        class_ref.update({'status': 'Cancelled'})
        query.edit_message_text(text="Your class has been cancelled.")
    except Exception as e:
        query.edit_message_text(text="There was an error cancelling your class. Please try again.")
    return ConversationHandler.END

# Define the Conversation Handler
cancelclass_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(cancelclass_start, pattern='^CANCELCLASS$')],
    states={
        SELECT_CLASS_TO_CANCEL: [CallbackQueryHandler(select_class_to_cancel, pattern='^CANCEL_')],
        CONFIRM_CANCELLATION: [CallbackQueryHandler(confirm_cancellation, pattern='^CONFIRM_CANCEL$')]
    },
    fallbacks=[CallbackQueryHandler(button_handler, pattern='^CANCEL$')],
)

# Add the CANCEL CLASS Handler to the Dispatcher
dispatcher.add_handler(cancelclass_conv_handler)


# Implementing the CANCEL Command
# This command simply restarts the conversation.
def cancel(update: Update, context: CallbackContext):
    update.message.reply_text('Operation cancelled.')
    return ConversationHandler.END


# Starting the Bot
if __name__ == '__main__':
    updater.start_polling()
    updater.idle()


# Error Handling and Logging
# Add Error Handler
def error_handler(update: object, context: CallbackContext):
    """Log the error and send a telegram message to notify the developer."""
    import traceback
    # Log the error
    print(f"Exception while handling an update: {context.error}")
    traceback.print_exc()
    # Notify user
    if isinstance(update, Update) and update.effective_chat:
        context.bot.send_message(chat_id=update.effective_chat.id, text="An unexpected error occurred. Please try again later.")

# Add the ERROR Handler to the Dispatcher
dispatcher.add_error_handler(error_handler)

# Enable Logging
import logging

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
