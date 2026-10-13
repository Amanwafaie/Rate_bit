import os
import httpx
from telegram.ext import ApplicationBuilder, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

async def fetch_and_post(context: ContextTypes.DEFAULT_TYPE):
    try:
        text = "📊 آخرین نرخ ارزها از د افغانستان بانک"
        await context.bot.send_message(chat_id=CHANNEL_ID, text=text)
    except Exception as e:
        print(f"Error: {e}")

def main():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN is missing!")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    if app.job_queue:
        app.job_queue.run_repeating(fetch_and_post, interval=7200, first=10)

    app.run_polling()

if __name__ == "__main__":
    main()
