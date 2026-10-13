import os
import threading
import httpx
from bs4 import BeautifulSoup
from flask import Flask
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is running and alive!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
ADMIN_ID = os.getenv("ADMIN_ID")

CHANNEL_USERNAME = "@NewsAfghan24"
CHANNEL_LINK = "https://t.me/NewsAfghan24"

FOOTER = (
    "\n━━━━━━━━━━━━━━\n"
    "ℹ️ نرخ مرجع رسمی است و ممکن است با بازار آزاد فرق داشته باشد.\n"
    "🔄 به‌روزرسانی: هر ۲ ساعت\n\n"
    f"📢 {CHANNEL_USERNAME}\n"
    "🤝 کانال را به دوستان خود معرفی کنید"
)

SHARE_URL = (
    "https://t.me/share/url?url=" + CHANNEL_LINK +
    "&text=" + "نرخ روزانه ارز د افغانستان بانک"
)

def share_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📤 اشتراک‌گذاری کانال", url=SHARE_URL)
    ]])

NAMES = [
    ("USD", "دالر امریکا", "🇺🇸"),
    ("EURO", "یورو", "🇪🇺"),
    ("POUND", "پوند", "🇬🇧"),
    ("SWISS", "فرانک سویس", "🇨🇭"),
    ("INDIAN", "روپیه هند", "🇮🇳"),
    ("PAKISTAN", "روپیه پاکستان", "🇵🇰"),
    ("CNY", "یوان چین", "🇨🇳"),
    ("UAE", "درهم امارات", "🇦🇪"),
    ("SAUDI", "ریال سعودی", "🇸🇦"),
]

def translate(name):
    up = name.upper()
    for key, fa, flag in NAMES:
        if key in up:
            return fa, flag
    return None, None

async def fetch_dab_rates():
    url = "https://dab.gov.af/exchange-rates"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=20)
            if response.status_code != 200:
                return None
            soup = BeautifulSoup(response.text, "html.parser")
            tables = soup.find_all("table")
            if not tables:
                return None
            kabul = timezone(timedelta(hours=4, minutes=30))
            now = datetime.now(kabul).strftime("%Y-%m-%d  %H:%M")
            text = f"💱 نرخ ارز | نرخ مرجع د افغانستان بانک\n🕐 {now}\n\n"
            count = 0
            for row in tables[0].find_all("tr")[1:]:
                cols = row.find_all("td")
                if len(cols) < 2:
                    continue
                raw_name = cols[0].get_text(strip=True)
                fa, flag = translate(raw_name)
                if not fa:
                    continue
                try:
                    value = float(cols[1].get_text(strip=True).replace(",", ""))
                except ValueError:
                    continue
                up = raw_name.upper()
                if "INDIAN" in up or "PAKISTAN" in up:
                    text += f"{flag} {fa} (100): ؋ {value * 100:.2f}\n"
                else:
                    text += f"{flag} {fa}: ؋ {value:.2f}\n"
                count += 1
            if count == 0:
                return None
            text += FOOTER
            return text
    except Exception as e:
        print(f"Error scraping DAB: {e}")
    return None

async def send_rates(bot):
    text = await fetch_dab_rates()
    if not text:
        print("No rates fetched")
        return False
    await bot.send_message(
        chat_id=CHANNEL_ID,
        text=text,
        reply_markup=share_keyboard(),
    )
    return True

async def scheduled_post(context: ContextTypes.DEFAULT_TYPE):
    try:
        await send_rates(context.bot)
    except Exception as e:
        print(f"Error sending message: {e}")

async def postnow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_ID and str(update.effective_user.id) != str(ADMIN_ID):
        return
    try:
        ok = await send_rates(context.bot)
        if ok:
            await update.message.reply_text("✅ نرخ جدید ارسال شد")
        else:
            await update.message.reply_text("❌ دریافت نرخ ناموفق بود")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"سلام! آیدی عددی شما: {update.effective_user.id}\n"
        "برای ارسال فوری نرخ به کانال: /postnow"
    )

def main():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN is missing!")
        return
    threading.Thread(target=run_flask, daemon=True).start()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("postnow", postnow))
    if app.job_queue:
        app.job_queue.run_repeating(scheduled_post, interval=7200, first=10)
    app.run_polling()

if __name__ == "__main__":
    main()
