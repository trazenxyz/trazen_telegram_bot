# trazen_register.py
import json
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ---------------------------
# Config (from environment variables)
# ---------------------------
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

# File to store registered chats/topics
SENT_FILE = "sent_updates.json"

# Load or initialize sent_updates.json
if os.path.exists(SENT_FILE):
    with open(SENT_FILE, "r") as f:
        data = json.load(f)
else:
    data = {"registered_chats": {}}

# Helper to save JSON data
def save_data():
    with open(SENT_FILE, "w") as f:
        json.dump(data, f, indent=4)

# /register command
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    thread_id = getattr(update.message, "message_thread_id", None)

    key = str(chat_id)
    if key in data["registered_chats"]:
        await update.message.reply_text("ℹ️ This chat/topic is already registered.")
        return

    # Save chat info
    data["registered_chats"][key] = {"thread_id": thread_id}
    save_data()

    await update.message.reply_text(
        "✅ This chat has been registered! Future Trazen updates will be posted here."
    )

# ---------------------------
# Main function
# ---------------------------
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("register", register))
    app.run_polling()  # Bot runs live and listens for /register commands

if __name__ == "__main__":
    main()
