import os
import json
import logging
import requests
from telegram import Bot

# ---------------- CONFIG ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TRAZEN_API = os.getenv("TRAZEN_API")

DB_FILE = "registered_chats.json"
SENT_FILE = "sent_updates.json"

logging.basicConfig(level=logging.INFO)

# ---------------- STORAGE ----------------
def load_json(file):
    try:
        with open(file, "r") as f:
            return json.load(f)
    except:
        return {}

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

# ---------------- FETCH ----------------
def fetch_trazen_updates():
    try:
        response = requests.get(TRAZEN_API, timeout=10)
        response.raise_for_status()
        return response.json().get("updates", [])
    except Exception as e:
        logging.error(f"Error fetching updates: {e}")
        return []

# ---------------- FORMAT ----------------
def format_message(update_item):
    title = update_item.get("title", "No Title")
    link = update_item.get("link", "#")
    reward = update_item.get("reward")
    deadline = update_item.get("deadline")
    type_ = update_item.get("type", "Opportunity")

    message = f"🚀 New opportunity on Trazen!\n\n"
    message += f"📌 Type: {type_}\n"
    message += f"📝 {title}\n"

    if reward:
        message += f"💰 Reward: {reward}\n"

    if deadline:
        message += f"📅 Deadline: {deadline}\n"

    message += f"\n🔗 Apply now: {link}\n\n"
    message += "Don’t miss out."

    return message

# ---------------- SEND ----------------
def send_updates():
    bot = Bot(token=TELEGRAM_TOKEN)

    chats = load_json(DB_FILE)
    sent_updates = load_json(SENT_FILE)

    updates = fetch_trazen_updates()

    if not updates:
        logging.info("No updates found.")
        return

    for update_item in updates:
        update_id = str(update_item.get("id"))

        if update_id in sent_updates:
            continue  # skip already sent

        message = format_message(update_item)

        for key, chat_info in chats.items():
            chat_id = chat_info["chat_id"]
            thread_id = chat_info.get("thread_id")

            try:
                if thread_id:
                    bot.send_message(
                        chat_id=int(chat_id),
                        text=message,
                        message_thread_id=int(thread_id)
                    )
                else:
                    bot.send_message(
                        chat_id=int(chat_id),
                        text=message
                    )
            except Exception as e:
                logging.error(f"Failed sending to {chat_id}: {e}")

        sent_updates[update_id] = True

    save_json(SENT_FILE, sent_updates)
    logging.info("Finished sending updates.")

# ---------------- RUN ----------------
if __name__ == "__main__":
    send_updates()

  
