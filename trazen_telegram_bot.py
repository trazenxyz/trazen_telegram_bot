import os
import json
import logging
import requests
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ---------------- CONFIG ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TRAZEN_API = os.getenv("TRAZEN_API", "https://api.trazen.xyz/latest-updates")
DB_FILE = "registered_chats.json"

# Logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ---------------- HELPER FUNCTIONS ----------------
def load_registered_chats():
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_registered_chats(chats_dict):
    with open(DB_FILE, "w") as f:
        json.dump(chats_dict, indent=4)

def fetch_trazen_updates():
    """Fetch updates from Trazen API"""
    try:
        resp = requests.get(TRAZEN_API, timeout=10)
        resp.raise_for_status()
        return resp.json().get("updates", [])
    except Exception as e:
        logging.error(f"Error fetching Trazen updates: {e}")
        return []

def format_message(update_item):
    """Polished message format for any opportunity type"""
    title = update_item.get("title", "No Title")
    link = update_item.get("link", "#")
    reward = update_item.get("reward")
    deadline = update_item.get("deadline")
    type_ = update_item.get("type", "Opportunity")

    message = f"🚀 New opportunity on Trazen!\n📌 Type: {type_}\n📝 Title: {title}"
    if reward:
        message += f"\n💰 Reward: {reward}"
    if deadline:
        message += f"\n📅 Deadline: {deadline}"
    message += f"\n🔗 Apply: {link}\n\nDon't miss out — check it out now!"
    return message

# ---------------- COMMAND HANDLERS ----------------
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Register chat/topic automatically"""
    chat_id = str(update.effective_chat.id)
    thread_id = update.message.message_thread_id  # None if not in topic
    chat_name = update.effective_chat.title or update.effective_chat.username

    all_chats = load_registered_chats()
    key = f"{chat_id}:{thread_id}" if thread_id else chat_id

    if key in all_chats:
        await update.message.reply_text(f"Already registered: {chat_name}")
    else:
        all_chats[key] = {"chat_id": chat_id, "thread_id": thread_id, "name": chat_name}
        save_registered_chats(all_chats)
        await update.message.reply_text(f"Registered successfully: {chat_name}")

async def unregister(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove chat/topic from registration"""
    chat_id = str(update.effective_chat.id)
    thread_id = update.message.message_thread_id
    key = f"{chat_id}:{thread_id}" if thread_id else chat_id

    all_chats = load_registered_chats()
    if key in all_chats:
        del all_chats[key]
        save_registered_chats(all_chats)
        await update.message.reply_text("Unregistered successfully.")
    else:
        await update.message.reply_text("This chat/topic is not registered.")

# ---------------- CRON-FRIENDLY UPDATE SENDER ----------------
def send_updates():
    """Send Trazen updates to all registered chats/topics"""
    bot = Bot(token=TELEGRAM_TOKEN)
    updates = fetch_trazen_updates()
    if not updates:
        logging.info("No new updates.")
        return

    all_chats = load_registered_chats()
    for key, chat_info in all_chats.items():
        chat_id = chat_info["chat_id"]
        thread_id = chat_info.get("thread_id")
        for update_item in updates:
            try:
                if thread_id:
                    bot.send_message(
                        chat_id=int(chat_id),
                        text=format_message(update_item),
                        message_thread_id=int(thread_id)
                    )
                else:
                    bot.send_message(
                        chat_id=int(chat_id),
                        text=format_message(update_item)
                    )
            except Exception as e:
                logging.error(f"Failed to send to {chat_id}: {e}")

# ---------------- MAIN ----------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "send":
        # Cron mode: send updates only
        logging.info("Cron mode: sending Trazen updates...")
        send_updates()
        logging.info("Done sending updates. Exiting.")
    else:
        # Start interactive bot for registration commands
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        app.add_handler(CommandHandler("register", register))
        app.add_handler(CommandHandler("unregister", unregister))
        logging.info("Trazen Registration Bot running...")
        app.run_polling()
