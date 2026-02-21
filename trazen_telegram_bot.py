import os
import json
import requests
from telegram import Bot

# ENV variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TRAZEN_API = os.getenv("TRAZEN_API")
CHAT_ID = os.getenv("CHAT_ID")  # group or channel id

SENT_FILE = "sent_updates.json"


def load_sent():
    try:
        with open(SENT_FILE, "r") as f:
            return json.load(f)
    except:
        return {}


def save_sent(data):
    with open(SENT_FILE, "w") as f:
        json.dump(data, f, indent=2)


def fetch_updates():
    try:
        res = requests.get(TRAZEN_API, timeout=10)
        res.raise_for_status()
        return res.json().get("updates", [])
    except:
        return []


def format_message(item):
    title = item.get("title", "Opportunity")
    link = item.get("link", "")
    type_ = item.get("type", "Opportunity")
    reward = item.get("reward")

    msg = f"🚀 New opportunity on Trazen!\n\n"
    msg += f"📌 Type: {type_}\n"
    msg += f"📝 {title}\n"

    if reward:
        msg += f"💰 Reward: {reward}\n"

    msg += f"\n🔗 Apply now: {link}"

    return msg


def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    sent = load_sent()
    updates = fetch_updates()

    updated = False

    for item in updates:
        uid = str(item.get("id"))

        if uid in sent:
            continue

        message = format_message(item)

        try:
            bot.send_message(chat_id=CHAT_ID, text=message)
            sent[uid] = True
            updated = True
        except Exception as e:
            print("Send error:", e)

    if updated:
        save_sent(sent)


if __name__ == "__main__":
    main()
