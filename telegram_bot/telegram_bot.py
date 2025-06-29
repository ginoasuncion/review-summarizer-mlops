import os

import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Load environment variables from .env
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN in environment")

API_URL = "https://product-query-api-nxbmt7mfiq-uc.a.run.app/query"


# Telegram command: /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi! I can provide summaries of YouTube"
        " reviews for shoe models. "
        "Please enter the name of the "
        "shoe model you're interested in"
        " (e.g., 'Adidas Ultraboost')."
    )


# Telegram message handler: get summary from API
async def get_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    product_name = update.message.text.strip()
    payload = {"product_name": product_name}

    try:
        response = requests.post(
            API_URL, headers={"Content-Type": "application/json"}, json=payload
        )
        print(f"API Response Status: {response.status_code}")
        print(f"API Response: {response.text}")  # Debug: Print raw response
        if response.status_code == 200:
            data = response.json()
            # Check for summary_content in the data object
            summary_content = None
            if "data" in data and "summary_content" in data["data"]:
                summary_content = data["data"]["summary_content"]
            elif "summary_content" in data:
                summary_content = data["summary_content"]

            if summary_content:
                message = f"Summary for {product_name}:\n\n{summary_content}"
                # Split message if too long (Telegram limit is 4096 characters)
                MAX_MESSAGE_LENGTH = 4096
                while len(message) > MAX_MESSAGE_LENGTH:
                    split_index = message.rfind("\n", 0, MAX_MESSAGE_LENGTH)
                    if split_index == -1:
                        split_index = MAX_MESSAGE_LENGTH
                    await update.message.reply_text(message[:split_index])
                    message = message[split_index:]
                await update.message.reply_text(message)
            else:
                await update.message.reply_text(
                    f"No summary found for '{product_name}'"
                )
        else:
            await update.message.reply_text(
                f"Error fetching summary (Status: {response.status_code})."
            )
    except Exception as e:
        print(f"Error fetching summary: {e}")
        await update.message.reply_text("⚠️ Sorry, I couldn't process your request.")


def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, get_summary))

    print("✅ Bot is running...")
    app.run_polling()


if __name__ == "_main_":
    main()
