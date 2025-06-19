import os

from dotenv import load_dotenv
from openai import OpenAI
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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_BOT_TOKEN or not OPENAI_API_KEY:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN or OPENAI_API_KEY in environment")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


# Telegram command: /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hello! Ask me anything — I'm powered by ChatGPT!"
    )


# Telegram message handler: chat with ChatGPT
async def chatgpt_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_message},
            ],
        )
        bot_reply = response.choices[0].message.content
        await update.message.reply_text(bot_reply)

    except Exception as e:
        print("Error from OpenAI:", e)
        await update.message.reply_text("⚠️ Sorry, I couldn't process your request.")


def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chatgpt_reply))

    print("✅ Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
