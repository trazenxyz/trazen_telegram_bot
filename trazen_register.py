import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    chat_id = chat.id
    chat_type = chat.type  # private, group, supergroup, channel

    thread_id = getattr(update.message, "message_thread_id", None)

    # Detect topic usage
    if thread_id:
        location = f"Topic thread detected\nThread ID: {thread_id}"
    else:
        location = "No topic detected (posts will go to main chat)"

    message = (
        f"✅ Registration Info\n\n"
        f"Chat Type: {chat_type}\n"
        f"Chat ID:\n{chat_id}\n\n"
        f"{location}"
    )

    await update.message.reply_text(message)

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("register", register))
    app.run_polling()

if name == "main":
    main()
