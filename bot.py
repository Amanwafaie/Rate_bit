import os
import threading
import httpx
from bs4 import BeautifulSoup
from flask import Flask
from telegram.ext import ApplicationBuilder, ContextTypes

# ایجاد وب‌سرور برای زنده نگه داشتن سرویس روی Render
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is running and alive!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port)

# اطلاعات ربات و کانال
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

async def fetch_dab_rates():
    """تابع برای دریافت نرخ ارز از سایت د افغانستان بانک"""
    url = "https://dab.gov.af/exchange-rates"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                # استخراج اطلاعات نرخ ارز بر اساس ساختار سایت
                rates_text = "📊 **آخرین نرخ ارزهای د افغانستان بانک (DAB)**\n\n"
                
                # پیدا کردن جدول نرخ‌ها در صفحه
                tables = soup.find_all('table')
                if tables:
                    rows = tables[0].find_all('tr')
                    for row in rows[1:]: # رد کردن ردیف سرتیتر
                        cols = row.find_all('td')
                        if len(cols) >= 2:
                            currency = cols[0].get_text(strip=True)
                            rate = cols[1].get_text(strip=True)
                            rates_text += f"🔹 {currency}: `{rate}`\n"
                    return rates_text
                else:
                    return "📊 آخرین نرخ ارزها: اطلاعات جدول در سایت یافت نشد، اما اتصال برقرار است."
    except Exception as e:
        print(f"Error scraping DAB: {e}")
    return None

async def fetch_and_post(context: ContextTypes.DEFAULT_TYPE):
    """تایمر خودکار برای ارسال پیام هر ۲ ساعت"""
    text = await fetch_dab_rates()
    if text and CHANNEL_ID:
        try:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="Markdown")
        except Exception as e:
            print(f"Error sending message to channel: {e}")

def main():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN is missing!")
        return

    # استارت کردن وب‌سرور در پس‌زمینه
    threading.Thread(target=run_flask, daemon=True).start()

    # ساخت اپلیکیشن تلگرام
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # تنظیم زمان‌بندی (هر ۷۲۰۰ ثانیه = ۲ ساعت، و شروع اولین اجرا بعد از ۵ ثانیه)
    if app.job_queue:
        app.job_queue.run_repeating(fetch_and_post, interval=7200, first=5)

    app.run_polling()

if __name__ == "__main__":
    main()
