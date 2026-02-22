import os
import json
import requests
from telegram import Bot
from telegram.ext import Updater, CommandHandler

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TRAZEN_API = os.environ["TRAZEN_API"]
SENT_FILE = "sent_updates.json"
MAX_PER_CHAT = 2

bot = Bot(token=TELEGRAM_TOKEN)

# Load or initialize sent_updates.json
if os.path.exists(SENT_FILE):
    with open(SENT_FILE, "r") as f:
        data = json.load(f)
else:
    data = {"registered_chats": {}, "sent_ids": []}

def save_data():
    with open(SENT_FILE, "w") as f:
        json.dump(data, f, indent=4)

def fetch_opportunities():
    try:
        response = requests.get(TRAZEN_API)
        response.raise_for_status()
        return response.json()
    except:
        return []

# /register command
def register(update, context):
    chat_id = update.effective_chat.id
    thread_id = getattr(update.message, "message_thread_id", None)

    if "registered_chats" not in data:
        data["registered_chats"] = {}
    if "sent_ids" not in data:
        data["sent_ids"] = []

    if str(chat_id) in data["registered_chats"]:
        update.message.reply_text("ℹ️ Already registered.")
        return

    data["registered_chats"][str(chat_id)] = {"thread_id": thread_id}
    save_data()
    update.message.reply_text("✅ Registered successfully!")

# Send updates to registered chats
def send_updates():
    opportunities = fetch_opportunities()
    for chat_key, chat_info in data.get("registered_chats", {}).items():
        messages_sent = 0
        for opp in opportunities:
            opp_id = opp.get("id")
            if opp_id in data["sent_ids"]:
                continue
            if messages_sent >= MAX_PER_CHAT:
                break
            text = f"🚀 New opportunity available!\n\n{opp.get('title')}\n{opp.get('link')}"
            try:
                bot.send_message(chat_id=chat_key, text=text, message_thread_id=chat_info.get("thread_id"))
                messages_sent += 1
                data["sent_ids"].append(opp_id)
            except Exception as e:
                print("Send failed:", e)
    save_data()

# Entry point for live /register
def run_polling():
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("register", register))
    updater.start_polling()
    updater.idle()

# Detect if running locally for /register, otherwise just send updates
if __name__ == "__main__":
    if os.environ.get("MODE") == "POLLING":
        run_polling()
    else:
        send_updates()
