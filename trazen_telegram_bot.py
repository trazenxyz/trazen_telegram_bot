import json
import requests
import os
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# ---------------------------
# Config (from GitHub Secrets)
# ---------------------------
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TRAZEN_API = os.environ["TRAZEN_API"]

# File to store registered chats/topics and sent updates
SENT_FILE = "sent_updates.json"

# Max messages per chat per run (prevents spam)
MAX_PER_CHAT = 2

# ---------------------------
# Initialize bot
# ---------------------------
bot = Bot(token=TELEGRAM_TOKEN)

# Load or initialize sent_updates.json
if os.path.exists(SENT_FILE):
    with open(SENT_FILE, "r") as f:
        data = json.load(f)
else:
    data = {"registered_chats": {}, "sent_ids": []}


# ---------------------------
# Helper to save JSON data
# ---------------------------
def save_data():
    with open(SENT_FILE, "w") as f:
        json.dump(data, f, indent=4)


# ---------------------------
# Fetch new opportunities from Trazen API
# ---------------------------
def fetch_opportunities():
    try:
        response = requests.get(TRAZEN_API)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print("Error fetching Trazen API:", e)
        return []


# ---------------------------
# /register command
# ---------------------------
def register(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    thread_id = getattr(update.message, "message_thread_id", None)

    if "registered_chats" not in data:
        data["registered_chats"] = {}
    if "sent_ids" not in data:
        data["sent_ids"] = []

    if str(chat_id) not in data["registered_chats"]:
        # Save the chat info
        data["registered_chats"][str(chat_id)] = {"thread_id": thread_id}
        save_data()

        # Send confirmation message
        context.bot.send_message(
            chat_id=chat_id,
            text="✅ This chat has been registered! Future Trazen updates will be posted here."
        )

        # Immediately send the latest opportunities (up to MAX_PER_CHAT)
        opportunities = fetch_opportunities()
        messages_sent = 0
        for opp in opportunities:
            opp_id = opp.get("id")
            if opp_id in data["sent_ids"]:
                continue
            if messages_sent >= MAX_PER_CHAT:
                break
            text = f"🚀 New opportunity available!\n\n{opp.get('title')}\n{opp.get('link')}"
            try:
                bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    message_thread_id=thread_id
                )
                messages_sent += 1
            except Exception as e:
                print("Failed to send to chat:", e)
            data["sent_ids"].append(opp_id)
        save_data()
    else:
        # Chat already registered
        context.bot.send_message(
            chat_id=chat_id,
            text="ℹ️ This chat/topic is already registered."
        )


# ---------------------------
# Send updates to all registered chats (with per-chat limits)
# ---------------------------
def send_updates():
    opportunities = fetch_opportunities()
    for chat_key, chat_info in data["registered_chats"].items():
        messages_sent = 0
        for opp in opportunities:
            opp_id = opp.get("id")
            if opp_id in data["sent_ids"]:
                continue
            if messages_sent >= MAX_PER_CHAT:
                break

            text = f"🚀 New opportunity available!\n\n{opp.get('title')}\n{opp.get('link')}"
            try:
                bot.send_message(
                    chat_id=int(chat_key),
                    text=text,
                    message_thread_id=chat_info.get("thread_id")
                )
                messages_sent += 1
            except Exception as e:
                print(f"Failed to send to chat {chat_key}:", e)

            # Mark this opportunity as sent globally
            data["sent_ids"].append(opp_id)

    save_data()


# ---------------------------
# Optional local polling for testing
# ---------------------------
def main():
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("register", register))
    updater.start_polling()
    updater.idle()


# ---------------------------
# Entry point for GitHub Actions (scheduled runs)
# ---------------------------
if __name__ == "__main__":
    send_updates()
