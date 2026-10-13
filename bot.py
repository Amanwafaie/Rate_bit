import os
import threading
from flask import Flask
from telegram.ext import ApplicationBuilder, ContextTypes

# ساخت وب سرور ساده برای پاسخ به Render
app_express = Flask(__name__)

@app_express.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app_express.run(host="0.0.0.0", port=port)

# اطلاعات ربات
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

async def fetch_and_post(context: ContextTypes.DEFAULT_TYPE):
    try:
        text = "📊 آخرین نرخ ارزها از د افغانستان بانک"
        await context.bot.send_message(chat_id=CHANNEL_ID, text=text)
    except Exception as e:
        print(f"Error sending message: {e}")

def main():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN is missing!")
        return

    # اجرا کردن وب‌سرور در یک تاپیک جداگانه
    threading.Thread(target=run_flask, daemon=True).start()

    # ساخت و اجرای ربات تلگرام
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    if app.job_queue:
        app.job_queue.run_repeating(fetch_and_post, interval=7200, first=10)

    app.run_polling()

if __name__ == "__main__":
    main()
