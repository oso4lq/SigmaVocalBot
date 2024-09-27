# This module will handle all interactions with Firestore, such as
# fetching user data, classes, adding new classes, and handling requests.

# Initialization: The initialize_firebase function initializes the Firebase Admin SDK. 

# User Operations: Functions like get_user_by_telegram_username fetch user data based on the Telegram username.
# Class Operations: Functions to fetch classes, add new classes, and update class statuses.
# Request Operations: Function to add new user requests.

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from typing import Optional, List, Dict, Any

# Initialize Firebase Admin SDK (Ensure this is called once)
def initialize_firebase(service_account_key_path: str) -> firestore.client:
    if not firebase_admin._apps:
        cred = credentials.Certificate(service_account_key_path)
        firebase_admin.initialize_app(cred)
    return firestore.client()

# Fetch user data by Telegram username
def get_user_by_telegram_username(db: firestore.client, telegram_username: str) -> Optional[Dict[str, Any]]:
    users_ref = db.collection('users')
    query = users_ref.where('telegram', '==', telegram_username).stream()
    user_docs = list(query)
    if user_docs:
        user_doc = user_docs[0]
        user_data = user_doc.to_dict()
        user_data['id'] = user_doc.id  # Include the document ID
        return user_data
    return None

# Fetch classes by class IDs
def get_classes_by_ids(db: firestore.client, class_ids: List[str]) -> List[Dict[str, Any]]:
    classes = []
    for class_id in class_ids:
        class_doc = db.collection('classes').document(str(class_id)).get()
        if class_doc.exists:

            # classes.append(class_doc.to_dict())

            class_data = class_doc.to_dict()
            class_data['id'] = class_doc.id  # Ensure the class ID is included
            classes.append(class_data)
            
    return classes

# Fetch occupied time slots for a specific date
def get_occupied_time_slots(db: firestore.client, selected_date: str) -> List[str]:
    occupied_slots = []
    classes_ref = db.collection('classes')
    start_datetime = f"{selected_date}T00:00:00"
    end_datetime = f"{selected_date}T23:59:59"
    booked_classes = classes_ref.where('startdate', '>=', start_datetime).where('startdate', '<=', end_datetime).stream()
    for class_doc in booked_classes:
        class_data = class_doc.to_dict()
        time = class_data['startdate'].split('T')[1][:5]
        occupied_slots.append(time)
    return occupied_slots

# Add a new class
def add_new_class(db: firestore.client, class_data: Dict[str, Any]) -> Optional[str]:
    try:
        new_class_ref = db.collection('classes').document()  # Create a new document reference with auto-generated ID
        class_data['id'] = new_class_ref.id  # Set the 'id' field in class_data
        new_class_ref.set(class_data)
        return new_class_ref.id  # Return the document ID
    except Exception as e:
        print(f"Error adding new class: {e}")
        return None

# Delete a class
def delete_class(db: firestore.client, class_id: str) -> bool:
    try:
        class_ref = db.collection('classes').document(class_id)
        class_ref.delete()
        return True
    except Exception as e:
        print(f"Error deleting class: {e}")
        return False
    
# Update user's classes list
def update_user_classes(db: firestore.client, user_id: str, class_id: str) -> bool:
    try:
        user_ref = db.collection('users').document(user_id)
        user_ref.update({'classes': firestore.ArrayUnion([class_id])})
        return True
    except Exception as e:
        print(f"Error updating user classes: {e}")
        return False

# Add a new request
def add_new_request(db: firestore.client, request_data: Dict[str, Any]) -> bool:
    try:
        db.collection('requests').add(request_data)
        return True
    except Exception as e:
        print(f"Error adding new request: {e}")
        return False

# Remove a class from user's classes list
def remove_user_class(db: firestore.client, user_id: str, class_id: str) -> bool:
    try:
        user_ref = db.collection('users').document(user_id)
        user_ref.update({'classes': firestore.ArrayRemove([class_id])})
        return True
    except Exception as e:
        print(f"Error removing class from user: {e}")
        return False

# Update class status
def update_class_status(db: firestore.client, class_id: str, status: str) -> bool:
    try:
        class_ref = db.collection('classes').document(class_id)
        class_ref.update({'status': status})
        return True
    except Exception as e:
        print(f"Error updating class status: {e}")
        return False
