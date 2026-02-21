import json
import requests
import os
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# Load secrets from environment (set in GitHub Actions)
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TRAZEN_API = os.environ["TRAZEN_API"]

# File to store registered chats and sent updates
SENT_FILE = "sent_updates.json"

# Initialize bot
bot = Bot(token=TELEGRAM_TOKEN)

# Load sent updates and registered chats
if os.path.exists(SENT_FILE):
    with open(SENT_FILE, "r") as f:
        data = json.load(f)
else:
    data = {"registered_chats": {}, "sent_ids": []}

# Save data helper
def save_data():
    with open(SENT_FILE, "w") as f:
        json.dump(data, f, indent=4)

# /register command
def register(update: Update, context: CallbackContext):
    chat = update.effective_chat
    chat_id = chat.id
    thread_id = getattr(update.message, "message_thread_id", None)

    key = f"{chat_id}:{thread_id}" if thread_id else str(chat_id)
    if key not in data["registered_chats"]:
        data["registered_chats"][key] = {"chat_id": chat_id, "thread_id": thread_id}
        save_data()
        update.message.reply_text(
            f"✅ This chat/topic has been registered for Trazen updates!"
        )
    else:
        update.message.reply_text("ℹ️ This chat/topic is already registered.")

# Fetch new opportunities from Trazen API
def fetch_opportunities():
    try:
        response = requests.get(TRAZEN_API)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print("Error fetching Trazen API:", e)
        return []

# Send updates to all registered chats
def send_updates():
    opportunities = fetch_opportunities()
    for opp in opportunities:
        opp_id = opp.get("id")  # Each opportunity should have a unique ID
        if opp_id in data["sent_ids"]:
            continue  # Skip already sent
        text = f"🚀 New opportunity available!\n\n{opp.get('title')}\n{opp.get('link')}"
        for chat_info in data["registered_chats"].values():
            try:
                bot.send_message(
                    chat_id=chat_info["chat_id"],
                    text=text,
                    message_thread_id=chat_info.get("thread_id")
                )
            except Exception as e:
                print("Failed to send to chat:", e)
        data["sent_ids"].append(opp_id)
    save_data()

# Telegram command handling
def main():
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("register", register))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    # If run as a script via GitHub Actions, just send updates once
    send_updates()
