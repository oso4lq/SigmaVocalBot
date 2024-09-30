## Sigma The Vocal Place Telegram Bot

*Version 0.9*

Sigma The Vocal Place Telegram Bot is a versatile tool designed to streamline class management for both students and tutors/admins. Integrated with Firestore Database, the bot facilitates class bookings, cancellations, and schedule management through an intuitive interface using both inline keyboard buttons and direct commands.

**Commands:** START, NEWCLASS, CANCELCLASS, NEWREQUEST, SCHEDULE, CANCEL.

## Features
- **Class Management:** Students can book new classes or cancel existing ones.
- **Membership Integration:** Handles membership points, ensuring proper refunds and deductions based on cancellation policy.
- **Admin Schedule Control:** Tutor/Administrator can view, edit, and delete classes from their schedule.
- **Dual Interaction Modes:** Supports both inline keyboard buttons and direct text commands for enhanced user experience.
- **Real-Time Updates:** Automatically refreshes user interfaces to reflect the latest class schedules and statuses.
- **Robust Error Handling:** Provides clear feedback in case of errors, ensuring smooth interactions.

### START
Starts the bot.
- Greeting,
- Checks if the user's Telegram username exists in the Firestore Database,
- **Existing User:**
- - Fetches and displays the user's current classes and presents options to *Create a New Class* (/newclass or button) or *Cancel an Existing Class* (/cancelclass or button),
- - Provides an option to *Vview the Schedule* (/schedule or button) - *available only to admins*,
- **New User:**
- - Provides an option to *Leave a Request for the First Class* (/newrequest or button),

### NEWCLASS
Allows existing users to book a new class.
- **Select Date:** Presents the next 7 available weekdays as selectable buttons (excluding weekends).
- **Select Time Slot:** Displays available time slots for the chosen date, excluding already occupied slots. Prevents booking of past time slots.
- **Optional Message:** Offers the option to add an additional message or skip.
- **Confirmation:** Saves the class details to Firestore. Updates the user's class list and membership points accordingly.
- **Feedback:** Notifies the user of the booking status (success or error).
- **Auto-Reload:** Automatically restarts the /start command to display the updated class list.

### CANCELCLASS
Enables existing users to cancel a previously booked class.
- **Class Selection:** Lists all classes the user is enrolled in as selectable buttons.
- **Refund Policy Validation:** Checks membership points and class status to determine refund eligibility.
- **Confirmation:** Asks the user to confirm the cancellation.
- **Update Database:** Removes the selected class from Firestore. Adjusts membership points based on the refund policy.
- **Feedback:** Notifies the user of the cancellation status (success or error).
- **Auto-Reload:** Automatically restarts the /start command to display the updated class list.

### NEWREQUEST
Allows new users to request enrollment for their first class.
- **Enter Name:** Prompts the user to provide their full name.
- **Optional Message:** Offers the option to add an additional message or skip.
- **Save Request:** Stores the request details in Firestore.
- **Feedback:** Informs the user of the request status (success or error).

### SCHEDULE
Allows administrators to view and manage their class schedules.
- **View Schedule:** Displays the schedule for the selected day (defaults to today).
- **Navigate Dates:** Provides buttons to switch between previous and next days, refreshing the schedule accordingly.
- **Manage Classes:** Edit Status: Change the status of a class (e.g., from "Pending" to "Confirmed"). 
- **Delete Class:** Remove a class from the schedule.
- **Persistent Interaction:** Continues to allow schedule management without ending the conversation unless the admin chooses to cancel.

### CANCEL
Aborts the current operation or conversation.
- **Abort Current Task:** Stops any ongoing conversation or process.
- **Reset Commands:** Reverts available commands to /start.
- **Feedback:** Informs the user that the operation has been canceled.