import os

from data_processor_2 import summarize_shoe_review
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome! Send a shoe model name (e.g., Air Jordan 1) to get a "
        "summary of a video review."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    model_name = update.message.text.strip()
    summary = summarize_shoe_review(model_name)
    await update.message.reply_text(summary)


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
