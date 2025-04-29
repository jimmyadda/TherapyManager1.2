from flask import session
import vonage
import random
import time

from package.database import DatabaseManager



client = vonage.Client(key="f1638e9e", secret="olEAxDDpMnlrOf0W")
sms = vonage.Sms(client)

def send_verification_code(phone_number):
    # Generate a 6-digit random code
    verification_code = str(random.randint(1000, 9999))
    timestamp = time.time()  # Current time in seconds

    # Store the verification code and timestamp in SQLite
    client_key = session['client_key']
    db_manager = DatabaseManager(client_key)
    conn = db_manager.connect_to_db(client_key)
    cursor = conn.cursor()
    
    # Insert or replace the code for the phone number (updating if it already exists)
    cursor.execute("""
    REPLACE INTO verification_codes (phone_number, code, timestamp)
    VALUES (?, ?, ?)
    """, (phone_number, verification_code, timestamp))
    
    conn.commit()
    conn.close()
    
    # Send the verification code via SMS using Nexmo
    responseData = sms.send_message({
        "from": "TherapyManager",
        "to": phone_number,
        "text": f"Your verification code is: {verification_code} it will be valis for the next 5 Minutes",
    })    
    
    # Check if the message was sent successfully
    if responseData["messages"][0]["status"] == "0":
        print(f"Message sent to {phone_number} successfully.")
    else:
        print(f"Message failed with error: {responseData['messages'][0]['error-text']}")

def verify_code(phone_number, entered_code):
    # Retrieve the stored code and timestamp from SQLite
    client_key = session['client_key']
    db_manager = DatabaseManager(client_key)
    conn = db_manager.connect_to_db(client_key)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT code, timestamp FROM verification_codes WHERE phone_number = ?
    """, (phone_number,))
    
    result = cursor.fetchone()
    conn.close()

    print(result)
    if result:
        stored_code = result['code']
        code_timestamp = result['timestamp']

        # Check if the code has expired (5 minutes expiration)
        if time.time() - code_timestamp > 300:  # 5 minutes = 300 seconds
            print("Verification code has expired.")
            return False

        # Compare the stored code with the entered code
        if entered_code == stored_code:
            print("Verification successful.")
            return True
        else:
            print("Incorrect code.")
            return False
    else:
        print("No verification code found for this phone number.")
        return False

# Example of sending a verification code
# phone_number = "972528774804"  # Replace with user's phone number
# send_verification_code(phone_number)