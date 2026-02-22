# trazen_register.py
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    thread_id = getattr(update.message, "message_thread_id", None)

    message = (
        f"✅ Registration Info\n\n"
        f"Chat ID:\n{chat_id}\n\n"
        f"Thread ID:\n{thread_id}"
    )

    await update.message.reply_text(message)

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("register", register))
    app.run_polling()

if name == "main":
    main()
