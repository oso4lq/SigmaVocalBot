## Sigma The Vocal Place Telegram Bot

**v0.1**
Communicates with the Firestore Database.
Commands: START, NEWCLASS, CANCELCLASS, NEWREQUEST, CANCEL.

**START**
Starts the bot.
- Greeting,
- Check if the user's Telegram username is in the DB,
- If so, fetch the user's Classes and suggest editing (CANCELCLASS) or signing up for a new class (NEWCLASS),
- If not, suggest sending a new request to sign up for the first class (NEWREQUEST).

**NEWCLASS**
Allows an existing user to sign up for a new class.
- Display 5 options for the next 7 days (excluding weekends) as buttons,
- Display time slots for the selected day (excluding occupied) as buttons,
- Suggest leaving an optional message,
- Update the Classes object in the Firestore Database,
- Notify the user of the request status (success/error),
- Reload START to see the updated class list.

**CANCELCLASS**
Allows an existing user to cancel an existing class. 
- Check if the user has classes,
- Display the user's classes as buttons,
- Ask if the user is sure about canceling the selected class,
- Update the Classes object in the Firestore Database to delete the selected class,
- Notify the user of the request status (success/error),
- Reload START to see the updated class list.

**NEWREQUEST**
Allows a new user to sign up for a first class.
- Get the user's Telegram full name and username,
- Suggest leaving an optional message,
- Update the Requests object in the Firestore Database,
- Notify the user of the request status (success/error),
- Reload START.

**CANCEL**
Aborts the current command and reloads the bot.


Done in Frontend, not done in Bot:
- Refund policy validation (membership),
- Edit status function for admin.