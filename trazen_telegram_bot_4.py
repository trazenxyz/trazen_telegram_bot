
import os
import logging
import asyncio
import sqlite3
import datetime
import json
import httpx # For making async HTTP requests
from typing import Optional, Dict, Any

from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ChatMemberHandler, JobQueue

from fastapi import FastAPI, Request, HTTPException
import uvicorn

# --- Configuration --- #
DATABASE_NAME = 'bot_data.db'
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TRAZEN_API_URL = os.getenv("TRAZEN_API_URL", "https://api.trazen.com/opportunities") # Default API URL
FETCH_INTERVAL_MINUTES = int(os.getenv("FETCH_INTERVAL_MINUTES", 20)) # How often to fetch new opportunities

# --- Logging Setup --- #
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

# --- Database Manager Class (Integrated) --- #
class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_NAME, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        self.cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS telegram_chats (
                chat_id TEXT PRIMARY KEY,
                chat_type TEXT NOT NULL,
                chat_title TEXT,
                message_thread_id INTEGER,
                added_at TEXT NOT NULL,
                is_active INTEGER NOT NULL
            )
            '''
        )
        self.cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS sent_messages (
                opportunity_id TEXT NOT NULL,
                chat_id TEXT NOT NULL,
                message_thread_id INTEGER NOT NULL,
                sent_at TEXT NOT NULL,
                PRIMARY KEY (opportunity_id, chat_id, message_thread_id)
            )
            '''
        )
        self.cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            '''
        )
        self.conn.commit()

    def add_or_update_chat(self, chat_id, chat_type, chat_title, message_thread_id=None, is_active=1):
        added_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.cursor.execute(
            '''
            INSERT INTO telegram_chats (chat_id, chat_type, chat_title, message_thread_id, added_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                chat_type = excluded.chat_type,
                chat_title = excluded.chat_title,
                message_thread_id = excluded.message_thread_id,
                is_active = excluded.is_active
            ''',
            (chat_id, chat_type, chat_title, message_thread_id, added_at, is_active)
        )
        self.conn.commit()

    def get_active_chats(self):
        self.cursor.execute(
            'SELECT chat_id, chat_type, chat_title, message_thread_id FROM telegram_chats WHERE is_active = 1'
        )
        return self.cursor.fetchall()

    def get_chat_count(self):
        self.cursor.execute(
            'SELECT COUNT(*) FROM telegram_chats WHERE is_active = 1'
        )
        return self.cursor.fetchone()[0]

    def set_chat_active_status(self, chat_id, is_active):
        self.cursor.execute(
            'UPDATE telegram_chats SET is_active = ? WHERE chat_id = ?',
            (is_active, chat_id)
        )
        self.conn.commit()

    def is_message_sent(self, opportunity_id, chat_id, message_thread_id=0):
        self.cursor.execute(
            'SELECT 1 FROM sent_messages WHERE opportunity_id = ? AND chat_id = ? AND message_thread_id = ?',
            (opportunity_id, chat_id, message_thread_id)
        )
        return self.cursor.fetchone() is not None

    def mark_message_sent(self, opportunity_id, chat_id, message_thread_id=0):
        sent_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.cursor.execute(
            '''
            INSERT OR IGNORE INTO sent_messages (opportunity_id, chat_id, message_thread_id, sent_at)
            VALUES (?, ?, ?, ?)
            ''',
            (opportunity_id, chat_id, message_thread_id, sent_at)
        )
        self.conn.commit()

    def get_setting(self, key, default=None):
        self.cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        result = self.cursor.fetchone()
        return result[0] if result else default

    def set_setting(self, key, value):
        self.cursor.execute(
            '''
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            ''',
            (key, value)
        )
        self.conn.commit()

    def close(self):
        self.conn.close()

# --- Global Instances --- #
db = DatabaseManager()
app = FastAPI()
telegram_app: Optional[Application] = None
telegram_bot_instance: Optional[Bot] = None
job_queue_instance: Optional[JobQueue] = None

# --- Telegram Bot Handlers --- #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message on /start and captures chat info."""
    chat_id = str(update.effective_chat.id)
    chat_type = update.effective_chat.type
    chat_title = update.effective_chat.title if update.effective_chat.title else "Private Chat"
    message_thread_id = update.effective_message.message_thread_id if update.effective_message and update.effective_message.message_thread_id else None

    db.add_or_update_chat(chat_id, chat_type, chat_title, message_thread_id, is_active=1)
    logger.info(f"[DEBUG] /start command received. Captured chat: {chat_title} ({chat_id}), Type: {chat_type}, Topic ID: {message_thread_id}")

    await update.message.reply_text(
        f"Hello! I've captured this chat's ID ({chat_id}). "
        f"Type: {chat_type}. "
        f"Topic ID: {message_thread_id if message_thread_id else 'N/A'}.\n"
        "I will now automatically send messages here when instructed."
    )

async def handle_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles when the bot is added to a new group/channel."""
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            chat_id = str(update.effective_chat.id)
            chat_type = update.effective_chat.type
            chat_title = update.effective_chat.title if update.effective_chat.title else "Unknown Chat Title"
            message_thread_id = update.effective_message.message_thread_id if update.effective_message and update.effective_message.message_thread_id else None

            db.add_or_update_chat(chat_id, chat_type, chat_title, message_thread_id, is_active=1)
            logger.info(f"[DEBUG] Bot added to new chat: {chat_title} ({chat_id}), Type: {chat_type}, Topic ID: {message_thread_id}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"Hello everyone! I've been added to this chat ({chat_id}). "
                     f"Type: {chat_type}. "
                     f"Topic ID: {message_thread_id if message_thread_id else 'N/A'}.\n"
                     "I will now automatically send messages here when instructed.",
                message_thread_id=message_thread_id
            )

async def handle_left_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles when the bot is removed from a group/channel."""
    if update.my_chat_member.old_chat_member.status == 'member' and \
       update.my_chat_member.new_chat_member.status == 'left':
        chat_id = str(update.effective_chat.id)
        db.set_chat_active_status(chat_id, 0)
        logger.info(f"[DEBUG] Bot removed from chat: {update.effective_chat.title} ({chat_id})")

async def broadcast_message(bot: Bot, opportunity_id: str, message_text: str) -> list:
    """Sends a given message to all active chats and topics, avoiding duplicates."""
    active_chats = db.get_active_chats()
    sent_to = []

    for chat_id, chat_type, chat_title, message_thread_id in active_chats:
        # Use 0 for message_thread_id if it's None, for consistent DB lookup
        thread_id_for_db = message_thread_id if message_thread_id is not None else 0

        if not db.is_message_sent(opportunity_id, chat_id, thread_id_for_db):
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=message_text,
                    message_thread_id=message_thread_id, # Pass actual None if no topic
                    parse_mode='Markdown'
                )
                db.mark_message_sent(opportunity_id, chat_id, thread_id_for_db)
                sent_to.append(f"{chat_title} ({chat_id}) - Topic: {message_thread_id if message_thread_id else 'N/A'}")
                logger.info(f"[DEBUG] Message '{opportunity_id}' sent to {chat_title} ({chat_id}) - Topic: {message_thread_id}")
            except Exception as e:
                logger.error(f"[ERROR] Failed to send message '{opportunity_id}' to {chat_title} ({chat_id}) - Topic: {message_thread_id}: {e}")
        else:
            logger.info(f"[DEBUG] Message '{opportunity_id}' already sent to {chat_title} ({chat_id}) - Topic: {message_thread_id}. Skipping.")
    return sent_to

async def send_test_message_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Command to send a test message to all registered chats."""
    if not update.effective_chat.type == 'private':
        await update.message.reply_text("This command can only be used in a private chat with the bot.")
        return

    args = context.args
    if not args:
        await update.message.reply_text("Usage: /sendtest <opportunity_id> <Your test message>")
        return

    opportunity_id = args[0]
    test_message = " ".join(args[1:])

    if not test_message:
        await update.message.reply_text("Please provide a test message.")
        return

    await update.message.reply_text(f"Attempting to broadcast message '{opportunity_id}'...")
    sent_list = await broadcast_message(context.bot, opportunity_id, test_message)

    if sent_list:
        await update.message.reply_text("Message broadcasted successfully to:\n" + "\n".join(sent_list))
    else:
        await update.message.reply_text("No active chats found or message already sent to all.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends bot status information."""
    active_chat_count = db.get_chat_count()
    last_fetch_timestamp = db.get_setting("last_fetch_timestamp", "Never fetched")
    current_time = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    status_text = (
        f"*Bot Status:*\n"
        f"*Active Chats*: {active_chat_count}\n"
        f"*Last API Fetch*: {last_fetch_timestamp}\n"
        f"*Current Server Time*: {current_time}\n"
        f"*Fetch Interval*: {FETCH_INTERVAL_MINUTES} minutes\n"
    )
    await update.message.reply_text(status_text, parse_mode='Markdown')
    logger.info(f"[DEBUG] /status command executed. Active chats: {active_chat_count}, Last fetch: {last_fetch_timestamp}")

# --- Trazen API Polling Function --- #
async def fetch_and_broadcast_opportunities(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetches new opportunities from Trazen API and broadcasts them."""
    global telegram_bot_instance
    if not telegram_bot_instance:
        logger.error("Telegram bot instance not initialized for polling. Skipping fetch.")
        return

    last_fetch_timestamp_str = db.get_setting("last_fetch_timestamp", "2000-01-01T00:00:00Z")
    logger.info(f"[POLLING] Fetching opportunities since: {last_fetch_timestamp_str}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(TRAZEN_API_URL, params={"since": last_fetch_timestamp_str})
            response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
            opportunities = response.json()

        if not opportunities:
            logger.info("[POLLING] No new opportunities found.")
            return

        logger.info(f"[POLLING] Found {len(opportunities)} new opportunities.")
        new_last_fetch_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        for opportunity in opportunities:
            opportunity_id = opportunity.get("id")
            opportunity_type = opportunity.get("type", "Opportunity")
            opportunity_title = opportunity.get("title")
            opportunity_description = opportunity.get("description", "No description provided.")
            opportunity_url = opportunity.get("url")
            opportunity_created_at = opportunity.get("created_at", datetime.datetime.now(datetime.timezone.utc).isoformat())

            if not all([opportunity_id, opportunity_title, opportunity_url]):
                logger.warning(f"[POLLING] Skipping opportunity due to missing fields: {opportunity}")
                continue

            message_text = (
                f"*New Trazen Opportunity!*\n\n"
                f"*Type*: {opportunity_type}\n"
                f"*Title*: {opportunity_title}\n"
                f"*Description*: {opportunity_description}\n"
                f"*Link*: {opportunity_url}\n"
                f"*Posted At*: {opportunity_created_at}\n"
            )

            await broadcast_message(telegram_bot_instance, opportunity_id, message_text)

        db.set_setting("last_fetch_timestamp", new_last_fetch_timestamp)
        logger.info(f"[POLLING] Updated last_fetch_timestamp to: {new_last_fetch_timestamp}")

    except httpx.HTTPStatusError as e:
        logger.error(f"[POLLING] HTTP error fetching opportunities: {e.response.status_code} - {e.response.text}")
    except httpx.RequestError as e:
        logger.error(f"[POLLING] Network error fetching opportunities: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"[POLLING] JSON decode error from API response: {e}")
    except Exception as e:
        logger.exception(f"[POLLING] An unexpected error occurred during opportunity fetch: {e}")

# --- FastAPI Webhook Endpoint (Retained for flexibility) --- #
@app.post("/webhook")
async def handle_webhook(request: Request):
    """Receives opportunity data via webhook and broadcasts it."""
    global telegram_bot_instance
    if not telegram_bot_instance:
        logger.error("Telegram bot instance not initialized for webhook. This should not happen with unified startup.")
        raise HTTPException(status_code=500, detail="Telegram bot not ready. Please check bot logs.")

    try:
        payload = await request.json()
        logger.info(f"[DEBUG] Received webhook payload: {payload}")

        opportunity_id = payload.get("id")
        opportunity_type = payload.get("type", "Opportunity")
        opportunity_title = payload.get("title")
        opportunity_description = payload.get("description", "No description provided.")
        opportunity_url = payload.get("url")
        opportunity_created_at = payload.get("created_at", datetime.datetime.now(datetime.timezone.utc).isoformat())

        if not all([opportunity_id, opportunity_title, opportunity_url]):
            raise ValueError("Missing required opportunity fields (id, title, url) in payload.")

        message_text = (
            f"*New Trazen Opportunity!*\n\n"
            f"*Type*: {opportunity_type}\n"
            f"*Title*: {opportunity_title}\n"
            f"*Description*: {opportunity_description}\n"
            f"*Link*: {opportunity_url}\n"
            f"*Posted At*: {opportunity_created_at}\n"
        )

        sent_list = await broadcast_message(telegram_bot_instance, opportunity_id, message_text)

        if sent_list:
            logger.info(f"[DEBUG] Webhook broadcast successful for '{opportunity_id}' to: {', '.join(sent_list)}")
            return {"status": "success", "message": "Broadcast initiated", "sent_to": sent_list}
        else:
            logger.info(f"[DEBUG] Webhook broadcast for '{opportunity_id}': No active chats or already sent.")
            return {"status": "success", "message": "No active chats or already sent."}

    except Exception as e:
        logger.error(f"[ERROR] Error processing webhook: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# --- Unified Application Startup --- #
async def run_bot_and_server():
    """Initializes Telegram bot, JobQueue, and FastAPI server."""
    global telegram_app, telegram_bot_instance, job_queue_instance

    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set.")
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set.")

    # 1. Initialize Telegram Application and Bot Instance
    telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    telegram_bot_instance = telegram_app.bot
    job_queue_instance = telegram_app.job_queue

    # 2. Add Handlers
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("sendtest", send_test_message_command))
    telegram_app.add_handler(CommandHandler("status", status_command)) # New status command
    telegram_app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_chat_members))
    telegram_app.add_handler(ChatMemberHandler(handle_left_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))

    # 3. Schedule the API Polling Job
    job_queue_instance.run_repeating(fetch_and_broadcast_opportunities, interval=FETCH_INTERVAL_MINUTES * 60, first=10) # Start 10 seconds after launch
    logger.info(f"Scheduled opportunity fetch every {FETCH_INTERVAL_MINUTES} minutes.")

    # 4. Start Telegram Polling in the background
    # This will run indefinitely and handle Telegram updates
    polling_task = asyncio.create_task(telegram_app.run_polling(allowed_updates=Update.ALL_TYPES))
    logger.info("Telegram Bot polling started as background task.")

    # 5. Start FastAPI server
    # This will block until the server is stopped, but polling runs in background
    config = uvicorn.Config(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)), log_level="info")
    server = uvicorn.Server(config)
    logger.info(f"Starting Uvicorn server for FastAPI on http://0.0.0.0:{int(os.getenv('PORT', 8000))}")
    await server.serve()

    # Ensure polling task is awaited if server stops
    await polling_task

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("FastAPI shutdown event triggered. Stopping Telegram polling and closing DB...")
    if telegram_app:
        await telegram_app.shutdown()
    db.close()
    logger.info("Telegram polling stopped and DB closed.")

# Main entry point for Render
if __name__ == "__main__":
    try:
        asyncio.run(run_bot_and_server())
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        logger.exception("An unhandled error occurred in the main application loop.")
