# trazen_register.py
import os
import json
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ---------------------------
# Config
# ---------------------------
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
SENT_FILE = "sent_updates.json"

# ---------------------------
# Helper to load/save JSON
# ---------------------------
def load_data():
    if os.path.exists(SENT_FILE):
        with open(SENT_FILE, "r") as f:
            return json.load(f)
    else:
        return {"registered_chats": {}, "sent_ids": []}

def save_data(data):
    with open(SENT_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ---------------------------
# /register command
# ---------------------------
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    chat_id = chat.id
    chat_type = chat.type
    thread_id = getattr(update.message, "message_thread_id", None)

    data = load_data()  # Load existing chats

    if str(chat_id) not in data["registered_chats"]:
        # New chat — save it
        data["registered_chats"][str(chat_id)] = {"thread_id": thread_id}
        save_data(data)
        location = (
            f"Topic thread detected\nThread ID: {thread_id}"
            if thread_id else
            "No topic detected (posts will go to main chat)"
        )

        message = (
            f"✅ This chat has been registered!\n\n"
            f"Chat Type: {chat_type}\n"
            f"Chat ID: {chat_id}\n"
            f"{location}\n\n"
            f"You can now stop this bot; future updates are handled by GitHub Actions."
        )
        await update.message.reply_text(message)
    else:
        # Already registered
        await update.message.reply_text("ℹ️ This chat/topic is already registered.")

# ---------------------------
# Main
# ---------------------------
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("register", register))
    print("Bot started. Waiting for /register commands...")
    app.run_polling()

if __name__ == "__main__":
    main()
