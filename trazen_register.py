import json
import os
from telegram import Bot
from telegram.ext import Updater, CommandHandler

# ---------------------------
# Config (from environment variable)
# ---------------------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")  # Set this in PythonAnywhere

# File to store registered chats/topics
SENT_FILE = "sent_updates.json"

# Initialize bot
bot = Bot(token=TELEGRAM_TOKEN)

# Load or initialize sent_updates.json
if os.path.exists(SENT_FILE):
    with open(SENT_FILE, "r") as f:
        data = json.load(f)
else:
    data = {"registered_chats": {}}

# Save JSON helper
def save_data():
    with open(SENT_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ---------------------------
# /register command
# ---------------------------
def register(update, context):
    chat_id = update.effective_chat.id
    thread_id = getattr(update.message, "message_thread_id", None)

    if str(chat_id) in data["registered_chats"]:
        context.bot.send_message(chat_id=chat_id, text="ℹ️ This chat/topic is already registered.")
        return

    data["registered_chats"][str(chat_id)] = {"thread_id": thread_id}
    save_data()

    context.bot.send_message(
        chat_id=chat_id,
        text="✅ This chat has been registered! You can stop the bot now."
    )
    print(f"Registered chat: {chat_id}, thread: {thread_id}")

# ---------------------------
# Main polling loop
# ---------------------------
def main():
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("register", register))
    print("Bot is live. Send /register in your Telegram groups now...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
