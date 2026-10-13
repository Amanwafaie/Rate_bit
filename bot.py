import os
import httpx
from telegram.ext import ApplicationBuilder, ContextTypes

# دریافت متغیرهای محیطی
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

async def fetch_and_post(context: ContextTypes.DEFAULT_TYPE):
    url = "https://dab.gov.af/exchange-rates"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10)
            if response.status_code == 200:
                # پیام نمونه برای تست یا ارسال نرخ‌ها
                text = "📊 آخرین نرخ ارزهای د افغانستان بانک"
                await context.bot.send_message(chat_id=CHANNEL_ID, text=text)
    except Exception as e:
        print(f"Error fetching rates: {e}")

def main():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN is missing!")
        return

    # ساخت اپلیکیشن ربات
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # تنظیم ارسال خودکار هر ۲ ساعت یک‌بار (۷۲۰چ ثانیه)
    if app.job_queue:
        app.job_queue.run_repeating(fetch_and_post, interval=7200, first=10)

    # اجرای ربات با روش استاندارد نسخه ۲۱
    app.run_polling()

if __name__ == "__main__":
    main()
