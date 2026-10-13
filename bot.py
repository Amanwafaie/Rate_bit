import os
import time
import threading
import httpx
from urllib.parse import quote
from bs4 import BeautifulSoup
from flask import Flask
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ApplicationHandlerStop,
    TypeHandler,
)

app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is running and alive!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port)

def keep_alive():
    url = os.getenv("RENDER_EXTERNAL_URL")
    if not url:
        return
    while True:
        time.sleep(600)
        try:
            httpx.get(url, timeout=15)
        except Exception as e:
            print(f"keep-alive error: {e}")

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

ADMINS = [a.strip() for a in os.getenv("ADMIN_ID", "").split(",") if a.strip()]

def is_admin(user_id):
    return str(user_id) in ADMINS

def now_kabul():
    kabul = timezone(timedelta(hours=4, minutes=30))
    return datetime.now(kabul).strftime("%Y-%m-%d  %H:%M")

def footer(note):
    f = f"\n━━━━━━━━━━━━━━\nℹ️ {note}\n🔄 به‌روزرسانی منظم\n"
    if CHANNEL_ID and CHANNEL_ID.startswith("@"):
        f += f"\n📢 {CHANNEL_ID}\n"
    f += "🤝 کانال را به دوستان خود معرفی کنید"
    return f

def share_keyboard():
    if not (CHANNEL_ID and CHANNEL_ID.startswith("@")):
        return None
    link = f"https://t.me/{CHANNEL_ID[1:]}"
    url = "https://t.me/share/url?url=" + quote(link) + "&text=" + quote("نرخ روزانه ارز")
    return InlineKeyboardMarkup([[InlineKeyboardButton("📤 اشتراک‌گذاری کانال", url=url)]])

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
            text = f"💱 نرخ ارز | نرخ مرجع د افغانستان بانک\n🕐 {now_kabul()}\n\n"
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
            return text + footer("نرخ مرجع رسمی است و ممکن است با بازار آزاد فرق داشته باشد.")
    except Exception as e:
        print(f"Error scraping DAB: {e}")
    return None

async def send_official(bot):
    text = await fetch_dab_rates()
    if not text:
        print("No rates fetched")
        return False
    await bot.send_message(chat_id=CHANNEL_ID, text=text, reply_markup=share_keyboard())
    return True

async def scheduled_post(context: ContextTypes.DEFAULT_TYPE):
    try:
        await send_official(context.bot)
    except Exception as e:
        print(f"Error sending message: {e}")

DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫٬،", "01234567890123456789.. ")

ICONS = [("دالر", "💵"), ("دلار", "💵"), ("یورو", "💶"), ("پوند", "💷"),
         ("کلدار", "🇵🇰"), ("تومان", "🇮🇷"), ("روپیه", "🇮🇳")]

def icon_for(name):
    for key, ic in ICONS:
        if key in name:
            return ic
    return "🔹"

def parse_line(line):
    line = line.translate(DIGITS).replace(",", ".")
    parts = line.split()
    if len(parts) < 3:
        return None
    try:
        sell = float(parts[-1])
        buy = float(parts[-2])
    except ValueError:
        return None
    name = " ".join(parts[:-2])
    return name, buy, sell

def build_market_message(rows):
    text = f"💱 نرخ بازار آزاد\n🕐 {now_kabul()}\n\n"
    for name, buy, sell in rows:
        text += f"{icon_for(name)} {name}\n   خرید: {buy:.2f}   |   فروش: {sell:.2f}\n\n"
    return text.rstrip() + "\n" + footer("نرخ بازار در طول روز تغییر می‌کند.")

HELP = (
    "نرخ‌ها را این‌طور بفرستید (هر خط یک ارز: اسم، خرید، فروش):\n\n"
    "/market\n"
    "دالر 65.00 65.05\n"
    "یورو 73.00 73.20\n"
    "کلدار 229.00 229.50\n"
    "تومان بانکی 0.25 0.26"
)

async def market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = (update.message.text or "").split("\n")
    first = lines[0].split(maxsplit=1)
    if len(first) > 1:
        lines[0] = first[1]
    else:
        lines = lines[1:]
    rows = [r for r in (parse_line(l) for l in lines) if r]
    if not rows:
        await update.message.reply_text(HELP)
        return
    msg = build_market_message(rows)
    context.user_data["pending"] = msg
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ ارسال به کانال", callback_data="send"),
        InlineKeyboardButton("❌ لغو", callback_data="cancel"),
    ]])
    await update.message.reply_text("پیش‌نمایش:\n\n" + msg, reply_markup=kb)

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "cancel":
        context.user_data.pop("pending", None)
        await q.edit_message_text("❌ لغو شد.")
        return
    if q.data == "send":
        msg = context.user_data.pop("pending", None)
        if not msg:
            await q.edit_message_text("⚠️ منقضی شد. دوباره /market بفرستید.")
            return
        try:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=msg, reply_markup=share_keyboard())
            await q.edit_message_text("✅ نرخ بازار ارسال شد")
        except Exception as e:
            await q.edit_message_text(f"❌ خطا: {e}")

async def postnow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        ok = await send_official(context.bot)
        await update.message.reply_text("✅ نرخ جدید ارسال شد" if ok else "❌ دریافت نرخ ناموفق بود")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"سلام! آیدی عددی شما: {update.effective_user.id}")

async def guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user and is_admin(user.id):
        return
    if not ADMINS and update.message and (update.message.text or "").startswith("/start"):
        return
    raise ApplicationHandlerStop

def main():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN is missing!")
        return
    if not ADMINS:
        print("Warning: ADMIN_ID is empty, nobody can use commands.")
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(TypeHandler(Update, guard), group=-1)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("postnow", postnow))
    app.add_handler(CommandHandler("market", market))
    app.add_handler(CallbackQueryHandler(on_button))
    if app.job_queue:
        app.job_queue.run_repeating(scheduled_post, interval=7200, first=10)
    app.run_polling()

if __name__ == "__main__":
    main()
