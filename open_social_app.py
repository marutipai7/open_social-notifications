# import requests
# from bs4 import BeautifulSoup
# import threading
# import logging
# import time
# import os
# import re
# from datetime import datetime, timedelta    
# from flask import Flask, request, jsonify
# from dotenv import load_dotenv
# import mysql.connector

# # Load environment variables
# load_dotenv()

# # Logging configuration
# logging.basicConfig(
#     filename="open_social_notifications.log",
#     level=logger.info,
#     format="%(asctime)s - %(levelname)s - %(message)s",
#     filemode="a",
# )

# app = Flask(__name__)

# # Environment Variables
# OPEN_SOCIAL_BASE_URL = os.getenv("OPEN_SOCIAL_SITE")
# LARAVEL_NOTIFICATION_API = os.getenv("LARAVEL_NOTIFICATION_API")
# APP_NAME = os.getenv("APP_NAME")

# LOGIN_URL = f"{OPEN_SOCIAL_BASE_URL}/action/user/login"
# HOME_URL = f"{OPEN_SOCIAL_BASE_URL}/home"
# NOTIFICATIONS_URL = f"{OPEN_SOCIAL_BASE_URL}/notification/notification"

# # MySQL Database Connection
# def get_db_connection():
#     return mysql.connector.connect(
#         host=os.getenv("DB_HOST", "localhost"),
#         user="root",
#         password=os.getenv("DB_PASSWORD", "root"),
#         database=os.getenv("DB_NAME", "my_apps"),
#         unix_socket="/var/run/mysqld/mysqld.sock"
#     )

# def create_table():
#     connection = get_db_connection()
#     cursor = connection.cursor()
#     try:
#         cursor.execute("""
#             CREATE TABLE IF NOT EXISTS open_social_login_logout (
#                 username VARCHAR(255) PRIMARY KEY,
#                 login BOOLEAN NOT NULL,
#                 login_timestamp TIMESTAMP NOT NULL,
#                 last_fetched_timestamp TIMESTAMP
#             );
#         """)
#         connection.commit()
#     except mysql.connector.Error as err:
#         logger.error(f"Error creating table: {err.msg}")
#     finally:
#         cursor.close()
#         connection.close()

# def ensure_table_exists():
#     create_table()

# def update_login_status(username, status, last_fetched_timestamp=None):
#     connection = get_db_connection()
#     cursor = connection.cursor()
#     if status == "login":
#         cursor.execute("""
#             INSERT INTO open_social_login_logout (username, login, login_timestamp, last_fetched_timestamp)
#             VALUES (%s, TRUE, NOW(), %s)
#             ON DUPLICATE KEY UPDATE login=TRUE, login_timestamp=NOW(), last_fetched_timestamp=%s;
#         """, (username, last_fetched_timestamp, last_fetched_timestamp))
#     elif status == "logout":
#         cursor.execute("""
#             DELETE FROM open_social_login_logout WHERE username=%s;
#         """, (username,))
#     connection.commit()
#     cursor.close()
#     connection.close()

# def get_last_fetched_timestamp(username):
#     connection = get_db_connection()
#     cursor = connection.cursor()
#     cursor.execute("""
#         SELECT last_fetched_timestamp FROM open_social_login_logout WHERE username=%s;
#     """, (username,))
#     result = cursor.fetchone()
#     cursor.close()
#     connection.close()
#     return result[0] if result else None

# def is_user_logged_in(username):
#     connection = get_db_connection()
#     cursor = connection.cursor()
#     cursor.execute("""
#         SELECT login FROM open_social_login_logout WHERE username=%s;
#     """, (username,))
#     result = cursor.fetchone()
#     cursor.close()
#     connection.close()
#     return result and result[0]

# def login_to_open_social(username, password):
#     try:
#         session = requests.Session()
#         login_page = session.get(HOME_URL)
#         if login_page.status_code == 200:
#             soup = BeautifulSoup(login_page.text, 'html.parser')
#             ossn_ts = soup.find('input', {'name': 'ossn_ts'})['value']
#             ossn_token = soup.find('input', {'name': 'ossn_token'})['value']
#             login_payload = {
#                 "ossn_ts": ossn_ts,
#                 "ossn_token": ossn_token,
#                 "username": username,
#                 "password": password
#             }
#             headers = {"Referer": HOME_URL}
#             response = session.post(LOGIN_URL, data=login_payload, headers=headers)
#             if response.status_code == 200 and "News Feed" in response.text:
#                 logger.info(f"Login successful for {username}")
#                 return session
#             else:
#                 logger.error(f"Login failed for {username}. Response: {response.text}")
#                 return None
#         else:
#             logger.error("Failed to fetch login page.")
#             return None
#     except Exception as e:
#         logger.error(f"Error logging in {username}: {e}")
#         return None


# def parse_notifications(html_content, last_fetched_timestamp):
#     soup = BeautifulSoup(html_content, 'html.parser')
#     notifications = []

#     for notif in soup.select('.ossn-notifications-all li'):
#         sender = notif.select_one('.data strong').text.strip()
#         message = notif.select_one('.data').text.replace(sender, "").strip()

#         # Extract the relative time from the message
#         time_ago_match = re.search(r'(\d+)\s*(minutes?|hours?|seconds?|days?)\s*ago', message)
#         if time_ago_match:
#             quantity = int(time_ago_match.group(1))
#             unit = time_ago_match.group(2)

#             if unit.startswith('minute'):
#                 delta = timedelta(minutes=quantity)
#             elif unit.startswith('hour'):
#                 delta = timedelta(hours=quantity)
#             elif unit.startswith('second'):
#                 delta = timedelta(seconds=quantity)
#             elif unit.startswith('day'):
#                 delta = timedelta(days=quantity)
#             else:
#                 delta = timedelta(minutes=0)  # Default to no difference if unit is not recognized

#             timestamp = datetime.now() - delta
#         else:
#             # Extract the date from the title attribute if no relative time is found
#             date_str = notif.select_one('.time-created')['title']
#             date = datetime.strptime(date_str, '%d/%m/%Y')
#             timestamp = date.replace(hour=0, minute=0, second=0)

#         if last_fetched_timestamp is None or timestamp > last_fetched_timestamp:
#             notifications.append({"sender": sender, "message": message, "timestamp": timestamp})

#     return notifications

# def fetch_notifications(username, session):
#     logger.info(f"Started notification fetching thread for {username}")

#     while is_user_logged_in(username):
#         try:
#             headers = {"Referer": HOME_URL}
#             notifications_response = session.get(NOTIFICATIONS_URL, headers=headers)

#             if notifications_response.status_code == 200:
#                 notifications_json = notifications_response.json()
#                 html_content = notifications_json.get("data", "")

#                 last_fetched_timestamp = get_last_fetched_timestamp(username)
#                 notifications = parse_notifications(html_content, last_fetched_timestamp)

#                 if notifications:
#                     # Sort notifications by timestamp
#                     notifications.sort(key=lambda x: x["timestamp"], reverse=True)

#                     # Update the last fetched timestamp in the database
#                     latest_timestamp = notifications[0]["timestamp"]
#                     update_login_status(username, "login", last_fetched_timestamp=latest_timestamp)

#                     for notification in notifications:
#                         notification_data = {
#                             "app": APP_NAME,
#                             "username": username,
#                             "subject": f"{notification['sender']} {notification['message']}",
#                             # "timestamp": notification["timestamp"].strftime('%Y-%m-%d %H:%M:%S'),
#                             "timestamp": notification["timestamp"].strftime('%d/%m/%Y'),
#                         }
#                         notification_data["subject"] = ' '.join(notification_data["subject"].split())

#                         logger.info(f"Sending notification to Laravel: {notification_data}")
#                         send_notification_to_laravel(notification_data)
#                 else:
#                     logger.info(f"No new notifications found after {last_fetched_timestamp} for {username}.")

#             else:
#                 logger.error(f"Failed to fetch notifications for {username}. Response: {notifications_response.text}")

#         except Exception as e:
#             logger.error(f"Error fetching notifications for {username}: {e}")

#         logger.info("Sleeping for 60 seconds, will fetch the notifications afterwards.")
#         time.sleep(60)

#     logger.info(f"Stopped notifications thread for user {username}.")



# def send_notification_to_laravel(notification):
#     try:
#         response = requests.post(LARAVEL_NOTIFICATION_API, json=notification)
#         if response.status_code == 200:
#             logger.info(f"Notification sent successfully: {notification}")
#         else:
#             logger.error(f"Failed to send notification: {response.status_code}, {response.text}")
#     except Exception as e:
#         logger.exception(f"Error sending notification: {str(e)}")

# @app.route('/')
# def home():
#     return 'Hello from Open Social notifications app!'

# @app.route('/open_social_login_info', methods=['POST'])
# def user_login():
#     data = request.get_json()
#     username = data.get("email")
#     password = data.get("password")
#     if not username or not password:
#         logging.warning("Login request missing username or password")
#         return jsonify({"error": "Missing username or password"}), 400
#     ensure_table_exists()
#     if is_user_logged_in(username):
#         logger.info(f"User {username} already logged in.")
#         return jsonify({"message": f"User {username} already logged in and receiving notifications"}), 200
#     session = login_to_open_social(username, password)
#     if session:
#         update_login_status(username, "login")
#         # Add a small delay to ensure the login status update is visible
#         time.sleep(1)
#         thread = threading.Thread(target=fetch_notifications, args=(username, session), daemon=True)
#         thread.start()
#         return jsonify({"message": f"User {username} logged in and started fetching notifications"}), 200
#     else:
#         return jsonify({"error": "Login failed"}), 401

# @app.route('/open_social_logout_info', methods=['POST'])
# def user_logout():
#     data = request.get_json()
#     username = data.get("email")
#     if not username:
#         logging.warning("Logout request missing username")
#         return jsonify({"error": "Missing username"}), 400
#     ensure_table_exists()
#     if is_user_logged_in(username):
#         logger.info(f"User {username} logged out.")
#         update_login_status(username, "logout")
#         return jsonify({"message": "User logged out"}), 200
#     else:
#         return jsonify({"message": "User not logged in"}), 200

# if __name__ == "__main__":
#     logger.info("Starting Flask server on port 9002")
#     app.run(host="0.0.0.0", port=9002, debug=True)
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger(__name__)


import threading
import time
from collections import defaultdict

from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import requests

# -----------------------------------
# CONFIG
# -----------------------------------

# -----------------------------------
# AUTO USERS (HARDCODED)
# -----------------------------------
# AUTO_HUMHUB_USERS = {
#     "humhub": {
#         "username": "humhub",
#         "password": "Humhub@2025"
#     }
# }

HUMHUB_URL = "https://zulip.sizaf.com:5055"
import os
from dotenv import load_dotenv

load_dotenv()

LARAVEL_NOTIFICATION_API = os.getenv("LARAVEL_NOTIFICATION_API")


POLL_INTERVAL = 2  # seconds

# -----------------------------------
# FLASK APP
# -----------------------------------
app = Flask(__name__)

# -----------------------------------
# GLOBAL STATE (same idea as OpenSocial)
# -----------------------------------
LOGIN_STATE = {}              # username -> True/False
USER_THREADS = {}             # username -> Thread
NOTIFICATION_STORE = defaultdict(list)   # username -> notifications
SEEN_KEYS = defaultdict(set) # username -> deduplication

# -----------------------------------
# PLAYWRIGHT: FETCH HTML (UNCHANGED LOGIC)
# -----------------------------------

# def start_auto_humhub_workers():
#     """
#     Starts humhub_worker automatically for predefined users
#     """
#     for key, creds in AUTO_HUMHUB_USERS.items():
#         username = creds["username"]
#         password = creds["password"]

#         if LOGIN_STATE.get(username):
#             continue  # already running

#         LOGIN_STATE[username] = True

#         t = threading.Thread(
#             target=humhub_worker,
#             args=(username, password),
#             daemon=True
#         )
#         USER_THREADS[username] = t
#         t.start()

#         print(f"[AUTO] HumHub worker started for {username}")

def auto_fetch_notifications(username, interval=30):
    while LOGIN_STATE.get(username):
        notifications = fetch_all_notifications(username)
        print(f"[AUTO FETCH] {len(notifications)} notifications for {username}")
        time.sleep(interval)

    print(f"[AUTO FETCH] stopped for {username}")



def fetch_dashboard_html(username, password):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # 1️⃣ Login page
        page.goto(f"{HUMHUB_URL}/user/auth/login", timeout=60000)

        # 2️⃣ Login
        page.fill('input[name="Login[username]"]', username)
        page.fill('input[name="Login[password]"]', password)
        page.click('button[type="submit"]')

        # 3️⃣ Wait for dashboard
        page.wait_for_url("**/dashboard**", timeout=15000)
        time.sleep(1)  # Let the initial notifications load

        # 4️⃣ Scroll up loop to load all notifications
        # You need to find the correct scroll container selector
        # Example selector - replace with your actual container selector for notifications
        scroll_container_selector = "div.notifications-container"  

        previous_height = 0
        same_height_count = 0

        while True:
            try:
                container = page.query_selector(scroll_container_selector)
                if not container:
                    print("[ERROR] Notifications container not found")
                    break

                # Scroll to top inside the container
                page.evaluate(f"""
                    () => {{
                        const container = document.querySelector('{scroll_container_selector}');
                        container.scrollTop = 0;
                    }}
                """)

                time.sleep(2)  # wait for more notifications to load

                # Check scrollHeight to see if it has increased (more content loaded)
                current_height = page.evaluate(f"""
                    () => document.querySelector('{scroll_container_selector}').scrollHeight
                """)

                if current_height == previous_height:
                    same_height_count += 1
                else:
                    same_height_count = 0

                if same_height_count >= 3:  # no height increase after 3 attempts → all loaded
                    print("[DEBUG] All notifications loaded")
                    break

                previous_height = current_height

            except Exception as e:
                print(f"[ERROR] During scrolling: {e}")
                break

        # 5️⃣ Get final fully loaded HTML
        html = page.content()
        browser.close()
        return html





import mysql.connector

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="my_apps",
        autocommit=True
    )

def save_notification(username, sender, message, event_time):
    conn = get_db()
    cur = conn.cursor()

    normalized_msg = normalize_message(message)

    sql = """
    INSERT INTO humhub_notifications
        (username, sender, message, event_time)
    VALUES (%s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        id = id
    """

    cur.execute(sql, (username, sender, normalized_msg, event_time))
    conn.commit()

    send_notification_to_laravel(
    username=username,
    sender=sender,
    message=normalized_msg,
    event_time=event_time
)

    cur.close()
    conn.close()



# @app.route("/api/humhub/notifications", methods=["GET"])
# def get_humhub_notifications():
#     username = request.args.get("username")
#     limit = int(request.args.get("limit", 50))

#     if not username:
#         return jsonify({"error": "username is required"}), 400

#     username = username.strip()

#     db = get_db()
#     cur = db.cursor(dictionary=True)

#     cur.execute("""
#     SELECT
#         sender,
#         message,
#         event_time
#     FROM humhub_notifications
#     WHERE username = %s
#     GROUP BY sender, message, event_time
#     ORDER BY event_time DESC
# """, (username,))


#     rows = cur.fetchall()

#     cur.close()
#     db.close()

#     return jsonify({
#         "username": username,
#         "count": len(rows),
#         "notifications": rows
#     })

from flask import Response
import json
@app.route("/api/humhub/notifications", methods=["GET"])
def get_humhub_notifications():
    username = request.args.get("username")
    limit = int(request.args.get("limit", 50))

    if not username:
        return jsonify({"error": "username is required"}), 400

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT sender, message, event_time
        FROM humhub_notifications
        WHERE username = %s
        ORDER BY event_time DESC
        LIMIT %s
    """, (username, limit))

    rows = cur.fetchall()
    cur.close()
    db.close()

    response = {
        "username": username,
        "count": len(rows),
        "notifications": rows
    }

    return Response(
        json.dumps(response, indent=2, default=str),
        mimetype="application/json"
    )


# -----------------------------------
# PARSE NOTIFICATIONS (UNCHANGED LOGIC)
# -----------------------------------
# def parse_notifications(html):
#     soup = BeautifulSoup(html, "html.parser")
#     notifications = []

#     for div in soup.select("div.flex-grow-1.text-break"):
#         sender = div.find("strong")
#         time_tag = div.find("time")

#         if not sender or not time_tag:
#             continue

#         sender_name = sender.text.strip()
#         full_text = div.get_text(" ", strip=True)
#         message = full_text.replace(sender_name, "").strip()

#         timestamp = time_tag.get("datetime")

#         notifications.append({
#             "sender": sender_name,
#             "message": message,
#             "timestamp": timestamp
#         })

#     return notifications
import re

def clean_message(msg):
    # Remove HumHub relative time phrases
    patterns = [
        r"\s+less than a minute ago$",
        r"\s+\d+\s+minutes ago$",
        r"\s+\d+\s+hours ago$",
        r"\s+\d+\s+days ago$"
    ]

    for p in patterns:
        msg = re.sub(p, "", msg, flags=re.IGNORECASE)

    return msg.strip()


# def parse_notifications(html):
#     soup = BeautifulSoup(html, "html.parser")
#     notifications = []

#     for div in soup.select("div.flex-grow-1.text-break"):
#         sender = div.find("strong")
#         time_tag = div.find("time")

#         if not sender or not time_tag:
#             continue

#         sender_name = sender.text.strip()
#         full_text = div.get_text(" ", strip=True)

#         # Remove sender name
#         message = full_text.replace(sender_name, "").strip()

#         # Keep only text before first dot
#         if "." in message:
#             message = message.split(".", 1)[0]

#         # Convert quotes
#         message = message.replace('"', "'")

#         message = message.strip()


#         timestamp = time_tag.get("datetime")

#         notifications.append({
#             "sender": sender_name,
#             "message": message,
#             "timestamp": timestamp
#         })

#     return notifications
def parse_notifications(html):
    soup = BeautifulSoup(html, "html.parser")
    notifications = []

    for div in soup.select("div.flex-grow-1.text-break"):
        sender = div.find("strong")
        time_tag = div.find("time")

        if not sender or not time_tag:
            continue

        sender_name = sender.text.strip()
        full_text = div.get_text(" ", strip=True)

        # 1️⃣ Remove sender name
        message = full_text.replace(sender_name, "").strip()

        # 2️⃣ Remove HumHub relative time (CRITICAL FIX)
        message = clean_message(message)

        # 3️⃣ Keep text only before first dot
        if "." in message:
            message = message.split(".", 1)[0] + "."

        # 4️⃣ Convert quotes
        message = message.replace('"', "'").strip()

        timestamp = time_tag.get("datetime")

        notifications.append({
            "sender": sender_name,
            "message": message,
            "timestamp": timestamp
        })

    return notifications


# -----------------------------------
# WORKER THREAD (matches previous workflow)
# -----------------------------------
from datetime import datetime, timezone

def time_ago(iso_ts):
    ts = datetime.fromisoformat(iso_ts)
    now = datetime.now(ts.tzinfo)

    delta = now - ts
    seconds = int(delta.total_seconds())

    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        return f"{seconds // 60} minutes ago"
    elif seconds < 86400:
        return f"{seconds // 3600} hours ago"
    else:
        return f"{seconds // 86400} days ago"




# def humhub_worker(username, password):
#     print(f"[WORKER] Started for {username}")

#     while LOGIN_STATE.get(username):

#         try:
#             html = fetch_dashboard_html(username, password)
#             notifications = parse_notifications(html)

#             for n in notifications:
#                 key = f"{username}|{n['timestamp']}"

#                 if key in SEEN_KEYS[username]:
#                     continue

#                 NOTIFICATION_STORE[username].append(n)
#                 SEEN_KEYS[username].add(key)

#                 print("[NEW]", n)

#         except Exception as e:
#             print("[ERROR]", e)

#         time.sleep(POLL_INTERVAL)

#     print(f"[WORKER] Stopped for {username}")

def normalize_message(msg):
    # Remove relative-time phrases (FULLY)
    msg = re.sub(
        r"\s+(less than a minute ago|about an hour ago|about|"
        r"\d+\s+minutes ago|\d+\s+hours ago|\d+\s+days ago|"
        r"a\s+minute ago|an\s+hour ago|a\s+day ago|a\s+week ago)$",
        "",
        msg,
        flags=re.IGNORECASE
    )

    # Normalize joined-space notifications
    if msg.lower().startswith("joined the space"):
        parts = msg.split("joined the space", 1)
        if len(parts) == 2:
            space_name = parts[1].strip()
            msg = f"joined the space {space_name}"

    # Normalize quotes
    msg = msg.replace('"', "'")

    # Normalize punctuation & whitespace
    msg = msg.strip()
    msg = re.sub(r"\s+", " ", msg)
    msg = msg.rstrip(".")

    return msg

def send_notification_to_laravel(username, sender, message, event_time):
    payload = {
        "app": "Open_Social",
        "username": username,        # 🔥 dynamic, NOT hardcoded
        "sender": sender,
        "content": message,
        "event_time": (
            event_time.isoformat()
            if hasattr(event_time, "isoformat")
            else str(event_time)
        )
    }

    try:
        r = requests.post(LARAVEL_NOTIFICATION_API, json=payload, timeout=5)
        print(f"Laravel response [{username}]:", r.status_code, r.text)
    except Exception as e:
        print(f"Laravel send failed [{username}]:", e)




def fetch_all_notifications(username):
    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT sender, message, event_time
        FROM humhub_notifications
        WHERE username = %s
        ORDER BY event_time DESC
    """, (username,))

    rows = cur.fetchall()
    cur.close()
    db.close()

    return rows

def send_all_notifications_to_laravel(username):
    # Connect to DB, fetch notifications for username
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT sender, message, event_time
        FROM humhub_notifications
        WHERE username = %s
        ORDER BY event_time DESC
    """, (username,))
    notifications = cur.fetchall()
    cur.close()
    conn.close()

    for sender, message, event_time in notifications:
        notification = {
            "app": "Open_Social",
            "username": username,
            "sender": sender,
            "content": message,
            "event_time": str(event_time)
        }
        try:
            response = requests.post(LARAVEL_NOTIFICATION_API, json=notification)
            if response.status_code == 200:
                print(f"Sent: {notification}")
            else:
                print(f"Failed to send: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Error sending notification: {e}")

            
from flask import request, jsonify
import logging

@app.route("/sync/humhub/laravel", methods=["POST"])
def sync_humhub_laravel():
    try:
        data = request.get_json()
        username = data.get("username")
        if not username:
            return jsonify({"error": "username is required"}), 400

        # Call your function to send notifications here
        send_all_notifications_to_laravel(username)

        return jsonify({"status": "success"}), 200
    except Exception as e:
        logging.exception("Error in /sync/humhub/laravel")
        return jsonify({"error": str(e)}), 500




# def humhub_worker(username, password):
#     print(f"[WORKER] Started for {username}")
    

#     while LOGIN_STATE.get(username):
#         try:
#             html = fetch_dashboard_html(username, password)
#             notifications = parse_notifications(html)

#             for n in notifications:
#                 normalized_msg = normalize_message(n["message"])
#                 key = f"{username}|{n['timestamp']}|{normalized_msg}"

#                 if key in SEEN_KEYS[username]:
#                     continue

#                 event_time = datetime.fromisoformat(n["timestamp"])

#                 save_notification(
#                     username=username,
#                     sender=n["sender"],
#                     message=normalized_msg,
#                     event_time=event_time
#                 )

#                 send_notification_to_laravel(
#                     username,
#                     n["sender"],
#                     normalized_msg,
#                     event_time
#                 )

#                 NOTIFICATION_STORE[username].append(n)
#                 SEEN_KEYS[username].add(key)

#         except Exception as e:
#             print(f"[ERROR] Worker error for {username}:", e)

#         time.sleep(POLL_INTERVAL)
    

#     print(f"[WORKER] Stopped for {username}")


def humhub_worker(username, password):
    print(f"[WORKER] Started for {username}")

    USER_NOTIFICATIONS.setdefault(username, [])
    SEEN_KEYS.setdefault(username, set())

    while LOGIN_STATE.get(username):
        try:
            html = fetch_dashboard_html(username, password)
            notifications = parse_notifications(html)

            for n in notifications:
                normalized_msg = normalize_message(n["message"])
                key = f"{username}|{n['timestamp']}|{normalized_msg}"

                if key in SEEN_KEYS[username]:
                    continue

                event_time = datetime.fromisoformat(n["timestamp"])

                # Save to DB
                save_notification(
                    username=username,
                    sender=n["sender"],
                    message=normalized_msg,
                    event_time=event_time
                )

                # Send to Laravel
                send_notification_to_laravel(
                    username,
                    n["sender"],
                    normalized_msg,
                    event_time
                )

                # ✅ THIS is what feeds your GET API
                USER_NOTIFICATIONS[username].append({
                    "sender": n["sender"],
                    "message": normalized_msg,
                    "time": n["timestamp"]
                })

                SEEN_KEYS[username].add(key)

        except Exception as e:
            print(f"[ERROR] Worker error for {username}:", e)

        time.sleep(POLL_INTERVAL)

    print(f"[WORKER] Stopped for {username}")


# -----------------------------------
# ROUTES
# -----------------------------------
@app.route("/")
def home():
    response = {}

    for username, notes in NOTIFICATION_STORE.items():
        response[username] = [
            {
                **n,
                "time_ago": time_ago(n["timestamp"])
            }
            for n in notes
        ]

    return jsonify(response)


# @app.route("/humhub_login", methods=["POST"])
# def humhub_login():
#     data = request.get_json()
#     username = data.get("email")
#     password = data.get("password")

#     if not username or not password:
#         return jsonify({"error": "Missing email or password"}), 400

#     if LOGIN_STATE.get(username):
#         return jsonify({"message": "User already logged in"}), 200

#     LOGIN_STATE[username] = True

#     t = threading.Thread(
#         target=humhub_worker,
#         args=(username, password),
#         daemon=True
#     )
#     USER_THREADS[username] = t
#     t.start()

#     return jsonify({"message": "HumHub login started"}), 200

# @app.route("/humhub_login_info", methods=["POST"])
# def humhub_login_info():
#     data = request.form.to_dict()

#     print("RECEIVED DATA:", data)

#     username = data.get("email")
#     password = data.get("password")

#     if not username or not password:
#         return jsonify({
#             "error": "Missing username or password",
#             "received": data
#         }), 400

#     if LOGIN_STATE.get(username):
#         return jsonify({
#             "message": f"User {username} already logged in"
#         }), 200

#     LOGIN_STATE[username] = True

#     t = threading.Thread(
#         target=humhub_worker,
#         args=(username, password),
#         daemon=True
#     )
#     USER_THREADS[username] = t
#     t.start()

#     return jsonify({
#         "message": f"User {username} logged in and worker started"
#     }), 200

USER_NOTIFICATIONS = {}  # {email: [msg1, msg2]}

def humhub_fetch_once(username, password):
    try:
        html = fetch_dashboard_html(username, password)
        notifications = parse_notifications(html)

        result = []
        for n in notifications:
            result.append({
                "sender": n["sender"],
                "message": normalize_message(n["message"]),
                "timestamp": n["timestamp"]
            })

        return result
    except Exception as e:
        print("Initial fetch error:", e)
        return []


@app.route("/humhub_login_info", methods=["POST"])
def humhub_login_info():

    data = request.form if request.form else request.get_json(silent=True) or {}

    username = data.get("email")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Missing username or password"}), 400

    # 🔁 ALWAYS fetch notifications
    notifications = humhub_fetch_once(username, password)

    # 🔹 If already logged in → don't start worker again
    if LOGIN_STATE.get(username):
        return jsonify({
            "message": "Already logged in",
            "notifications": notifications
        }), 200

    # 🔹 First-time login
    LOGIN_STATE[username] = True
    USER_NOTIFICATIONS.setdefault(username, [])

    t = threading.Thread(
        target=humhub_worker,
        args=(username, password),
        daemon=True
    )
    USER_THREADS[username] = t
    t.start()

    return jsonify({
        "message": "Login successful",
        "notifications": notifications
    }), 200




@app.route("/humhub_logout", methods=["POST"])
def humhub_logout():
    data = request.get_json()
    username = data.get("email")

    if not username:
        return jsonify({"error": "Missing email"}), 400

    LOGIN_STATE[username] = False
    return jsonify({"message": "HumHub logout successful"}), 200

# -----------------------------------
# MAIN
# -----------------------------------
if __name__ == "__main__":
    print("🚀 Starting HumHub Notification Server on port 9002")
    app.run(host="0.0.0.0", port=9002, debug=False, threaded=True)


