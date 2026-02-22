import os
import json
import subprocess
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# ---------------------------
# Config (from GitHub Secrets / Environment Variables)
# ---------------------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO")  # e.g., "username/trazen_telegram_bot"
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")

SENT_FILE = "sent_updates.json"

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
# Helper to save JSON
# ---------------------------
def save_data():
    with open(SENT_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ---------------------------
# Push changes to GitHub
# ---------------------------
def push_to_github():
    try:
        subprocess.run(["git", "add", SENT_FILE], check=True)
        subprocess.run(["git", "commit", "-m", "Update registered chats"], check=True)
        subprocess.run(["git", "push", "origin", GITHUB_BRANCH], check=True)
        print("✅ Updated sent_updates.json pushed to GitHub")
    except subprocess.CalledProcessError as e:
        print("❌ Git push failed:", e)

# ---------------------------
# /register command
# ---------------------------
def register(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    thread_id = getattr(update.message, "message_thread_id", None)

    if str(chat_id) in data["registered_chats"]:
        update.message.reply_text("ℹ️ This chat/topic is already registered.")
        return

    data["registered_chats"][str(chat_id)] = {"thread_id": thread_id}
    save_data()
    update.message.reply_text("✅ This chat has been registered! Future Trazen updates will be posted here.")

    # Push updated JSON to GitHub automatically
    push_to_github()

# ---------------------------
# Main polling
# ---------------------------
def main():
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("register", register))
    print("Bot is live for /register. Press Ctrl+C to stop after registration is done.")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
